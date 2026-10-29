using System.Diagnostics;
using System.IO.MemoryMappedFiles;
using System.IO.Pipes;
using System.Text;
using System.Text.Json;
using System.Text.RegularExpressions;
using System.Threading.Channels;

internal static class Program
{
    internal static async Task<int> Main(string[] args)
    {
        string Option(string key,string fallback="") { int i=Array.IndexOf(args,key); return i>=0 && i+1<args.Length?args[i+1]:fallback; }
        string sessionPath=Path.GetFullPath(Option("--session"));
        string dataRoot=Path.GetDirectoryName(sessionPath)!;
        string reportPath=Path.GetFullPath(Option("--report"));
        DirectoryInfo? root=new(AppContext.BaseDirectory);
        while(root is not null && !File.Exists(Path.Combine(root.FullName,"AGENTS.md")))root=root.Parent;
        if(root is null)throw new ArgumentException("Workspace root is unavailable");
        string allowed=Path.Combine(root.FullName,"console_v2",".tools","app-evidence")+Path.DirectorySeparatorChar;
        if(!reportPath.StartsWith(allowed,StringComparison.OrdinalIgnoreCase))
            throw new ArgumentException("Reports must be in the private console_v2/.tools/app-evidence directory");
        for(DirectoryInfo? parent=new(Path.GetDirectoryName(reportPath)!);parent is not null;parent=parent.Parent)
            if(parent.Exists && parent.Attributes.HasFlag(FileAttributes.ReparsePoint))throw new ArgumentException("Report directory links are rejected");
        if(Option("--screenshot")!="" && Path.GetFullPath(Option("--screenshot"))!=Path.Combine(Path.GetDirectoryName(reportPath)!,"window.png"))
            throw new ArgumentException("Smoke screenshot must use the same private report directory");
        // Reserve the report before starting native/remote work; never overwrite an existing file.
        using FileStream report=new(reportPath,FileMode.CreateNew,FileAccess.Write,FileShare.Read);
        List<object> log=[];
        long applicationStarted=Stopwatch.GetTimestamp();
        SessionReader? session=null;
        Process? child=null;
        LiveSource? live=null;
        SessionVideo? video=null;
        bool passed=false;
        int jointMutationRequests=0,sessionDeletes=0;
        Dictionary<string,string> analysisPaths=[];
        for(int i=0;i<args.Length-1;i++)if(args[i]=="--analysis")
        {
            using JsonDocument a=JsonDocument.Parse(File.ReadAllBytes(args[i+1]));
            analysisPaths.Add(a.RootElement.GetProperty("sessionId").GetString()!,Path.GetFullPath(args[i+1]));
        }
        SessionReader Open(string path)
        {
            string sid=Path.GetFileName(Path.TrimEndingDirectorySeparator(path));
            if(analysisPaths.TryGetValue(sid,out string? existing))return new(path,existing);
            string saved=Path.Combine(root.FullName,"console_v2",".tools","local-analysis",sid);
            if(!args.Contains("--no-restore-local") && Directory.Exists(saved) && !File.GetAttributes(saved).HasFlag(FileAttributes.ReparsePoint))
            {
                foreach(string job in Directory.EnumerateDirectories(saved).OrderByDescending(Directory.GetLastWriteTimeUtc))
                {
                    try
                    {
                        string result=Path.Combine(job,"RESULT.json"), run=Path.Combine(job,"run"), analysisPath=Path.Combine(run,"analysis.json");
                        if(File.GetAttributes(job).HasFlag(FileAttributes.ReparsePoint) || !File.Exists(result) || !Directory.Exists(run)
                            || File.GetAttributes(run).HasFlag(FileAttributes.ReparsePoint) || !File.Exists(analysisPath)
                            || File.GetAttributes(result).HasFlag(FileAttributes.ReparsePoint) || File.GetAttributes(analysisPath).HasFlag(FileAttributes.ReparsePoint))continue;
                        using JsonDocument manifest=JsonDocument.Parse(File.ReadAllBytes(result));JsonElement record=manifest.RootElement;
                        if(record.GetProperty("kind").GetString()!="analysis" || record.GetProperty("sessionId").GetString()!=sid
                            || !string.Equals(Path.GetFullPath(record.GetProperty("path").GetString()??""),Path.GetFullPath(analysisPath),StringComparison.OrdinalIgnoreCase))continue;
                        SessionReader verified=new(path,analysisPath);analysisPaths[sid]=analysisPath;
                        log.Add(new{eventType="localAnalysisRestored",sessionId=sid,path=analysisPath});return verified;
                    }
                    catch(Exception error) when(error is IOException or UnauthorizedAccessException or JsonException or InvalidOperationException or ArgumentException or KeyNotFoundException)
                    {log.Add(new{eventType="localAnalysisRestoreRejected",sessionId=sid,message=error.Message});}
                }
            }
            return new(path,null);
        }
        try
        {
            log.Add(new{eventType="selfChecks",checks=SelfChecks.Run()});
            if(args.Contains("--self-check-gt"))
            {
                // 标注 store 回归：不启动 Qt、不读会话；--gt-root 原样交给 GtStore（含尾分隔符）。
                string rawRoot=Option("--gt-root");
                if(rawRoot=="")throw new ArgumentException("--self-check-gt needs --gt-root");
                log.Add(new{eventType="gtStoreChecks",rawRoot,checks=GtStoreChecks.Run(rawRoot)});
                passed=true;return 0;
            }
            session=Open(sessionPath);
            int initialFrame=int.Parse(Option("--frame","0"));
            if(initialFrame<0 || initialFrame>=session.Frames.Length)throw new ArgumentException("Initial frame out of range");
            if(args.Contains("--check"))
            {
                for(int i=0;i<session.Frames.Length;i++)log.Add(new{eventType="decoded",info=session.Read(i,0,false,1).Info});
                passed=true;return 0;
            }
            SessionNames names=new(Path.GetFullPath(Option("--names-file",Path.Combine(root.FullName,"console_v2","user_data","session_names.json"))));
            // 标注文档与 Web 标注台共用同一 store（gt_annotate/2）；测试用 --gt-root 指向私有目录。
            string gtRoot=Path.GetFullPath(Option("--gt-root",Path.Combine(root.FullName,"pc_apps","annotator_v2","gt_store_v2")));
            GtStore gtStore=new(gtRoot);
            using AnnotatorLauncher annotator=new(root.FullName,Option("--python","python"),dataRoot,Path.GetDirectoryName(reportPath)!,
                Option("--annotator-url")==""?null:Option("--annotator-url"),analysisPaths.Values.ToArray(),gtRoot);
            using JointCaptureClient? joint=Option("--joint-url")==""?null:new(Option("--joint-url"));
            string token=Guid.NewGuid().ToString("N"),pipeName="ConsoleV2App_"+token,mapName="Local\\ConsoleV2App_"+token;
            const int capacity=12_000_000; // one finite scene + one measured target, each <=500k XYZ
            using MemoryMappedFile map=MemoryMappedFile.CreateNew(mapName,capacity);
            using MemoryMappedViewAccessor writer=map.CreateViewAccessor(0,capacity,MemoryMappedFileAccess.Write);
            using NamedPipeServerStream pipe=new(pipeName,PipeDirection.InOut,1,PipeTransmissionMode.Byte,
                PipeOptions.Asynchronous|PipeOptions.CurrentUserOnly);
            ProcessStartInfo start=new(Option("--host")){UseShellExecute=false,CreateNoWindow=true,
                RedirectStandardError=true,RedirectStandardOutput=true};
            start.ArgumentList.Add("--pipe");start.ArgumentList.Add(pipeName);
            start.EnvironmentVariables["QT_ASSUME_STDERR_HAS_CONSOLE"]="1"; // GUI 子进程的 Qt 日志也走 stderr，随报告归档
            if(args.Contains("--smoke")){start.ArgumentList.Add("--smoke");start.ArgumentList.Add("--screenshot");start.ArgumentList.Add(Option("--screenshot"));}
            if(Option("--smoke-live")!="")
            {
                if(!new Uri(Option("--smoke-live")).IsLoopback)throw new ArgumentException("Smoke tests use loopback only");
                start.ArgumentList.Add("--smoke-live");start.ArgumentList.Add(Option("--smoke-live"));
            }
            if(args.Contains("--smoke-joint"))start.ArgumentList.Add("--smoke-joint");
            if(args.Contains("--smoke-pick"))start.ArgumentList.Add("--smoke-pick");
            if(args.Contains("--no-external-open"))start.ArgumentList.Add("--no-external-open");
            if(Option("--live-url")!=""){start.ArgumentList.Add("--live-url");start.ArgumentList.Add(Option("--live-url"));}
            if(Option("--workspace-report")!=""){start.ArgumentList.Add("--workspace-report");start.ArgumentList.Add(Option("--workspace-report"));}
            if(Option("--live-duration-ms")!=""){start.ArgumentList.Add("--live-duration-ms");start.ArgumentList.Add(Option("--live-duration-ms"));}
            foreach(string key in new[]{"--video-report","--preview-report","--annotation-report","--tour-report","--alert-report","--local-report","--offline-preview-report"})
                if(Option(key)!=""){start.ArgumentList.Add(key);start.ArgumentList.Add(Option(key));}
            if(args.Contains("--preview-stale"))start.ArgumentList.Add("--preview-stale");
            if(Option("--camera-report")!=""){start.ArgumentList.Add("--camera-report");start.ArgumentList.Add(Option("--camera-report"));}
            if(Option("--camera-reload-report")!=""){start.ArgumentList.Add("--camera-reload-report");start.ArgumentList.Add(Option("--camera-reload-report"));}
            if(Option("--smoke-delete")!=""){start.ArgumentList.Add("--smoke-delete");start.ArgumentList.Add(Option("--smoke-delete"));}
            if(args.Contains("--smoke-depth"))start.ArgumentList.Add("--smoke-depth");
            if(Option("--smoke-frame")!=""){start.ArgumentList.Add("--smoke-frame");start.ArgumentList.Add(Option("--smoke-frame"));}
            if(Option("--smoke-playback-ms")!=""){start.ArgumentList.Add("--smoke-playback-ms");start.ArgumentList.Add(Option("--smoke-playback-ms"));}
            if(Option("--ack-fault")!="")
            {
                if(Option("--ack-fault") is not ("missing" or "missing-live" or "bad"))throw new ArgumentException("Bad ACK fault option");
                start.ArgumentList.Add("--ack-fault");start.ArgumentList.Add(Option("--ack-fault"));
            }
            if(Option("--qml-file")!=""){start.ArgumentList.Add("--qml-file");start.ArgumentList.Add(Path.GetFullPath(Option("--qml-file")));}
            if(Option("--ground")!=""){start.ArgumentList.Add("--ground");start.ArgumentList.Add(Path.GetFullPath(Option("--ground")));}
            if(args.Contains("--smoke-reload"))start.ArgumentList.Add("--smoke-reload");
            child=Process.Start(start)??throw new IOException("Qt failed to start");
            // 子进程日志（Qt/QML 警告、着色器编译失败等）随报告归档，便于事后诊断。
            child.OutputDataReceived+=(_,e)=>{if(e.Data is not null)log.Add(new{eventType="nativeStdout",message=e.Data});};
            child.ErrorDataReceived+=(_,e)=>{if(e.Data is not null)log.Add(new{eventType="nativeStderr",atMs=Stopwatch.GetElapsedTime(applicationStarted).TotalMilliseconds,message=e.Data});};
            child.BeginOutputReadLine();child.BeginErrorReadLine();
            using CancellationTokenSource timeout=new(TimeSpan.FromSeconds(20));
            await pipe.WaitForConnectionAsync(timeout.Token);
            using StreamReader input=new(pipe,Encoding.UTF8,false,4096,true);
            using BinaryWriter output=new(pipe,Encoding.UTF8,true);
            void Send(object value)
            {
                byte[] bytes=JsonSerializer.SerializeToUtf8Bytes(value);
                output.Write(bytes.Length);output.Write(bytes);output.Flush();
            }
            bool videoEnabled=false;
            string reportedVideoError="";
            void SendVideoInfo(bool active=true) => Send(new{type="videoInfo",info=video!.Info,active});
            void ChangeVideoSession()
            {
                video?.Dispose();
                video=new(session!.DirectoryPath,Option("--python","python"),Path.Combine(root.FullName,"console_v2","app","video_worker.py"),Path.GetDirectoryName(reportPath)!);
                videoEnabled=false;SendVideoInfo();
            }
            video=new(session.DirectoryPath,Option("--python","python"),Path.Combine(root.FullName,"console_v2","app","video_worker.py"),Path.GetDirectoryName(reportPath)!);
            object[] Sessions() => Directory.EnumerateDirectories(dataRoot).Where(p=>File.Exists(Path.Combine(p,"meta.json")))
                .Select(p=>(object)new{id=Path.GetFileName(p),name=names.Get(Path.GetFileName(p)),hasAnalysis=analysisPaths.ContainsKey(Path.GetFileName(p))}).ToArray();
            Send(new{type="hello",version=1,map=mapName,capacity,sessions=Sessions(),jointConfigured=joint is not null});
            SendVideoInfo(Option("--live-url")=="");
            Channel<JsonElement> commands=Channel.CreateBounded<JsonElement>(64);
            using CancellationTokenSource stop=new();
            Task reader=Task.Run(async()=>
            {
                try
                {
                    while(!stop.IsCancellationRequested)
                    {
                        string? line=await input.ReadLineAsync(stop.Token);
                        if(line is null)break;
                        // 1 MiB 只给整份标注文档（gtSave）留余量；其余命令远小于此。
                        if(line.Length>1_048_576)throw new InvalidDataException("UI command too large");
                        using JsonDocument d=JsonDocument.Parse(line);
                        await commands.Writer.WriteAsync(d.RootElement.Clone(),stop.Token);
                    }
                }
                finally{commands.Writer.TryComplete();}
            });
            int index=initialFrame,generation=0,shown=-1,shownGeneration=-1;
            bool playing=false,waiting=false,quit=false;
            bool localEnabled=analysisPaths.ContainsKey(session.Id);
            Process? localProcess=null;
            string localJobId="",localJobSession="",localJobKind="",localJobOut="";
            string pendingAutoGround=args.Contains("--auto-level") && Option("--live-url")==""?session.Id:"";
            Task<string>? localError=null;
            Dictionary<string,(string Path,JsonElement Ground,string Meta,string Points)> localGround=[];
            void SendLocal(string state,string message) => Send(new{type="localTask",state,message,sessionId=session.Id,jobSessionId=localJobSession,jobId=localJobId,
                enabled=localEnabled,hasAnalysis=analysisPaths.ContainsKey(session.Id),groundAvailable=localGround.ContainsKey(session.Id)});
            void SendGround()
            {
                if(localGround.TryGetValue(session.Id,out var item) && item.Meta==session.MetaSha && item.Points==session.PointsSha)
                    Send(new{type="ground",ground=item.Ground});
                else Send(new{type="ground",ground=new{available=false,reason="no_valid_session_ground"}});
            }
            void StartLocalJob(string kind)
            {
                if(localProcess is not null)throw new InvalidOperationException("已有本地任务正在运行");
                if(kind=="ground" && session.Frames.Length<4)throw new InvalidOperationException("自动配平需要至少4帧（1帧拟合+3帧独立留出）");
                if(kind=="analysis" && session.Frames.Length<=50)throw new InvalidOperationException("本地算法需要空场前缀后仍有可处理帧");
                localJobKind=kind;localJobSession=session.Id;localJobId=Guid.NewGuid().ToString("N");
                localJobOut=Path.Combine(root.FullName,"console_v2",".tools","local-analysis",localJobSession,localJobId);
                ProcessStartInfo task=new(Option("--python","python")){UseShellExecute=false,CreateNoWindow=true,RedirectStandardError=true,WorkingDirectory=root.FullName};
                foreach(string arg in new[]{"-B","-W","error",Path.Combine(root.FullName,"console_v2","app","local_replay_worker.py"),"--session",session.DirectoryPath,"--out",localJobOut,"--kind",localJobKind})task.ArgumentList.Add(arg);
                if(kind=="analysis")
                {
                    task.ArgumentList.Add("--empty-prefix-frames");task.ArgumentList.Add("50");
                    if(localGround.TryGetValue(session.Id,out var ground) && ground.Meta==session.MetaSha && ground.Points==session.PointsSha)
                    {task.ArgumentList.Add("--ground");task.ArgumentList.Add(ground.Path);}
                }
                localProcess=Process.Start(task)??throw new InvalidOperationException("无法启动本地任务");
                localError=localProcess.StandardError.ReadToEndAsync();
                SendLocal("running",kind=="ground"?"正在拟合并验证本会话地面":kind=="offline-preview"?"正在生成整段背景离线预览（非实时）":"正在本地分析全部帧，完成后自动载入");
                log.Add(new{eventType="localTaskStarted",jobId=localJobId,sessionId=localJobSession,kind=localJobKind});
            }
            double speed=1,anchorSource=session.Stamps[0];long anchor=Stopwatch.GetTimestamp(),submission=0,waitingSince=0;
            string previousLiveStatus="";
            string previousLiveGround="";
            string? fatal=null;
            Task<JsonElement>? jointRequest=null;
            (string Action,JsonElement? Options,long? Seq)? jointCurrent=null;
            Queue<(string Action,JsonElement? Options,long? Seq)> jointQueue=[];
            void Reanchor(){anchor=Stopwatch.GetTimestamp();anchorSource=session.Stamps[index];}
            Send(new{type="status",message="只读会话已校验；实时与联合录制需显式连接",playing});
            SendLocal("idle","可运行本地分析或拟合地面");
            try
            {
                while(!quit && !child.HasExited)
                {
                    if(localProcess is not null && localProcess.HasExited)
                    {
                        int code=localProcess.ExitCode;
                        string error=localError is null?"":await localError;
                        localProcess.Dispose();localProcess=null;localError=null;
                        try
                        {
                            if(code!=0)
                            {
                                string detail=error.Trim();
                                if(Directory.Exists(localJobOut))File.WriteAllText(Path.Combine(localJobOut,"launcher-error.log"),detail);
                                if(detail.Contains("INSUFFICIENT_CLEAN_ROI_SUPPORT",StringComparison.Ordinal))
                                    detail="地面拟合失败：可用地面区域的数量或空间分布不足";
                                else if(detail.Length>240)detail=detail[..240]+"…";
                                throw new InvalidOperationException(detail.Length>0?detail:"本地任务失败，详情见任务日志");
                            }
                            using JsonDocument result=JsonDocument.Parse(File.ReadAllBytes(Path.Combine(localJobOut,"RESULT.json")));
                            JsonElement item=result.RootElement;
                            if(item.GetProperty("sessionId").GetString()!=localJobSession || item.GetProperty("kind").GetString()!=localJobKind)
                                throw new InvalidDataException("本地任务结果会话不匹配");
                            string resultPath=item.GetProperty("path").GetString()??throw new InvalidDataException("缺少结果路径");
                            if(localJobKind=="analysis")
                            {
                                using SessionReader verified=new(Path.Combine(dataRoot,localJobSession),resultPath);
                                analysisPaths[localJobSession]=resultPath;
                                if(session.Id==localJobSession && live is null)
                                {
                                    SessionReader replacement=new(session.DirectoryPath,resultPath);
                                    session.Dispose();session=replacement;localEnabled=true;generation++;shown=-1;
                                }
                                Send(new{type="sessions",sessions=Sessions()});
                            }
                            else if(localJobKind=="offline-preview")
                            {
                                using SessionReader source=new(Path.Combine(dataRoot,localJobSession),null);
                                if(item.GetProperty("metaSha256").GetString()!=source.MetaSha || item.GetProperty("pointsSha256").GetString()!=source.PointsSha)
                                    throw new InvalidDataException("离线预览后源会话发生变化");
                                if(session.Id==localJobSession && live is null)Send(new{type="openOfflinePreview",path=resultPath});
                            }
                            else
                            {
                                using SessionReader source=new(Path.Combine(dataRoot,localJobSession),null);
                                if(item.GetProperty("metaSha256").GetString()!=source.MetaSha || item.GetProperty("pointsSha256").GetString()!=source.PointsSha)
                                    throw new InvalidDataException("地面拟合后源会话发生变化");
                                localGround[localJobSession]=(resultPath,item.GetProperty("ground").Clone(),source.MetaSha,source.PointsSha);
                                if(session.Id==localJobSession && live is null)SendGround();
                            }
                            bool sameSession=session.Id==localJobSession && live is null;
                            SendLocal("done",!sameSession?"本地任务已完成；切回原会话后可使用":localJobKind=="analysis"?"本地分析完成并已载入":localJobKind=="offline-preview"?"已生成整段背景离线预览；不代表实时识别或确认跌倒":"地面拟合完成；配平只改变显示，物理地面未验证");
                            log.Add(new{eventType="localTaskDone",jobId=localJobId,sessionId=localJobSession,kind=localJobKind,path=resultPath});
                        }
                        catch(Exception errorResult) when(errorResult is IOException or InvalidOperationException or JsonException or ArgumentException)
                        {SendLocal("failed","会话 "+localJobSession+"："+errorResult.Message);log.Add(new{eventType="localTaskFailed",jobId=localJobId,message=errorResult.Message});}
                    }
                    if(localProcess is null && live is null && pendingAutoGround==session.Id && pendingAutoGround!="")
                    {
                        pendingAutoGround="";
                        if(localGround.TryGetValue(session.Id,out var fitted) && fitted.Meta==session.MetaSha && fitted.Points==session.PointsSha)
                            SendGround();
                        else
                        {
                            try{StartLocalJob("ground");}
                            catch(Exception error) when(error is IOException or InvalidOperationException or System.ComponentModel.Win32Exception)
                            {SendLocal("failed","自动配平失败："+error.Message);}
                        }
                    }
                    // Network status calls never block cloud dispatch or copy acknowledgements.
                    if(jointRequest is {IsCompleted:true})
                    {
                        // 回声发起该次录制请求的 seq：轮询与真实 start/stop 的回包从此可区分。
                        long? jointSeq=jointCurrent?.Seq;
                        try
                        {
                            JsonElement status=await jointRequest;
                            Send(new{type="joint",status,previewUrl=joint!.PreviewUrl+"?t="+Stopwatch.GetTimestamp(),seq=jointSeq});
                            if(status.TryGetProperty("state",out JsonElement phase) && phase.GetString()=="completed")
                                Send(new{type="sessions",sessions=Sessions()});
                        }
                        catch(Exception error) when(error is IOException or HttpRequestException or TaskCanceledException)
                        {Send(new{type="error",message=error.Message,seq=jointSeq});log.Add(new{eventType="commandError",message=error.Message});}
                        jointCurrent=null;
                        jointRequest=null;
                    }
                    if(jointRequest is null && jointQueue.TryDequeue(out var request))
                    {
                        jointCurrent=request;
                        jointRequest=joint!.Request(request.Action,request.Options);
                    }
                    while(commands.Reader.TryRead(out JsonElement command))
                    {
                            string op=command.GetProperty("op").GetString()??"";
                            // 归因参数：seq 由界面分配，终止回包原样带回；poll 表示后台轮询（结果不结算界面提示）。
                            long? seq=command.TryGetProperty("seq",out JsonElement seqElement)
                                && seqElement.ValueKind==JsonValueKind.Number?seqElement.GetInt64():null;
                            bool poll=command.TryGetProperty("poll",out JsonElement pollElement)
                                && pollElement.ValueKind==JsonValueKind.True;
                            bool replied=false;
                            // 记原始文本：日志不持有与任何 JsonDocument 生命周期绑定的元素，报告序列化才不可能因元素释放而失败
                            log.Add(new{eventType="command",command=command.GetRawText()});
                        try
                        {
                            switch(op)
                            {
                                case "ack":
                                    if(!waiting || command.GetProperty("submissionId").GetInt64()!=submission)
                                        throw new InvalidDataException("Unexpected copy acknowledgement");
                                    waiting=false;break;
                                case "quit":quit=true;break;
                                case "play":if(live is null){playing=true;Reanchor();}break;
                                case "pause":playing=false;break;
                                case "seek":case "step":
                                    if(live is not null)throw new InvalidOperationException("Disconnect live before replay");
                                    index=Math.Clamp(op=="seek"?command.GetProperty("index").GetInt32():index+command.GetProperty("delta").GetInt32(),0,session.Frames.Length-1);
                                    playing=false;generation++;Reanchor();break;
                                case "speed":
                                    double next=command.GetProperty("speed").GetDouble();
                                    if(next is not (.25 or .5 or 1 or 2 or 4))throw new ArgumentException("Invalid playback speed");
                                    speed=next;Reanchor();break;
                                case "open":
                                    string sid=command.GetProperty("sessionId").GetString()??"";
                                    if(!Regex.IsMatch(sid,"^[A-Za-z0-9_-]{1,128}$"))throw new ArgumentException("Invalid session id");
                                    SessionReader opened=Open(Path.Combine(dataRoot,sid));
                                    live?.Dispose();live=null;session.Dispose();session=opened;localEnabled=analysisPaths.ContainsKey(session.Id);index=0;generation++;playing=false;Reanchor();ChangeVideoSession();SendGround();SendLocal(localProcess is null?"idle":"running",localProcess is null?"可运行本地分析或拟合地面":"会话 "+localJobSession+" 的本地任务正在运行");Send(new{type="sessions",sessions=Sessions()});if(args.Contains("--auto-level"))pendingAutoGround=session.Id;break;
                                case "localAnalysisToggle":
                                {
                                    if(live is not null)throw new InvalidOperationException("请先返回会话回放");
                                    if(localEnabled || analysisPaths.ContainsKey(session.Id))
                                    {
                                        bool enable=!localEnabled;
                                        SessionReader replacement=new(session.DirectoryPath,enable?analysisPaths[session.Id]:null);
                                        session.Dispose();session=replacement;localEnabled=enable;generation++;shown=-1;playing=false;
                                        SendLocal("idle",enable?"已启用已有本地分析":"已关闭本地分析");
                                        break;
                                    }
                                    if(!command.TryGetProperty("emptyPrefix",out JsonElement confirmed) || confirmed.ValueKind!=JsonValueKind.True)
                                        throw new ArgumentException("请先确认该会话前50帧确实为空场");
                                    goto case "localAnalysisRun";
                                }
                                case "localAnalysisRun":case "localGroundFit":case "localOfflinePreview":
                                {
                                    if(live is not null)throw new InvalidOperationException("请先返回会话回放");
                                    if(localProcess is not null)throw new InvalidOperationException("已有本地任务正在运行");
                                    if(op=="localAnalysisRun" && (!command.TryGetProperty("emptyPrefix",out JsonElement confirmed) || confirmed.ValueKind!=JsonValueKind.True))
                                        throw new ArgumentException("请先确认该会话前50帧确实为空场");
                                    StartLocalJob(op=="localGroundFit"?"ground":op=="localOfflinePreview"?"offline-preview":"analysis");break;
                                }
                                case "rename":
                                {
                                    string renameSid=command.GetProperty("sessionId").GetString()??"";
                                    if(!Regex.IsMatch(renameSid,"^[A-Za-z0-9_-]{1,128}$") || !File.Exists(Path.Combine(dataRoot,renameSid,"meta.json")))
                                        throw new ArgumentException("会话不存在");
                                    names.Set(renameSid,command.GetProperty("name").GetString()??"");
                                    Send(new{type="sessions",sessions=Sessions()});
                                    Send(new{type="notice",message="会话名称已保存",seq});
                                    break;
                                }
                                case "annotate":
                                {
                                    string annotationSid=command.GetProperty("sessionId").GetString()??"";
                                    if(!Regex.IsMatch(annotationSid,"^[A-Za-z0-9_-]{1,128}$") || !File.Exists(Path.Combine(dataRoot,annotationSid,"meta.json")))
                                        throw new ArgumentException("请选择本地会话");
                                    string url=await annotator.Open(annotationSid,command.TryGetProperty("frameIndex",out var frame)?frame.GetInt32():0);
                                    Send(new{type="openUrl",url,seq});
                                    log.Add(new{eventType="annotatorOpened",sessionId=annotationSid,url});
                                    break;
                                }
                                case "gtLoad":
                                case "gtSave":
                                {
                                    string gtSid=command.GetProperty("sessionId").GetString()??"";
                                    if(!Regex.IsMatch(gtSid,"^[A-Za-z0-9_.-]{1,128}$"))throw new ArgumentException("Invalid session id");
                                    if(gtSid!=session.Id)throw new InvalidOperationException("标注只能用于当前打开的会话");
                                    if(op=="gtLoad")
                                    {
                                        GtStore.Draft draft=gtStore.Load(gtSid);
                                        Send(new{type="gt",sessionId=gtSid,version=draft.Version,savedAt=draft.SavedAt,
                                            exists=draft.Exists,doc=draft.Exists?(object)draft.Doc:null,seq});
                                        log.Add(new{eventType="gtLoaded",sessionId=gtSid,version=draft.Version,exists=draft.Exists});
                                        break;
                                    }
                                    if(!command.TryGetProperty("doc",out JsonElement gtDoc) || gtDoc.ValueKind!=JsonValueKind.Object)
                                        throw new ArgumentException("缺少标注文档");
                                    int baseVersion=command.TryGetProperty("baseVersion",out JsonElement baseElement)
                                        && baseElement.ValueKind==JsonValueKind.Number?baseElement.GetInt32():0;
                                    int savedVersion=gtStore.Save(gtSid,baseVersion,gtDoc,session.Frames.Length);
                                    Send(new{type="gtSaved",sessionId=gtSid,version=savedVersion,seq});
                                    log.Add(new{eventType="gtSaved",sessionId=gtSid,baseVersion,version=savedVersion,
                                        persons=gtDoc.GetProperty("persons").GetArrayLength(),
                                        boxes=gtDoc.GetProperty("boxes").GetArrayLength(),
                                        intervals=gtDoc.TryGetProperty("intervals",out JsonElement savedIntervals)?savedIntervals.GetArrayLength():0});
                                    break;
                                }
                                case "videoEnabled":
                                    videoEnabled=live is null && command.GetProperty("enabled").GetBoolean();
                                    if(!videoEnabled){video!.Stop();Send(new{type="videoClear"});}
                                    break;
                                case "videoSelect":
                                    video!.Select(command.GetProperty("name").GetString()??"");SendVideoInfo();break;
                                case "videoOffset":
                                    video!.SetOffset(command.GetProperty("offsetMs").GetDouble()/1000);SendVideoInfo();break;
                                case "liveConnect":
                                    if(live is not null)throw new InvalidOperationException("Already connected");
                                    live=new(command.GetProperty("url").GetString()!,command.GetProperty("prefix").GetString()!,command.GetProperty("points").GetString()!);
                                    previousLiveStatus="";previousLiveGround="";videoEnabled=false;video!.Stop();SendVideoInfo(false);
                                    Send(new{type="status",message="连接实时源，等待同帧点云",clearTarget=true,groundBinding=(object?)null});
                                    log.Add(new{eventType="modeCleared",reason="liveConnect",clearTarget=true});
                                    playing=false;generation++;break;
                                case "liveDisconnect":live?.Dispose();live=null;generation++;shown=-1;SendVideoInfo();break;
                                case "deleteProbe":case "deleteConfirm":
                                {
                                    string targetSid=command.GetProperty("sessionId").GetString()??"";
                                    if(!Regex.IsMatch(targetSid,"^[A-Za-z0-9_-]{1,128}$"))throw new ArgumentException("Invalid session id");
                                    string dir=Path.Combine(dataRoot,targetSid);
                                    if(targetSid==Path.GetFileName(dataRoot.TrimEnd(Path.DirectorySeparatorChar))||Path.GetFullPath(dir)==Path.TrimEndingDirectorySeparator(Path.GetFullPath(dataRoot)))
                                        throw new ArgumentException("Invalid session id");
                                    (List<object> Files,long Total) Manifest()
                                    {
                                        if(!Directory.Exists(dir))throw new IOException("本地会话不存在: "+targetSid);
                                        List<object> files=[];
                                        long total=0;
                                        foreach(string path in Directory.EnumerateFiles(dir))
                                        {
                                            using FileStream content=new(path,FileMode.Open,FileAccess.Read,FileShare.Read);
                                            total+=content.Length;
                                            string sha=Convert.ToHexString(System.Security.Cryptography.SHA256.HashData(content)).ToLowerInvariant();
                                            files.Add(new{name=Path.GetFileName(path),bytes=content.Length,sha256=sha});
                                        }
                                        if(files.Count==0)throw new IOException("本地会话目录为空: "+targetSid);
                                        return (files,total);
                                    }
                                    if(op=="deleteProbe")
                                    {
                                        var (files,total)=Manifest();
                                        string manifestSha=FrameCodec.Sha(JsonSerializer.SerializeToUtf8Bytes(files));
                                        Send(new{type="deleteManifest",manifest=new{sessionId=targetSid,fileCount=files.Count,totalBytes=total,sha256=manifestSha,files},seq});
                                        log.Add(new{eventType="deleteProbe",sessionId=targetSid,fileCount=files.Count,totalBytes=total,sha256=manifestSha,files});
                                        break;
                                    }
                                    // deleteConfirm：重算清单并与用户确认过的摘要比对（防确认期间变化），先板端后本地。
                                    string echo=command.GetProperty("manifestSha").GetString()??"";
                                    var (confirmFiles,confirmTotal)=Manifest();
                                    if(FrameCodec.Sha(JsonSerializer.SerializeToUtf8Bytes(confirmFiles))!=echo)
                                        throw new IOException("会话内容在确认期间发生变化，已取消删除（请重新发起）");
                                    bool wantBoard=command.GetProperty("board").GetBoolean();
                                    string boardNote="";
                                    if(wantBoard)
                                    {
                                        string boardUrl=command.GetProperty("boardUrl").GetString()??throw new ArgumentException("Missing boardUrl");
                                        if(!Uri.TryCreate(boardUrl,UriKind.Absolute,out Uri? baseUri) || baseUri.Scheme!="http"
                                            || string.IsNullOrEmpty(baseUri.Host) || !string.IsNullOrEmpty(baseUri.UserInfo))
                                            throw new ArgumentException("板端地址必须是 http://主机:端口 形式");
                                        using HttpClient boardHttp=new() { Timeout=TimeSpan.FromSeconds(10) };
                                        using HttpResponseMessage response=await boardHttp.DeleteAsync(
                                            baseUri.AbsoluteUri.TrimEnd('/')+"/api/v1/sessions/"+Uri.EscapeDataString(targetSid));
                                        if(response.StatusCode==System.Net.HttpStatusCode.Conflict)
                                            throw new IOException("板端拒绝删除（录制中或状态机不允许）");
                                        if(response.StatusCode==System.Net.HttpStatusCode.NotFound)
                                            boardNote="；板端无此会话（可能已删除/未登记），本地照常删除";
                                        else if(!response.IsSuccessStatusCode)
                                            throw new IOException("板端删除失败 HTTP "+(int)response.StatusCode);
                                    }
                                    bool wasOpen=session.Id==targetSid;
                                    string? fallback=null;
                                    if(wasOpen)
                                    {
                                        fallback=Directory.EnumerateDirectories(dataRoot)
                                            .Where(p=>File.Exists(Path.Combine(p,"meta.json"))).Select(Path.GetFileName)
                                            .FirstOrDefault(name=>name!=targetSid);
                                        if(fallback is null)throw new IOException("不能删除最后一个本地会话");
                                    }
                                    for(string? p=dir;p is not null && p.StartsWith(Path.TrimEndingDirectorySeparator(Path.GetFullPath(dataRoot))+Path.DirectorySeparatorChar,StringComparison.OrdinalIgnoreCase);p=Path.GetDirectoryName(p))
                                        if((File.GetAttributes(p)&FileAttributes.ReparsePoint)!=0)throw new IOException("会话路径含目录链接，拒绝删除");
                                    if(wasOpen){video!.Stop();session.Dispose();}
                                    Directory.Delete(dir,true);
                                    sessionDeletes++;
                                    log.Add(new{eventType="sessionDeleted",sessionId=targetSid,board=wantBoard,note=boardNote,
                                        files=confirmFiles.Count,bytes=confirmTotal});
                                    if(wasOpen)
                                    {
                                        session=Open(Path.Combine(dataRoot,fallback!));
                                        index=0;generation++;playing=false;Reanchor();shown=-1;shownGeneration=-1;ChangeVideoSession();
                                    }
                                    Send(new{type="sessions",sessions=Sessions()});
                                    Send(new{type="status",message=$"已删除 {targetSid}（本地 {confirmTotal} 字节{boardNote}）",seq});
                                    replied=true;
                                    break;
                                }
                                case "jointStatus":case "jointStart":case "jointStop":case "jointPreview":
                                    if(joint is null)throw new InvalidOperationException("No local joint recorder configured (--joint-url)");
                                    string action=op=="jointStatus"?"status":op=="jointStart"?"start":op=="jointStop"?"stop":"preview-config";
                                    if(action is "start" or "stop")jointMutationRequests++;
                                    if(jointQueue.Count>=32)throw new InvalidOperationException("录制命令队列已满");
                                    // 轮询（poll）不带 seq：它的回包不参与归因，也不给队列添负担；用户手点的
                                    // 「刷新录制状态」一定有 seq，因此必须回一次，忙时也排队而不是静默丢弃。
                                    if(!poll || (jointRequest is null && jointQueue.Count==0))
                                        jointQueue.Enqueue((action,poll?null:(command.TryGetProperty("options",out JsonElement options)?options:null),poll?null:seq));
                                    break;
                                default:throw new ArgumentException("Unknown UI command");
                            }
                            if(!replied && op is not ("ack" or "rename" or "annotate" or "gtLoad" or "gtSave" or "jointStatus"
                                    or "jointStart" or "jointStop" or "jointPreview" or "videoEnabled" or "videoSelect" or "videoOffset") && !quit)
                                    Send(new{type="status",playing,speed,message=live is null?"会话回放":"实时订阅（不修改板端模式）",seq});
                        }
                        catch(Exception error) when(op!="ack" && (error is ArgumentException or IOException or InvalidOperationException or HttpRequestException or TaskCanceledException or JsonException or System.ComponentModel.Win32Exception))
                        {Send(new{type="error",message=error.Message,seq});log.Add(new{eventType="commandError",message=error.Message});}
                    }
                    if(commands.Reader.Completion.IsCompleted)break;
                    string videoError=video!.Error??"";
                    if(videoError!=reportedVideoError)
                    {
                        reportedVideoError=videoError;
                        if(videoError!="")Send(new{type="videoError",message=videoError});
                    }
                    double videoTime=Math.Clamp((playing?anchorSource+Stopwatch.GetElapsedTime(anchor).TotalSeconds*speed:session.Stamps[index])-session.Stamps[0],0,session.Stamps[^1]-session.Stamps[0]);
                    JsonElement? videoResponse=video!.Take();
                    if(videoEnabled && live is null && videoResponse is JsonElement vr
                        && vr.GetProperty("sessionId").GetString()==session.Id
                        && vr.GetProperty("generation").GetInt32()==generation
                        && vr.GetProperty("mediaVersion").GetInt32()==video.Version
                        && Math.Abs(vr.GetProperty("sourceTimeSec").GetDouble()-videoTime)<(playing?.25:1e-6))
                    {
                        Send(new{type="videoFrame",packet=vr});
                        log.Add(new{eventType="videoFrame",sessionId=session.Id,generation,mediaVersion=video.Version,
                            sourceFrameIndex=vr.GetProperty("sourceFrameIndex").GetInt32(),sourceTimeSec=vr.GetProperty("sourceTimeSec").GetDouble(),
                            jpegSha256=vr.GetProperty("jpegSha256").GetString(),info=vr.GetProperty("info").Clone()});
                    }
                    if(waiting)
                    {
                        // Status/TTL is independent of the shared-frame ACK. Do
                        // not consume or overwrite its slot while Qt owns it.
                        if(live is not null)
                        {
                            var pending=live.Take(consume:false);
                            var pendingStatus=pending.Status;
                            string pendingGround=JsonSerializer.Serialize(pending.Ground);
                            bool statusChanged=pendingStatus!=previousLiveStatus;
                            if(statusChanged || pendingGround!=previousLiveGround)
                            {
                                previousLiveStatus=pendingStatus;
                                previousLiveGround=pendingGround;
                                Send(new{type="liveStatus",message=pendingStatus,clearTarget=statusChanged && pendingStatus!="connected",groundBinding=pending.Ground});
                                log.Add(new{eventType="liveStatus",atMs=Stopwatch.GetElapsedTime(applicationStarted).TotalMilliseconds,
                                    message=pendingStatus,clearTarget=statusChanged && pendingStatus!="connected",groundBinding=pending.Ground});
                            }
                        }
                        // 界面卡住时不要用一条 IOException 把整次运行变成“原因不明”的退出：给足 30 s，
                        // 超时则显式记 ackTimeout 并让报告写清原因（本次运行仍然算失败）。
                        if(Stopwatch.GetElapsedTime(waitingSince).TotalSeconds>30)
                        {
                            double waitedMs=Math.Round(Stopwatch.GetElapsedTime(waitingSince).TotalMilliseconds);
                            log.Add(new{eventType="ackTimeout",submission,waitMs=waitedMs});
                            log.Add(new{eventType="failed",error=$"Copy acknowledgement timeout: GUI did not acknowledge submission {submission} within 30 s (waited {waitedMs} ms)"});
                            Send(new{type="error",message=$"界面在 30 s 内未确认帧拷贝（submission {submission}），本次运行判定失败"});
                            fatal="ackTimeout";
                            break;
                        }
                        await Task.Delay(2);continue;
                    }
                    byte[]? scene=null,target=null,intensity=null,depthPreview=null;object? info=null;
                    if(live is not null)
                    {
                        var sample=live.Take();
                        string sampleGround=JsonSerializer.Serialize(sample.Ground);
                        bool statusChanged=sample.Status!=previousLiveStatus;
                        if(statusChanged || sampleGround!=previousLiveGround)
                        {
                            previousLiveStatus=sample.Status;
                            previousLiveGround=sampleGround;
                            Send(new{type="liveStatus",message=sample.Status,clearTarget=statusChanged && sample.Status!="connected",groundBinding=sample.Ground});
                            log.Add(new{eventType="liveStatus",atMs=Stopwatch.GetElapsedTime(applicationStarted).TotalMilliseconds,
                                message=sample.Status,clearTarget=statusChanged && sample.Status!="connected",groundBinding=sample.Ground});
                        }
                        if(sample.Packet is not null){scene=sample.Packet.Scene;target=sample.Packet.Target;intensity=sample.Packet.Intensity;info=sample.Packet.Info;depthPreview=sample.Packet.DepthPreview;}
                    }
                    else
                    {
                        if(playing && index==shown && index<session.Frames.Length-1
                            && session.Stamps[index+1]<=anchorSource+Stopwatch.GetElapsedTime(anchor).TotalSeconds*speed)index++;
                        if(playing && index==session.Frames.Length-1){playing=false;Send(new{type="status",playing,speed,message="回放结束"});}
                        if(index!=shown || generation!=shownGeneration)
                        {
                            var frame=session.Read(index,generation,playing,speed);
                            scene=frame.Scene;target=frame.Target;intensity=frame.Intensity;info=frame.Info;shown=index;shownGeneration=generation;
                            depthPreview=session.DepthPreview;
                        }
                    }
                    if(scene is not null && target is not null)
                    {
                        if(scene.Length+target.Length+(intensity?.Length ?? 0)>capacity)throw new InvalidDataException("Frame exceeds shared capacity");
                        writer.WriteArray(0,scene,0,scene.Length);writer.WriteArray(scene.Length,target,0,target.Length);
                        if(intensity is not null)writer.WriteArray(scene.Length+target.Length,intensity,0,intensity.Length);
                        submission++;waiting=true;waitingSince=Stopwatch.GetTimestamp();
                        Send(new{type="frame",submissionId=submission,sceneBytes=scene.Length,targetBytes=target.Length,
                            intensityBytes=intensity?.Length ?? 0,info,depthPreview});
                        log.Add(new{eventType="published",submissionId=submission,atMs=Stopwatch.GetElapsedTime(applicationStarted).TotalMilliseconds,info});
                    }
                    // A preview that missed this frame's presentation may still refresh the
                    // displayed depth image; same submission only, never target/3D payload.
                    if(live is not null && submission>0 && live.TryTakeDepth(out LivePacket? lateDepth)
                        && lateDepth?.DepthPreview is not null)
                    {
                        Send(new{type="depth",submissionId=submission,depthPreview=lateDepth.DepthPreview,info=lateDepth.Info});
                        log.Add(new{eventType="depthUpdate",submissionId=submission,
                            atMs=Stopwatch.GetElapsedTime(applicationStarted).TotalMilliseconds});
                    }
                    if(videoEnabled && live is null)
                    {
                        double? bagTime=session.Frames[index].TryGetProperty("bag_time_sec",out JsonElement bag) && bag.ValueKind==JsonValueKind.Number
                            ?bag.GetDouble()+videoTime-(session.Stamps[index]-session.Stamps[0]):null;
                        video.Request(generation,index,videoTime,bagTime,playing);
                    }
                    await Task.Delay(5);
                }
                if(!child.HasExited)Send(new{type="close"});
            }
            finally
            {
                if(localProcess is not null) {if(!localProcess.HasExited)localProcess.Kill(true);localProcess.Dispose();}
                stop.Cancel();
                try{await reader;}catch(Exception error) when(error is OperationCanceledException or IOException){ }
            }
            if(!child.HasExited && !child.WaitForExit(5000))child.Kill(true);
            log.Add(new{eventType="nativeExit",exitCode=child.ExitCode});
            passed=child.ExitCode==0 && fatal is null;return passed?0:2;
        }
        catch(Exception error)
        {log.Add(new{eventType="failed",error=error.ToString()});Console.Error.WriteLine(error);return 2;}
        finally
        {
            live?.Dispose();video?.Dispose();session?.Dispose();
            if(child is not null){if(!child.HasExited)child.Kill(true);child.Dispose();}
            try
            {
                JsonSerializer.Serialize(report,new{status=passed?"PASS":"FAIL",directBoardCalls=0,jointMutationRequests,sessionDeletes,log},new JsonSerializerOptions{WriteIndented=true});
            }
            catch(Exception reportError)
            {
                // 报告必须落盘且不允许把进程带崩：序列化失败降级为最小错误报告，保留失败原因
                report.SetLength(0);report.Position=0;
                byte[] fallback=Encoding.UTF8.GetBytes("{\"status\":\"FAIL\",\"reportError\":"+JsonSerializer.Serialize(reportError.GetType().Name+": "+reportError.Message)+"}\n");
                report.Write(fallback,0,fallback.Length);
            }
        }
    }
}
