using System.Text.Json;
using System.Text.RegularExpressions;

// Display names live outside source sessions: sid, meta, analysis and GT bindings stay stable.
internal sealed class SessionNames(string path)
{
    private Dictionary<string,string> Read() => File.Exists(path)
        ? JsonSerializer.Deserialize<Dictionary<string,string>>(File.ReadAllBytes(path))
            ?? throw new InvalidDataException("会话名称文件无效") : [];
    internal string Get(string sid) => Read().GetValueOrDefault(sid,sid);
    internal void Set(string sid,string name)
    {
        if(!Regex.IsMatch(sid,"^[A-Za-z0-9_-]{1,128}$"))throw new ArgumentException("Invalid session id");
        name=name.Trim();
        if(name.Length is <1 or >80 || name.Any(char.IsControl))
            throw new ArgumentException("会话名称需为 1–80 个字符，不能包含换行或控制字符");
        var names=Read();names[sid]=name;
        Directory.CreateDirectory(Path.GetDirectoryName(path)!);
        string temp=path+"."+Guid.NewGuid().ToString("N")+".tmp";
        try
        {
            using(FileStream stream=new(temp,FileMode.CreateNew,FileAccess.Write,FileShare.None))
                JsonSerializer.Serialize(stream,names,new JsonSerializerOptions{WriteIndented=true});
            File.Move(temp,path,true);
        }
        finally{if(File.Exists(temp))File.Delete(temp);}
    }
}
