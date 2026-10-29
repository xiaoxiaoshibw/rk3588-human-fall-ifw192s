using System.Diagnostics;
using System.Text.Json;

internal sealed class AnnotatorLauncher(string root,string python,string dataRoot,string reportDir,
    string? existingUrl,string[] analyses,string storeRoot) : IDisposable
{
    private Process? child;
    private string? url=existingUrl;
    internal async Task<string> Open(string sid,int frame)
    {
        if(child is {HasExited:true}){Dispose();url=null;}
        if(url is null)
        {
            Dispose();
            try
            {
            var start=new ProcessStartInfo(python){UseShellExecute=false,CreateNoWindow=true,
                RedirectStandardOutput=true,RedirectStandardError=true};
            foreach(string arg in new[]{"-u","-B","-W","error",Path.Combine(root,"pc_apps","annotator_v2","server.py"),
                "--port","0","--data-root",dataRoot,"--store-root",storeRoot})start.ArgumentList.Add(arg);
            foreach(string analysis in analyses){start.ArgumentList.Add("--analysis");start.ArgumentList.Add(analysis);}
            child=Process.Start(start)??throw new IOException("无法启动标注台服务");
            child.ErrorDataReceived+=(_,e)=>{if(e.Data is not null)File.AppendAllText(Path.Combine(reportDir,"annotator.stderr"),e.Data+Environment.NewLine);};
            child.BeginErrorReadLine();
            using var timeout=new CancellationTokenSource(TimeSpan.FromSeconds(10));
            string? line=await child.StandardOutput.ReadLineAsync(timeout.Token);
            using var ready=JsonDocument.Parse(line??throw new IOException("标注台服务未就绪"));
            url=ready.RootElement.GetProperty("url").GetString()!;
            }
            catch{Dispose();throw;}
        }
        if(!Uri.TryCreate(url,UriKind.Absolute,out Uri? uri) || !uri.IsLoopback || uri.Scheme!="http"
            || !string.IsNullOrEmpty(uri.UserInfo))throw new ArgumentException("标注台地址必须是本机 HTTP 服务");
        using HttpClient http=new(){Timeout=TimeSpan.FromSeconds(5)};
        using var doc=JsonDocument.Parse(await http.GetStringAsync(new Uri(uri,"api/sessions")));
        if(!doc.RootElement.GetProperty("sessions").EnumerateArray().Any(s=>s.GetProperty("sessionId").GetString()==sid))
            throw new IOException("标注台服务中不存在所选会话，请检查数据目录");
        return new Uri(uri,"?sid="+Uri.EscapeDataString(sid)+"&frame="+Math.Max(0,frame)).AbsoluteUri;
    }
    public void Dispose()
    {
        Process? process=child;child=null;
        if(process is not null){if(!process.HasExited)process.Kill(true);process.Dispose();}
    }
}
