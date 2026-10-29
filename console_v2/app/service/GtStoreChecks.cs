using System.Text.Json;

/// <summary>
/// GtStore 的进程内回归（--self-check-gt）：只证明“缺陷真的被拒/合法文档真的能存”，
/// 不启动 Qt、不读会话。全部写入 --gt-root 指到的私有目录（内含一个放在子 store
/// 上一级的诱饵 draft.json，用来证明 Load("..") 读不到 store 之外）。
/// </summary>
internal static class GtStoreChecks
{
    internal static object Run(string root)
    {
        List<object> checks=[];
        bool passed=true;
        void Check(string name,bool ok,string detail="")
        {
            checks.Add(new{name,passed=ok,detail});
            passed&=ok;
        }

        static byte[] Document(string sessionId,object? suggestions=null,string boxOrigin="human",string? fromSuggestionId=null)
        {
            object suggestionList=suggestions ?? Array.Empty<object>();
            return JsonSerializer.SerializeToUtf8Bytes(new
            {
                format="gt_annotate",formatVersion=2,sessionId,
                coordinateFrame="sensor-IFW192S-raw",units="m",frameCount=3,annotator="self-check",
                persons=new[]{new{personId="P1",label=(string?)null,color=(string?)null}},
                boxes=new[]{new{boxId="box_1",frameIndex=0,personId="P1",x=1.0,y=2.0,w=1.5,h=0.8,
                    zMin=0.0,zMax=1.8,visibility="visible",reviewed=false,note=(string?)null,
                    origin=new{kind=boxOrigin,fromSuggestionId}}},
                intervals=new[]{new{intervalId="itv_1",personId="P1",kind="event",label="fall",
                    startFrame=0,endFrame=2,reviewed=false,note=(string?)null,origin=new{kind="human"}}},
                suggestions=suggestionList,
                sampleFrames=new[]{1},savedAtMs=1
            });
        }
        // 文档内的 sessionId 必须与被保存的 sid 一致（GtStore 会校验），所以两者用同一个参数。
        static int Save(GtStore store,string sid,object? suggestions=null,string boxOrigin="human",string? fromSuggestionId=null)
        {
            using JsonDocument doc=JsonDocument.Parse(Document(sid,suggestions,boxOrigin,fromSuggestionId));
            return store.Save(sid,0,doc.RootElement,3);
        }
        // 统一的“必须被拒”断言：只接受参数/IO 异常（不是崩溃，也不是静默通过）。
        static (bool Rejected,string Detail) Rejects(Action action)
        {
            try {action();return (false,"未被拒绝");}
            catch(ArgumentException error) {return (true,error.Message);}
            catch(IOException error) {return (true,error.Message);}
        }

        string fullRoot=Path.GetFullPath(root);
        GtStore store=new(fullRoot);
        Check("gt_root_has_no_trailing_separator",store.Root==Path.TrimEndingDirectorySeparator(fullRoot),store.Root);
        var rawSave=Rejects(()=>Save(store,"probe_raw"));
        Check("save_with_raw_gt_root_works",!rawSave.Rejected,rawSave.Detail);

        // 尾分隔符：直接构造带尾分隔符的 store，不依赖 Path.GetFullPath 是否保留它。
        GtStore trailing=new(store.Root+Path.DirectorySeparatorChar);
        var trailingSave=Rejects(()=>Save(trailing,"probe_trailing"));
        Check("save_with_trailing_separator_root_works",!trailingSave.Rejected,trailingSave.Detail);
        var conflict=Rejects(()=>Save(trailing,"probe_trailing"));
        Check("version_conflict_still_rejected",conflict.Rejected && conflict.Detail.Contains("版本冲突"),conflict.Detail);

        // 诱饵：在私有根目录里建 <root>/probe_escape/inner，把 draft.json 放在 inner 的上一级。
        // 修复前 inner.Load("..") 会读到这份诱饵；现在必须报「会话编号非法」。
        // 诱饵留在私有根目录内，不碰 --gt-root 的上一级。
        string escape=Path.Combine(store.Root,"probe_escape");
        Directory.CreateDirectory(Path.Combine(escape,"inner"));
        File.WriteAllBytes(Path.Combine(escape,"draft.json"),Document("probe_decoy"));
        GtStore inner=new(Path.Combine(escape,"inner"));
        var dotdot=Rejects(()=>inner.Load(".."));
        Check("load_rejects_dotdot",dotdot.Rejected,dotdot.Detail+"（同级诱饵存在）");
        var dot=Rejects(()=>inner.Load("."));
        Check("load_rejects_dot",dot.Rejected,dot.Detail);
        var saveDotdot=Rejects(()=>Save(inner,".."));
        Check("save_rejects_dotdot",saveDotdot.Rejected,saveDotdot.Detail);
        var saveSlash=Rejects(()=>Save(inner,"a/b"));
        Check("save_rejects_path_separator",saveSlash.Rejected,saveSlash.Detail);

        // suggestions：对齐 validation.ts 的 suggestion.duplicate-id / suggestion.empty（error 级）。
        // 重复 id 的两条建议都带框，确保被拒原因是 id 重复而不是 suggestion.empty。
        object? duplicate=new[]{new{suggestionId="s1",box=(object?)new{x=1.0,y=2.0,w=1.2,h=1.1,zMin=0.1,zMax=2.0},interval=(object?)null},
                                new{suggestionId="s1",box=(object?)new{x=1.0,y=2.0,w=1.2,h=1.1,zMin=0.1,zMax=2.0},interval=(object?)null}};
        var dup=Rejects(()=>Save(store,"probe_suggest_dup",duplicate));
        Check("suggestion_duplicate_id_rejected",dup.Rejected,dup.Detail);

        object? empty=new[]{new{suggestionId="s2",box=(object?)null,interval=(object?)null}};
        var emptyResult=Rejects(()=>Save(store,"probe_suggest_empty",empty));
        Check("suggestion_empty_rejected",emptyResult.Rejected,emptyResult.Detail);

        object? valid=new[]{new{suggestionId="s3",box=new{x=1.0,y=2.0,w=1.2,h=1.1,zMin=0.1,zMax=2.0},
                                 interval=(object?)null,status="proposed",adoptedRef=(string?)null}};
        var validSave=Rejects(()=>Save(store,"probe_suggest_valid",valid));
        Check("suggestion_valid_accepted",!validSave.Rejected,validSave.Detail);
        GtStore.Draft loaded=store.Load("probe_suggest_valid");
        bool kept=false;
        if(loaded.Exists && loaded.Doc.TryGetProperty("suggestions",out JsonElement saved))
        {
            JsonElement first=saved.EnumerateArray().First();
            kept=saved.GetArrayLength()==1 && first.GetProperty("suggestionId").GetString()=="s3";
        }
        Check("suggestion_survives_roundtrip",kept,"V"+loaded.Version);

        // warning 级（adopted 建议缺失）不拒绝：与 validation.ts 一致，是 warning 不是 error。
        var adopted=Rejects(()=>Save(store,"probe_adopted_warning",null,"adopted","missing_suggestion"));
        Check("adopted_origin_warning_not_rejected",!adopted.Rejected,adopted.Detail);

        // 合法网页文档形状：suggestion 带框、区间与取样清单都能存并读回。
        var webDraft=Rejects(()=>Save(store,"probe_web_draft",valid));
        GtStore.Draft web=store.Load("probe_web_draft");
        Check("valid_web_draft_roundtrip",!webDraft.Rejected && web.Exists && web.Version==1
            && web.Doc.GetProperty("boxes").GetArrayLength()==1
            && web.Doc.GetProperty("intervals").GetArrayLength()==1
            && web.Doc.GetProperty("sampleFrames").GetArrayLength()==1,"V"+web.Version);
        bool inside=web.Exists && Path.GetFullPath(Path.Combine(store.Root,"probe_web_draft","draft.json"))
            .StartsWith(store.Root+Path.DirectorySeparatorChar,StringComparison.OrdinalIgnoreCase);
        Check("draft_written_inside_store_root",inside,store.Root);

        return new{passed,root=fullRoot,checks};
    }
}
