using System.Text.Json;
using System.Text.RegularExpressions;

/// <summary>
/// 标注文档（gt_annotate/2）本机读写：与 Web 标注台同一 store 目录、同一格式，
/// 写入用临时文件原子替换并做版本冲突检测；字段校验覆盖
/// pc_apps/annotator_v2/src/domain/validation.ts 的 error 级规则
/// （persons / boxes / intervals / suggestions / sampleFrames；warning 级的
/// 「adopted 框引用不存在的建议」「accepted 建议无 adoptedRef」不拒绝保存）。
/// 只写本机标注 store，不读写会话原始数据、不触板端。
/// </summary>
internal sealed class GtStore(string root)
{
    // 会话编号直接拼进路径：拒绝 "." 与 ".."（否则 Load 可读到 store 之外），也不接受分隔符。
    private static readonly Regex SessionPattern=new(@"^(?!\.\.?$)[A-Za-z0-9_.-]{1,128}$",RegexOptions.CultureInvariant);
    private static readonly Regex IdPattern=new("^[A-Za-z0-9_.-]{1,64}$",RegexOptions.CultureInvariant);
    // 去掉尾分隔符：否则 Root+separator 变成 "D:\foo\\"，Save 的前缀检查恒假。
    internal string Root{get;}=Path.TrimEndingDirectorySeparator(Path.GetFullPath(root));
    // 根目录本身以分隔符结尾（如盘符根）时不能再补一个。
    private string RootPrefix=>Root.EndsWith(Path.DirectorySeparatorChar)?Root:Root+Path.DirectorySeparatorChar;

    internal sealed record Draft(int Version,string? SavedAt,JsonElement Doc,bool Exists);

    /// <summary>会话目录：编号合法且解析后仍在 Root 之下；Load 与 Save 共用同一条路径检查。</summary>
    private string ResolveDirectory(string sid)
    {
        if(!SessionPattern.IsMatch(sid))throw new ArgumentException("会话编号非法");
        string directory=Path.GetFullPath(Path.Combine(Root,sid));
        if(!directory.StartsWith(RootPrefix,StringComparison.OrdinalIgnoreCase))
            throw new IOException("标注目录越出标注 store 根目录");
        return directory;
    }

    internal Draft Load(string sid)
    {
        string path=Path.Combine(ResolveDirectory(sid),"draft.json");
        if(!File.Exists(path))return new(0,null,default,false);
        using JsonDocument envelope=JsonDocument.Parse(File.ReadAllBytes(path));
        JsonElement rootElement=envelope.RootElement;
        int version=rootElement.TryGetProperty("version",out JsonElement v)&&v.ValueKind==JsonValueKind.Number?v.GetInt32():0;
        string? savedAt=rootElement.TryGetProperty("saved_at",out JsonElement s)&&s.ValueKind==JsonValueKind.String?s.GetString():null;
        JsonElement doc=rootElement.TryGetProperty("doc",out JsonElement d)&&d.ValueKind==JsonValueKind.Object?d.Clone():default;
        return new(version,savedAt,doc,doc.ValueKind==JsonValueKind.Object);
    }

    /// <summary>校验后原子保存；baseVersion 与磁盘当前版本不符时抛冲突，不覆盖他人编辑。</summary>
    internal int Save(string sid,int baseVersion,JsonElement doc,int frameCount)
    {
        Validate(doc,sid,frameCount);
        string directory=ResolveDirectory(sid),path=Path.Combine(directory,"draft.json");
        EnsureWritable(directory);
        int current=File.Exists(path)?Load(sid).Version:0;
        if(baseVersion!=current)
            throw new IOException($"标注版本冲突：磁盘为 V{current}，界面基于 V{baseVersion}；请先重载再保存");
        Directory.CreateDirectory(directory);
        string temporary=path+".tmp-"+Guid.NewGuid().ToString("N");
        try
        {
            using(FileStream stream=new(temporary,FileMode.CreateNew,FileAccess.Write,FileShare.None))
            using(Utf8JsonWriter writer=new(stream))
            {
                writer.WriteStartObject();
                writer.WriteNumber("version",current+1);
                writer.WriteString("saved_at",DateTime.Now.ToString("yyyy-MM-ddTHH:mm:ss"));
                writer.WritePropertyName("doc");doc.WriteTo(writer);
                writer.WriteEndObject();
            }
            File.Move(temporary,path,true);
        }
        finally {if(File.Exists(temporary))File.Delete(temporary);}
        return current+1;
    }

    private static void Validate(JsonElement doc,string sid,int frameCount)
    {
        if(doc.ValueKind!=JsonValueKind.Object)throw new IOException("标注文档必须是 JSON 对象");
        if(Text(doc,"format")!="gt_annotate")
            throw new IOException("标注文档 format 必须是 gt_annotate");
        if(Number(doc,"formatVersion")!=2)
            throw new IOException("只支持 formatVersion 2 的标注文档");
        if(Text(doc,"sessionId")!=sid)
            throw new IOException("标注文档的会话编号与当前会话不一致");
        if(Text(doc,"coordinateFrame")!="sensor-IFW192S-raw" || Text(doc,"units")!="m")
            throw new IOException("标注文档坐标系或单位与传感器原始坐标不匹配");
        int declared=(int)Number(doc,"frameCount");
        if(declared!=frameCount)
            throw new IOException($"标注文档帧数 {declared} 与当前会话 {frameCount} 不一致，请重载");

        HashSet<string> persons=new(StringComparer.Ordinal);
        foreach(JsonElement person in Array(doc,"persons").EnumerateArray())
        {
            string id=Text(person,"personId");
            if(id.Length==0 || !IdPattern.IsMatch(id))throw new IOException($"人物 id 非法：{id}");
            if(!persons.Add(id))throw new IOException($"人物 id 重复：{id}");
        }
        HashSet<string> boxIds=new(StringComparer.Ordinal);
        HashSet<string> perPersonFrame=new(StringComparer.Ordinal);
        foreach(JsonElement box in Array(doc,"boxes").EnumerateArray())
        {
            string id=Text(box,"boxId");
            if(id.Length==0 || !IdPattern.IsMatch(id))throw new IOException($"框 id 非法：{id}");
            if(!boxIds.Add(id))throw new IOException($"框 id 重复：{id}");
            string person=Text(box,"personId");
            if(!persons.Contains(person))throw new IOException($"框 {id} 引用不存在的人物：{person}");
            int frame=(int)Number(box,"frameIndex");
            if(frame<0 || frame>=frameCount)throw new IOException($"框 {id} 帧号越界：{frame}");
            double x=Number(box,"x"),y=Number(box,"y"),w=Number(box,"w"),h=Number(box,"h");
            double zMin=Number(box,"zMin"),zMax=Number(box,"zMax");
            if(!double.IsFinite(x) || !double.IsFinite(y) || !double.IsFinite(w) || !double.IsFinite(h)
                || !double.IsFinite(zMin) || !double.IsFinite(zMax))
                throw new IOException($"框 {id} 含非有限数值");
            if(!(w>0) || !(h>0))throw new IOException($"框 {id} 宽高必须为正");
            if(w>200 || h>200)throw new IOException($"框 {id} 尺寸超出 200 m，拒绝保存");
            if(!(zMax>zMin))throw new IOException($"框 {id} 的 zMax 必须大于 zMin");
            if(!perPersonFrame.Add(person+"@"+frame))throw new IOException($"同一人物同帧存在多个框：{person}@{frame}");
            string visibility=Text(box,"visibility");
            if(visibility is not ("visible" or "partial" or "occluded"))
                throw new IOException($"框 {id} 可见性非法：{visibility}");
            string kind=Text(Object(box,"origin"),"kind");
            if(kind is not ("human" or "propagated" or "adopted"))
                throw new IOException($"框 {id} 来源非法：{kind}");
        }
        HashSet<string> intervalIds=new(StringComparer.Ordinal);
        if(doc.TryGetProperty("intervals",out JsonElement intervals))
        {
            if(intervals.ValueKind!=JsonValueKind.Array)throw new IOException("intervals 必须是数组");
            foreach(JsonElement interval in intervals.EnumerateArray())
            {
                string id=Text(interval,"intervalId");
                if(id.Length==0 || !IdPattern.IsMatch(id))throw new IOException($"区间 id 非法：{id}");
                if(!intervalIds.Add(id))throw new IOException($"区间 id 重复：{id}");
                if(!persons.Contains(Text(interval,"personId")))throw new IOException($"区间 {id} 引用不存在的人物");
                double start=Number(interval,"startFrame"),end=Number(interval,"endFrame");
                if(start<0 || end>=frameCount || start>end)throw new IOException($"区间 {id} 帧范围非法");
                if(Text(interval,"label").Length==0)throw new IOException($"区间 {id} 标签为空");
            }
        }
        HashSet<string> suggestionIds=new(StringComparer.Ordinal);
        if(doc.TryGetProperty("suggestions",out JsonElement suggestions))
        {
            if(suggestions.ValueKind!=JsonValueKind.Array)throw new IOException("suggestions 必须是数组");
            foreach(JsonElement suggestion in suggestions.EnumerateArray())
            {
                string id=Text(suggestion,"suggestionId");
                if(!suggestionIds.Add(id))throw new IOException($"建议 id 重复：{id}");
                // 对齐 validation.ts 的 suggestion.empty：框与区间都为 null 的建议没有产物。
                if(IsNullProperty(suggestion,"box") && IsNullProperty(suggestion,"interval"))
                    throw new IOException($"建议 {id} 必须携带框或区间之一");
            }
        }
        if(doc.TryGetProperty("sampleFrames",out JsonElement samples))
        {
            if(samples.ValueKind!=JsonValueKind.Array)throw new IOException("sampleFrames 必须是数组");
            foreach(JsonElement sample in samples.EnumerateArray())
            {
                if(sample.ValueKind!=JsonValueKind.Number)throw new IOException("sampleFrames 只能包含帧号");
                int frame=sample.GetInt32();
                if(frame<0 || frame>=frameCount)throw new IOException($"标注帧清单越界：{frame}（共 {frameCount} 帧）");
            }
        }
    }

    /// <summary>只允许写 Root 之下的真实目录：含目录链接（junction/reparse point）时拒绝。</summary>
    private void EnsureWritable(string directory)
    {
        string full=Path.GetFullPath(directory);
        if(!full.StartsWith(RootPrefix,StringComparison.OrdinalIgnoreCase))
            throw new IOException("标注目录越出标注 store 根目录");
        for(string? path=full;path is not null;path=Path.GetDirectoryName(path))
        {
            if(Directory.Exists(path) && (File.GetAttributes(path)&FileAttributes.ReparsePoint)!=0)
                throw new IOException("标注目录含目录链接，拒绝写入");
            if(string.Equals(path,Root,StringComparison.OrdinalIgnoreCase))break;
        }
    }

    private static JsonElement Array(JsonElement parent,string name)
    {
        if(!parent.TryGetProperty(name,out JsonElement value) || value.ValueKind!=JsonValueKind.Array)
            throw new IOException($"标注文档字段 {name} 缺失或不是数组");
        return value;
    }

    private static JsonElement Object(JsonElement parent,string name)
    {
        if(!parent.TryGetProperty(name,out JsonElement value) || value.ValueKind!=JsonValueKind.Object)
            throw new IOException($"标注文档字段 {name} 缺失或不是对象");
        return value;
    }

    // 与 validation.ts 的 `s.box === null` / `s.interval === null` 一致：字段缺失不算 null。
    private static bool IsNullProperty(JsonElement parent,string name)
        => parent.TryGetProperty(name,out JsonElement value) && value.ValueKind==JsonValueKind.Null;

    private static string Text(JsonElement parent,string name)
    {
        if(!parent.TryGetProperty(name,out JsonElement value) || value.ValueKind!=JsonValueKind.String)
            throw new IOException($"标注文档字段 {name} 缺失或不是字符串");
        return value.GetString()!;
    }

    private static double Number(JsonElement parent,string name)
    {
        if(!parent.TryGetProperty(name,out JsonElement value) || value.ValueKind!=JsonValueKind.Number
            || !value.TryGetDouble(out double number))
            throw new IOException($"标注文档字段 {name} 缺失或不是数字");
        return number;
    }
}