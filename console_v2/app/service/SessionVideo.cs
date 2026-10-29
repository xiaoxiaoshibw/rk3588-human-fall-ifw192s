using System.Diagnostics;
using System.Text;
using System.Text.Json;
using System.Threading.Channels;

// PC-only decoder process. Its input and output are latest-value mailboxes.
internal sealed class SessionVideo : IDisposable
{
    private readonly string directory,python,worker,reportDir;
    private readonly object gate=new();
    private Process? child;
    private CancellationTokenSource? stop;
    private Channel<object>? requests;
    private JsonElement? pending;
    private string? error;
    private string lastKey="";
    private long lastRequestAt,requestId;
    internal string SessionId {get;}
    internal string[] Options {get;}
    internal string? Selected {get;private set;}
    internal int Version {get;private set;}
    internal double OffsetSec {get;private set;}
    internal string? Error {get{lock(gate)return error;}}
    internal object Info => new{sessionId=SessionId,available=Selected is not null,name=Selected,
        options=Options,mediaVersion=Version,offsetMs=OffsetSec*1000,error};
    internal SessionVideo(string directory,string python,string worker,string reportDir)
    {
        this.directory=directory;this.python=python;this.worker=worker;this.reportDir=reportDir;
        SessionId=Path.GetFileName(directory);
        string[] extensions=[".mjpeg",".mjpg",".mp4",".mov",".avi",".mkv",".webm"];
        bool IsVideo(string path)
        {
            if(!extensions.Contains(Path.GetExtension(path).ToLowerInvariant()))return false;
            try{return !File.GetAttributes(path).HasFlag(FileAttributes.ReparsePoint) && new FileInfo(path).Length>0;}
            catch(Exception e) when(e is IOException or UnauthorizedAccessException){return false;}
        }
        Options=Directory.EnumerateFiles(directory)
            .Where(IsVideo)
            .OrderBy(p=>Path.GetFileName(p).Equals("camera.mjpeg",StringComparison.OrdinalIgnoreCase)?0:1)
            .ThenBy(Path.GetFileName,StringComparer.OrdinalIgnoreCase).Select(p=>Path.GetFileName(p)).ToArray();
        Selected=Options.FirstOrDefault();
    }
    internal void Select(string name)
    {
        if(!Options.Contains(name))throw new ArgumentException("视频不在当前会话目录中");
        Stop();Selected=name;OffsetSec=0;Version++;
    }
    internal void SetOffset(double seconds)
    {
        if(!double.IsFinite(seconds) || Math.Abs(seconds)>60)throw new ArgumentException("视频偏移不能超过60秒");
        OffsetSec=seconds;Version++;lastKey="";
    }
    internal void Request(int generation,int sourceFrameIndex,double sourceTimeSec,double? bagTimeSec,bool playing)
    {
        if(Selected is null)return;
        if(error is not null)return;
        string key=$"{generation}/{Version}/{sourceFrameIndex}/{Math.Floor(sourceTimeSec*30)}/{playing}";
        if(key==lastKey)return;
        if(lastRequestAt!=0 && Stopwatch.GetElapsedTime(lastRequestAt).TotalSeconds<1.0/30
            && lastKey.StartsWith($"{generation}/{Version}/",StringComparison.Ordinal) && playing)return;
        try
        {
            if(child is null)Start();
            if(child!.HasExited)throw new IOException("视频解码进程已退出");
            lastKey=key;lastRequestAt=Stopwatch.GetTimestamp();
            requests!.Writer.TryWrite(new{requestId=++requestId,path=Path.Combine(directory,Selected),sessionId=SessionId,
                generation,mediaVersion=Version,sourceFrameIndex,sourceTimeSec,bagTimeSec,offsetSec=OffsetSec});
        }
        catch(Exception e) when(e is IOException or InvalidOperationException or System.ComponentModel.Win32Exception)
        {lock(gate)error=e.Message;lastKey=key;}
    }
    private void Start()
    {
        var start=new ProcessStartInfo(python){UseShellExecute=false,CreateNoWindow=true,
            RedirectStandardInput=true,RedirectStandardOutput=true,RedirectStandardError=true,
            StandardInputEncoding=new UTF8Encoding(false),StandardOutputEncoding=Encoding.UTF8,StandardErrorEncoding=Encoding.UTF8};
        foreach(string arg in new[]{"-u","-B","-W","error",worker})start.ArgumentList.Add(arg);
        start.Environment["PYTHONIOENCODING"]="utf-8";
        child=Process.Start(start)??throw new IOException("无法启动视频解码器");
        child.StandardInput.AutoFlush=true;
        stop=new();var token=stop.Token;Process process=child;
        requests=Channel.CreateBounded<object>(new BoundedChannelOptions(1){FullMode=BoundedChannelFullMode.DropOldest,SingleReader=true,SingleWriter=true});
        Channel<object> channel=requests;
        child.ErrorDataReceived+=(_,e)=>{if(e.Data is not null)File.AppendAllText(Path.Combine(reportDir,"video.stderr"),e.Data+Environment.NewLine);};
        child.BeginErrorReadLine();
        _=Task.Run(async()=>
        {
            try
            {
                await foreach(object request in channel.Reader.ReadAllAsync(token))
                    await process.StandardInput.WriteLineAsync(JsonSerializer.Serialize(request).AsMemory(),token);
            }
            catch(Exception e) when(e is OperationCanceledException or IOException or InvalidOperationException)
            {if(!token.IsCancellationRequested)lock(gate)error=e.Message;}
        });
        _=Task.Run(async()=>
        {
            try
            {
                while(!token.IsCancellationRequested)
                {
                    string? line=await process.StandardOutput.ReadLineAsync(token);
                    if(line is null)break;
                    if(line.Length>900_000)throw new InvalidDataException("Video response exceeds limit");
                    using var doc=JsonDocument.Parse(line);
                    lock(gate)if(!token.IsCancellationRequested)pending=doc.RootElement.Clone();
                }
            }
            catch(Exception e) when(e is OperationCanceledException or IOException or InvalidOperationException or JsonException)
            {if(!token.IsCancellationRequested)lock(gate)error=e.Message;}
        });
    }
    internal JsonElement? Take(){lock(gate){JsonElement? value=pending;pending=null;return value;}}
    internal void Stop()
    {
        stop?.Cancel();requests?.Writer.TryComplete();
        Process? process=child;child=null;
        if(process is not null)
        {
            if(!process.HasExited){process.Kill(true);process.WaitForExit(2000);}
            process.Dispose();
        }
        stop?.Dispose();stop=null;requests=null;lastKey="";lastRequestAt=0;
        lock(gate){pending=null;error=null;}
    }
    public void Dispose()=>Stop();
}
