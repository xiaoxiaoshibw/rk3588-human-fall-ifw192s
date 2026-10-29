using System.Buffers.Binary;
using System.Net.WebSockets;
using System.Text;
using System.Text.Json;
using System.Diagnostics;

internal sealed record LivePacket(byte[] Scene, byte[] Target, byte[]? Intensity, object Info, byte[]? DepthPreview=null);
internal sealed record CloudFrame(string Key, uint Seq, double Stamp, byte[] RawXyz, byte[] Scene, string RawSha,
    long ReceivedAt, long Order=0, byte[]? Intensity=null);
internal sealed record MatchedLivePacket(LivePacket Packet, long SourceReceivedAt, double TtlS);

// A read-only Foxglove subscriber. Tracking is owned by the configured ROS node.
internal sealed class LiveSource : IDisposable
{
    private readonly ClientWebSocket socket = new();
    private readonly CancellationTokenSource cancel = new();
    private readonly Dictionary<string, CloudFrame> clouds = [];
    private readonly Dictionary<string, MatchedLivePacket> matches = [];
    private readonly Queue<string> order = [];
    private readonly HashSet<string> retired = [];
    private readonly object gate = new();
    private readonly string pointsTopic, stateTopic;
    private JsonElement? state;
    private JsonElement? groundBinding;
    private string? groundFrame;
    private long groundSourceOrder=-1;
    private long groundChangeAfterOrder=-1;
    private string? announcedGroundSha;
    private string? session;
    private long epoch = -1, selection = -1;
    private const double PreviewDelayS=.35;
    private long receivedAt;
    private long stateAt, cloudOrder, lastPresentedOrder=-1;
    private double stateTtlS=2, presentedTtlS=2;
    private long presentedSourceAt;
    private bool resultExpired;
    private string resultInvalidReason="recognition result expired: UNKNOWN";
    private long cloudCount, sequenceGaps, superseded, firstCloudAt;
    private string? presentedKey;
    private LivePacket? pendingDepth;
    private bool presentedDepth;
    private uint? previousSeq;
    private double? previousStamp;
    private double receiveHz, sourceHz;
    private string status = "connecting";
    private object? algorithmInput;
    private readonly Task task;
    internal LiveSource(string url, string prefix, string topic)
    {
        Uri uri = new(url);
        if (uri.Scheme is not ("ws" or "wss") || !string.IsNullOrEmpty(uri.UserInfo))
            throw new ArgumentException("Expected a Foxglove WebSocket URL without credentials");
        if (!prefix.StartsWith('/') || !prefix.EndsWith('/') || !topic.StartsWith('/'))
            throw new ArgumentException("Absolute ROS prefix/topic required");
        if(topic!="/innolidar_points") throw new ArgumentException("First native live adapter accepts the full /innolidar_points stream only");
        pointsTopic=topic; stateTopic=prefix+"state";
        socket.Options.AddSubProtocol("foxglove.websocket.v1");
        // Only public sensor data travels here; negotiate existing bridge compression.
        socket.Options.DangerousDeflateOptions = new WebSocketDeflateOptions();
        task = Task.Run(() => Receive(uri));
    }
    internal (LivePacket? Packet, string Status, JsonElement? Ground) Take(bool consume=true)
    {
        lock (gate)
        {
            bool stale = receivedAt == 0 || Stopwatch.GetElapsedTime(receivedAt).TotalSeconds > 2;
            bool stateStale = stateAt!=0 && Stopwatch.GetElapsedTime(stateAt).TotalSeconds>stateTtlS;
            CloudFrame? ready=null;
            foreach(CloudFrame cloud in consume ? clouds.Values : Enumerable.Empty<CloudFrame>())
                if(cloud.Order>lastPresentedOrder && Stopwatch.GetElapsedTime(cloud.ReceivedAt).TotalSeconds>=PreviewDelayS
                    && (ready is null || cloud.Order>ready.Order))ready=cloud;
            LivePacket? packet=null;
            if(!stale && ready is not null)
            {
                if(lastPresentedOrder>=0)superseded+=Math.Max(0,ready.Order-lastPresentedOrder-1);
                lastPresentedOrder=ready.Order;presentedKey=ready.Key;pendingDepth=null;
                presentedDepth=matches.TryGetValue(ready.Key,out MatchedLivePacket? presented)
                    && presented.Packet.DepthPreview is not null;
                if(matches.TryGetValue(ready.Key,out MatchedLivePacket? match)
                    && Stopwatch.GetElapsedTime(match.SourceReceivedAt).TotalSeconds<=match.TtlS)
                {
                    packet=match.Packet;presentedSourceAt=match.SourceReceivedAt;
                    presentedTtlS=match.TtlS;resultExpired=false;
                }
                else {matches.Remove(ready.Key);packet=Unmatched(ready);presentedSourceAt=0;}
            }
            if(presentedSourceAt!=0 && Stopwatch.GetElapsedTime(presentedSourceAt).TotalSeconds>presentedTtlS)
            {presentedSourceAt=0;resultExpired=true;resultInvalidReason="recognition result expired: UNKNOWN";}
            return (stale ? null : packet, stale && status == "connected" ? "stale: UNKNOWN"
                : stateStale && status=="connected" ? "recognition state stream stale: UNKNOWN"
                : resultExpired && status=="connected" ? resultInvalidReason : status,
                stateAt!=0 && !stateStale ? groundBinding : null);
        }
    }
    private async Task Receive(Uri uri)
    {
        try
        {
            await socket.ConnectAsync(uri, cancel.Token);
            lock(gate) status="connected";
            byte[] buffer = new byte[65536];
            Dictionary<int,int> subscribed=[];
            while (!cancel.IsCancellationRequested)
            {
                using MemoryStream message = new();
                WebSocketReceiveResult part;
                do
                {
                    part = await socket.ReceiveAsync(new ArraySegment<byte>(buffer), cancel.Token);
                    if (part.MessageType == WebSocketMessageType.Close) throw new IOException("Live connection closed");
                    message.Write(buffer,0,part.Count);
                    if (message.Length > 32*1024*1024) throw new InvalidDataException("Oversized Foxglove message");
                } while (!part.EndOfMessage);
                byte[] bytes=message.ToArray();
                if (part.MessageType == WebSocketMessageType.Text)
                {
                    using JsonDocument document=JsonDocument.Parse(bytes);
                    JsonElement msg=document.RootElement;
                    string? op=msg.GetProperty("op").GetString();
                    if (op=="advertise")
                    {
                        foreach(JsonElement ch in msg.GetProperty("channels").EnumerateArray())
                        {
                            string? topic=ch.GetProperty("topic").GetString();
                            int id=topic==pointsTopic ? 1 : topic==stateTopic ? 2 : 0;
                            if(id==0 || ch.GetProperty("encoding").GetString()!="ros1") continue;
                            string expected=id==1?"sensor_msgs/PointCloud2":"std_msgs/String";
                            if(ch.GetProperty("schemaName").GetString()!=expected) throw new InvalidDataException("Live channel schema mismatch");
                            int channelId=ch.GetProperty("id").GetInt32();
                            if(subscribed.TryGetValue(id,out int previous))
                            {
                                if(previous==channelId)continue;
                                byte[] unsubscribe=JsonSerializer.SerializeToUtf8Bytes(new{op="unsubscribe",subscriptionIds=new[]{id}});
                                await socket.SendAsync(new ArraySegment<byte>(unsubscribe),WebSocketMessageType.Text,true,cancel.Token);
                            }
                            subscribed[id]=channelId;
                            byte[] subscribe=JsonSerializer.SerializeToUtf8Bytes(new{op="subscribe",subscriptions=new[]{new{id,channelId=ch.GetProperty("id").GetInt32()}}});
                            await socket.SendAsync(new ArraySegment<byte>(subscribe),WebSocketMessageType.Text,true,cancel.Token);
                        }
                    }
                    if(op=="unadvertise" && msg.GetProperty("channelIds").EnumerateArray().Any(v=>subscribed.Values.Contains(v.GetInt32())))
                        throw new IOException("Selected live channel withdrawn; reconnect explicitly");
                }
                else if(bytes.Length >= 13 && bytes[0]==1)
                {
                    int id=BinaryPrimitives.ReadInt32LittleEndian(bytes.AsSpan(1,4));
                    byte[] payload=bytes[13..];
                    lock(gate)
                    {
                        if(id==1)
                        {
                            CloudFrame cloud=DecodeCloud(payload) with { Order=++cloudOrder };
                            if(!clouds.ContainsKey(cloud.Key)) order.Enqueue(cloud.Key);
                            clouds[cloud.Key]=cloud;
                            while(order.Count>8){string oldest=order.Dequeue();clouds.Remove(oldest);matches.Remove(oldest);}
                            cloudCount++;
                            if(firstCloudAt==0)firstCloudAt=cloud.ReceivedAt;
                            double elapsed=Stopwatch.GetElapsedTime(firstCloudAt).TotalSeconds;
                            receiveHz=elapsed>0?(cloudCount-1)/elapsed:0;
                            if(previousSeq is uint seq && previousStamp is double stamp && cloud.Seq>seq && cloud.Stamp>stamp)
                            {
                                sequenceGaps+=cloud.Seq-seq-1;
                                sourceHz=(cloud.Seq-seq)/(cloud.Stamp-stamp);
                            }
                            previousSeq=cloud.Seq;previousStamp=cloud.Stamp;
                            // Bound the wait independently of inference; present at source cadence.
                            receivedAt=cloud.ReceivedAt;
                        }
                        if(id==2)
                        {
                            if(payload.Length<4 || BinaryPrimitives.ReadUInt32LittleEndian(payload)!=payload.Length-4)
                                throw new InvalidDataException("Invalid ROS String");
                            using JsonDocument document=JsonDocument.Parse(payload.AsMemory(4));
                            JsonElement s=document.RootElement;
                            if(s.GetProperty("schema_version").GetInt32()!=1 || s.GetProperty("kind").GetString()!="target_state")
                                throw new InvalidDataException("Invalid target state schema");
                            string next=s.GetProperty("session_id").GetString() ?? throw new InvalidDataException("Missing live session");
                            long e=s.GetProperty("time_epoch").GetInt64();
                            long v=s.TryGetProperty("selection_version",out JsonElement sv) && sv.ValueKind==JsonValueKind.Number?sv.GetInt64():0;
                            if(string.IsNullOrWhiteSpace(next) || e<0 || v<0)throw new InvalidDataException("Invalid live identity");
                            if(retired.Contains(next) || (session==next && (e<epoch || (e==epoch && v<selection)))) continue;
                            if(session is not null && (session!=next || epoch!=e || selection!=v))
                            {state=null;matches.Clear();presentedSourceAt=0;resultExpired=true;
                             resultInvalidReason="recognition identity changed: UNKNOWN";}
                            if(session!=next)
                            {
                                groundBinding=null;groundFrame=null;groundSourceOrder=-1;groundChangeAfterOrder=-1;announcedGroundSha=null;
                                if(session is not null) retired.Add(session);
                                if(retired.Count>128) throw new InvalidDataException("Live session capacity reached; reconnect explicitly");
                            }
                            session=next; epoch=e; selection=v; stateAt=Stopwatch.GetTimestamp();
                            string inputReason=s.TryGetProperty("acquisition",out JsonElement acq)
                                && acq.TryGetProperty("reason",out JsonElement ar)?ar.GetString()??"unknown":"unknown";
                            double? cloudAge=null;
                            if(s.TryGetProperty("sensor_quality",out JsonElement quality)
                                && quality.TryGetProperty("cloud",out JsonElement cq)
                                && cq.TryGetProperty("age_s",out JsonElement age) && age.ValueKind==JsonValueKind.Number)
                                cloudAge=age.GetDouble();
                            bool hasSource=s.TryGetProperty("source",out JsonElement header) && header.ValueKind==JsonValueKind.Object;
                            JsonElement? service=s.TryGetProperty("service",out JsonElement si)?si.Clone():null;
                            bool independentGround=false;
                            stateTtlS=2; // Legacy protocol retains its existing freshness contract.
                            if(service is JsonElement descriptor)
                            {
                                if(descriptor.GetProperty("protocol").GetString()!="range_recognition/1"
                                    || descriptor.GetProperty("version").GetInt32()!=1
                                    || descriptor.GetProperty("confirmedEnabled").GetBoolean())
                                    throw new InvalidDataException("Unsupported recognition service protocol");
                                if(descriptor.GetProperty("instanceId").GetString()!=next)
                                    throw new InvalidDataException("Recognition service instance mismatch");
                                string[] mandatory=["source_wire_sha256","source_rows","range_runtime","height","ground_alert_v1","heartbeat"];
                                HashSet<string?> capabilities=descriptor.GetProperty("capabilities").EnumerateArray().Select(c=>c.GetString()).ToHashSet();
                                independentGround=capabilities.Contains("independent_ground_binding");
                                if(mandatory.Any(c=>!capabilities.Contains(c)))
                                    throw new InvalidDataException("Recognition service missing required capabilities");
                                int ttl=descriptor.GetProperty("ttlMs").GetInt32();
                                if(ttl<=0 || ttl>500)throw new InvalidDataException("Invalid recognition service TTL");
                                stateTtlS=ttl/1000.0;
                            }
                            bool groundSourceFresh=false;
                            long previousGroundOrder=groundSourceOrder;
                            if(hasSource)
                            {
                                string frame=header.GetProperty("frame_id").GetString()??"";
                                string groundKey=Key(header.GetProperty("seq").GetUInt32(),header.GetProperty("stamp_secs").GetUInt32(),
                                    header.GetProperty("stamp_nsecs").GetUInt32(),frame);
                                if(clouds.TryGetValue(groundKey,out CloudFrame? groundCloud)
                                    && Stopwatch.GetElapsedTime(groundCloud.ReceivedAt).TotalSeconds<=stateTtlS
                                    && groundCloud.Order>=groundSourceOrder)
                                {groundFrame=frame;groundSourceOrder=groundCloud.Order;groundSourceFresh=true;}
                            }
                            JsonElement? previousGround=groundBinding;
                            groundBinding=null;
                            if(independentGround && s.TryGetProperty("groundBinding",out JsonElement gb)
                                && gb.ValueKind==JsonValueKind.Object && groundFrame is not null)
                            {
                                ValidateGround(gb,next,groundFrame);
                                if(gb.GetProperty("supportCurrent").GetBoolean() && !hasSource)
                                    throw new InvalidDataException("Live ground support is not current without source");
                                string? incomingSha=gb.GetProperty("sha256").GetString();
                                if(announcedGroundSha is not null && announcedGroundSha!=incomingSha)
                                    groundChangeAfterOrder=previousGroundOrder;
                                announcedGroundSha=incomingSha;
                                if(previousGround is JsonElement previous
                                    && previous.GetProperty("sha256").GetString()==gb.GetProperty("sha256").GetString())
                                {
                                    JsonElement a=previous.GetProperty("displayPlane"),b=gb.GetProperty("displayPlane");
                                    if(a.GetProperty("offsetM").GetDouble()!=b.GetProperty("offsetM").GetDouble()
                                        || !a.GetProperty("normal").EnumerateArray().Select(x=>x.GetDouble())
                                            .SequenceEqual(b.GetProperty("normal").EnumerateArray().Select(x=>x.GetDouble())))
                                        throw new InvalidDataException("Live ground display binding changed without SHA change");
                                }
                                // A new plane must first arrive with a source frame;
                                // a heartbeat cannot install a changed binding.
                                if((groundSourceFresh && groundSourceOrder>groundChangeAfterOrder) || (previousGround is JsonElement prior
                                    && prior.GetProperty("sha256").GetString()==gb.GetProperty("sha256").GetString()))
                                    groundBinding=gb.Clone();
                            }
                            algorithmInput=new{status=hasSource?"source_bound":"invalid",reason=inputReason,cloudAgeSec=cloudAge,
                                service,capabilityStatus=service is null?"legacy_protocol_new_capabilities_unavailable":"advertised"};
                            if(!s.TryGetProperty("source",out JsonElement src) || src.ValueKind!=JsonValueKind.Object)
                            {
                                state=null;matches.Clear();presentedSourceAt=0;resultExpired=false;
                                status="算法输入失效："+inputReason;continue;
                            }
                            status="connected";state=s.Clone();
                        }
                        TryMatch();
                    }
                }
            }
        }
        catch(Exception error) when(error is not OutOfMemoryException)
        {
            lock(gate) { status=error.Message+": UNKNOWN"; clouds.Clear();matches.Clear();order.Clear();state=null;groundBinding=null; }
        }
    }
    private static void ValidateGround(JsonElement gs,string sessionId,string frameId)
    {
        JsonElement plane=gs.GetProperty("displayPlane");
        string? sha=gs.GetProperty("sha256").GetString();
        if(sha is null || sha.Length!=64 || sha.Any(c=>!Uri.IsHexDigit(c))
            || plane.GetProperty("scope").GetString()!="bound_display_only"
            || plane.GetProperty("sessionId").GetString()!=sessionId
            || plane.GetProperty("groundSha256").GetString()!=sha
            || plane.GetProperty("frameId").GetString()!=frameId)
            throw new InvalidDataException("Live ground display binding mismatch");
        double[] normal=plane.GetProperty("normal").EnumerateArray().Select(v=>v.GetDouble()).ToArray();
        double offset=plane.GetProperty("offsetM").GetDouble();
        if(normal.Length!=3 || normal.Any(v=>!double.IsFinite(v)) || !double.IsFinite(offset)
            || offset<=0 || normal[2]<=0 || Math.Abs(normal.Sum(v=>v*v)-1)>1e-5)
            throw new InvalidDataException("Invalid live ground display plane");
        _=gs.GetProperty("available").GetBoolean();
    }
    private static string Key(uint seq,uint secs,uint nsecs,string frame) => $"{seq}/{secs}/{nsecs}/{frame}";
    private object Metrics() => new{received=cloudCount,receiveHz,sourceHz,sequenceGaps,superseded,previewDelayMs=PreviewDelayS*1000,
        stateStreamAgeMs=stateAt==0?(double?)null:Stopwatch.GetElapsedTime(stateAt).TotalMilliseconds};
    private LivePacket Unmatched(CloudFrame c) => new(c.Scene,[],c.Intensity,new{mode="live",sessionId=session??"UNKNOWN",
        frameIndex=c.Seq,frameCount=0,stampSec=c.Stamp,playing=false,speed=1,sceneCount=c.Scene.Length/12,
        targetCount=0,rawSha256=c.RawSha,xyzSha256=FrameCodec.Sha(c.Scene),
        targetSha256=FrameCodec.Sha([]),intensitySha256=FrameCodec.Sha(c.Intensity??[]),
        intensityAvailable=c.Intensity is not null && c.Intensity.Length>0,
        result=(object?)null,algorithmInput,confirmedEnabled=false,stream=Metrics()});
    private void TryMatch()
    {
        if(state is not JsonElement s) return;
        JsonElement source=s.GetProperty("source");
        string key=Key(source.GetProperty("seq").GetUInt32(), source.GetProperty("stamp_secs").GetUInt32(),
            source.GetProperty("stamp_nsecs").GetUInt32(),source.GetProperty("frame_id").GetString() ?? "");
        if(!clouds.TryGetValue(key,out CloudFrame? cloud)
            || Stopwatch.GetElapsedTime(cloud.ReceivedAt).TotalSeconds>stateTtlS
            || Stopwatch.GetElapsedTime(stateAt).TotalSeconds>stateTtlS) return;
        bool measured=s.GetProperty("bbox_observed").GetBoolean() && !s.GetProperty("position_predicted").GetBoolean()
            && s.GetProperty("track_status").GetString()=="locked" && s.GetProperty("observability").GetString()!="invalid";
        int[] rows=measured?s.GetProperty("target_source_rows").EnumerateArray().Select(v=>v.GetInt32()).ToArray():[];
        if(rows.Distinct().Count()!=rows.Length || rows.Any(i=>i<0 || i>=cloud.RawXyz.Length/12))
            throw new InvalidDataException("Live source rows outside matched cloud");
        byte[] target=new byte[rows.Length*12];
        for(int i=0;i<rows.Length;i++)
        {
            cloud.RawXyz.AsSpan(rows[i]*12,12).CopyTo(target.AsSpan(i*12));
            for(int c=0;c<3;c++)
                if(!float.IsFinite(BinaryPrimitives.ReadSingleLittleEndian(target.AsSpan(i*12+c*4,4))))
                    throw new InvalidDataException("Invalid live target measurement");
        }
        string mode=s.GetProperty("target_mode").GetString() ?? "UNKNOWN";
        string fall=s.TryGetProperty("fall_status",out JsonElement f)? f.GetString() ?? "unknown" : "unknown";
        // Existing board algorithms are unverified; this viewer does not promote confirmation.
        if(fall=="confirmed") throw new InvalidDataException("Unexpected confirmed state; unverified mode");
        object? box=null;
        if(rows.Length>0)
        {
            double[] lo=[double.PositiveInfinity,double.PositiveInfinity,double.PositiveInfinity];
            double[] hi=[double.NegativeInfinity,double.NegativeInfinity,double.NegativeInfinity];
            for(int i=0;i<rows.Length;i++)for(int c=0;c<3;c++)
            {
                double v=BinaryPrimitives.ReadSingleLittleEndian(target.AsSpan(i*12+c*4,4));
                lo[c]=Math.Min(lo[c],v);hi[c]=Math.Max(hi[c],v);
            }
            box=new{x=(lo[0]+hi[0])/2,y=(lo[1]+hi[1])/2,w=hi[0]-lo[0],h=hi[1]-lo[1],zMin=lo[2],zMax=hi[2]};
        }
        byte[]? preview=null;object? depth=null;object? body=null;
        JsonElement? groundAlert=null,demoFallCandidate=null,posture=null,skeleton=null,fallEvidence=null,groundStatus=null;
        double? height=null;
        JsonElement? serviceInfo=s.TryGetProperty("service",out JsonElement serviceDescriptor)?serviceDescriptor.Clone():null;
        string reason="旧协议：新版高度/地面能力未声明 · "+mode;
        if(serviceInfo is JsonElement svc)
        {
            if(svc.GetProperty("protocol").GetString()!="range_recognition/1" || svc.GetProperty("version").GetInt32()!=1
                || svc.GetProperty("confirmedEnabled").GetBoolean())throw new InvalidDataException("Unsupported recognition service protocol");
            reason="板端识别服务 · "+svc.GetProperty("releaseId").GetString();
            string[] required=["source_wire_sha256","source_rows","range_runtime","height","ground_alert_v1","heartbeat"];
            HashSet<string?> advertised=svc.GetProperty("capabilities").EnumerateArray().Select(v=>v.GetString()).ToHashSet();
            string[] missing=required.Where(v=>!advertised.Contains(v)).ToArray();
            if(missing.Length>0)reason+=" · 缺能力："+string.Join(", ",missing);
            if(svc.TryGetProperty("initialization",out JsonElement initialization)
                && initialization.TryGetProperty("ground",out JsonElement groundInitialization))
                reason+=" · 地面初始化："+groundInitialization.GetString();
        }
        if(s.TryGetProperty("local_range",out JsonElement local))
        {
            if(local.GetProperty("version").GetInt32()!=1 || local.GetProperty("wireSha256").GetString()!=cloud.RawSha)
                throw new InvalidDataException("Local range/source SHA mismatch");
            string encoded=local.TryGetProperty("preview",out JsonElement previewValue)
                && previewValue.ValueKind==JsonValueKind.String?previewValue.GetString()??"":"";
            if(encoded.Length>360000)throw new InvalidDataException("Oversized live depth preview");
            JsonElement descriptor=local.GetProperty("depth"),metadata=descriptor.GetProperty("metadata");
            if(metadata.GetProperty("version").GetInt32()!=2 || metadata.GetProperty("width").GetInt32()!=256
                || metadata.GetProperty("height").GetInt32()!=192 || metadata.GetProperty("nativeTransform").GetString()!="rotate180"
                || metadata.GetProperty("orientation").GetString()!="native_grid_rotated_180_for_view"
                || metadata.GetProperty("quantity").GetString()!="radial_range" || metadata.GetProperty("units").GetString()!="m"
                || metadata.GetProperty("targetPixels").GetInt32()!=rows.Length)
                throw new InvalidDataException("Local live depth contract mismatch");
            if(encoded.Length>0)
            {
                preview=Convert.FromBase64String(encoded);
                if(preview.Length>262144 || FrameCodec.Sha(preview)!=descriptor.GetProperty("previewSha256").GetString())
                    throw new InvalidDataException("Local live preview SHA mismatch");
                depth=new{metadata=metadata.Clone(),previewSha256=FrameCodec.Sha(preview),exportUrl=""};
            }
            JsonElement h=local.GetProperty("heightMedianM");
            if(h.ValueKind==JsonValueKind.Number)
            {height=h.GetDouble();if(!double.IsFinite(height.Value)||rows.Length==0)throw new InvalidDataException("Invalid live height");}
            JsonElement alert=local.GetProperty("groundAlert");
            if(alert.GetProperty("variant").GetString()!="ground_alert_v1" || alert.GetProperty("semantic").GetString()!="UNKNOWN"
                || alert.GetProperty("confirmedEnabled").GetBoolean() || (alert.GetProperty("active").GetBoolean() && (rows.Length==0 || height is null)))
                throw new InvalidDataException("Invalid live low posture hint");
            groundAlert=alert.Clone();
            if(local.TryGetProperty("demoFallCandidate",out JsonElement demo) && demo.ValueKind==JsonValueKind.Object)
            {
                int level=demo.GetProperty("level").GetInt32();
                if(demo.GetProperty("variant").GetString()!="horizontal_low_posture_v1"
                    || demo.GetProperty("semantic").GetString()!="UNKNOWN" || demo.GetProperty("confirmedEnabled").GetBoolean()
                    || level<0 || level>2 || demo.GetProperty("active").GetBoolean()!=(level>0)
                    || (level>0 && (rows.Length==0 || height is null)))
                    throw new InvalidDataException("Invalid horizontal low posture hint");
                demoFallCandidate=demo.Clone();
            }
            JsonElement pose=local.GetProperty("skeleton");
            SessionReader.ValidateSkeleton(pose,rows,cloud.RawXyz,12);skeleton=pose.Clone();
            JsonElement p=local.GetProperty("posture");
            if(p.ValueKind==JsonValueKind.Object)
            {
                if(p.GetProperty("humanSemantic").GetString()!="UNKNOWN" || p.GetProperty("fallEvent").GetBoolean())
                    throw new InvalidDataException("Invalid live posture semantics");
                posture=p.Clone();
            }
            JsonElement candidates=local.GetProperty("bodyCandidates");
            if(candidates.ValueKind==JsonValueKind.Object)
            {
                if(candidates.GetProperty("method").GetString()!="range_topology_branches_v2"
                    || candidates.GetProperty("semantic").GetString()!="UNKNOWN")throw new InvalidDataException("Invalid live body semantics");
                HashSet<int> allowed=rows.ToHashSet(),used=[];var parts=new List<object>();
                foreach(JsonElement part in candidates.GetProperty("parts").EnumerateArray())
                {
                    int[] support=part.GetProperty("sourceRows").EnumerateArray().Select(v=>v.GetInt32()).ToArray();
                    if(support.Any(i=>!allowed.Contains(i)||!used.Add(i)))throw new InvalidDataException("Live body/target source mismatch");
                    parts.Add(new{part=part.GetProperty("part").GetString(),pointCount=support.Length});
                }
                body=new{parts};
            }
            reason=(serviceInfo is null?"本机2D/3D":reason)
                +"："+s.GetProperty("acquisition").GetProperty("reason").GetString();
            if(preview is null)reason+=" · 预览未到达（主链独立）";
            if(local.TryGetProperty("ground",out JsonElement gs) && gs.ValueKind==JsonValueKind.Object)
            {
                if(height is not null && !gs.GetProperty("available").GetBoolean())
                    throw new InvalidDataException("Height present with unavailable ground");
                if(gs.TryGetProperty("displayPlane",out JsonElement plane))
                {
                    bool frozenDisplay=plane.TryGetProperty("scope",out JsonElement scope)
                        && scope.GetString()=="bound_display_only";
                    if((!gs.GetProperty("available").GetBoolean() && !frozenDisplay) || plane.GetProperty("sessionId").GetString()!=session
                        || plane.GetProperty("groundSha256").GetString()!=gs.GetProperty("sha256").GetString()
                        || plane.GetProperty("frameId").GetString()!=source.GetProperty("frame_id").GetString())
                        throw new InvalidDataException("Live ground display binding mismatch");
                    double[] normal=plane.GetProperty("normal").EnumerateArray().Select(v=>v.GetDouble()).ToArray();
                    double offset=plane.GetProperty("offsetM").GetDouble();
                    if(normal.Length!=3 || normal.Any(v=>!double.IsFinite(v)) || !double.IsFinite(offset)
                        || offset<=0 || normal[2]<=0 || Math.Abs(normal.Sum(v=>v*v)-1)>1e-5)
                        throw new InvalidDataException("Invalid live ground display plane");
                }
                groundStatus=gs.Clone();reason+=" · 地面："+gs.GetProperty("reason").GetString();
            }
            if(local.TryGetProperty("fallEvidence",out JsonElement fe) && fe.ValueKind==JsonValueKind.Object)
            {
                if(fe.GetProperty("confirmed_enabled").GetBoolean() || fe.GetProperty("state").GetString()!=fall)
                    throw new InvalidDataException("Invalid live fall evidence");
                fallEvidence=fe.Clone();reason+=" · "+string.Join(" / ",fe.GetProperty("reason_codes").EnumerateArray().Select(v=>v.GetString()));
            }
        }
        LivePacket packet=new(cloud.Scene,target,cloud.Intensity,new{mode="live",sessionId=session,frameIndex=cloud.Seq,frameCount=0,
            stampSec=cloud.Stamp,playing=false,speed=1,sceneCount=cloud.Scene.Length/12,targetCount=rows.Length,
            rawSha256=cloud.RawSha,xyzSha256=FrameCodec.Sha(cloud.Scene),targetSha256=FrameCodec.Sha(target),
            intensitySha256=FrameCodec.Sha(cloud.Intensity??[]),
            intensityAvailable=cloud.Intensity is not null && cloud.Intensity.Length>0,
            result=new{state=rows.Length>0?fall:"unknown",trackId=rows.Length>0?s.GetProperty("track_id").ToString():null,
                measured=rows.Length>0,box,heightMedianM=height,groundAlert,demoFallCandidate,groundStatus,fallEvidence,posture,skeleton,bodyCandidates=body,
                service=serviceInfo,reasons=new[]{reason,"human/fall GT UNKNOWN"},targetReason=s.GetProperty("track_status").GetString()},
            depth,targetMode=mode,algorithmInput,confirmedEnabled=false,stream=Metrics()},preview);
        if(cloud.Order<=lastPresentedOrder)
        {
            // Same frame is already on screen: a preview that missed the presentation
            // can still refresh just the depth image, but never the target/3D payload.
            if(!presentedDepth && cloud.Key==presentedKey && preview is not null)
            {pendingDepth=packet;presentedDepth=true;}
            state=null;
            return;
        }
        matches[cloud.Key]=new(packet,cloud.ReceivedAt,stateTtlS);
        state=null; // never reapply old state to later cloud arrivals
    }
    internal bool TryTakeDepth(out LivePacket? packet)
    {
        lock(gate)
        {
            packet=pendingDepth;pendingDepth=null;
            if(packet is null) return false;
            if(presentedSourceAt==0 || Stopwatch.GetElapsedTime(presentedSourceAt).TotalSeconds>presentedTtlS) return false;
            return true;
        }
    }
    internal static CloudFrame DecodeCloud(byte[] payload)
    {
        using BinaryReader reader=new(new MemoryStream(payload),Encoding.UTF8);
        uint seq=reader.ReadUInt32(),secs=reader.ReadUInt32(),nsecs=reader.ReadUInt32();
        string Text(){uint n=reader.ReadUInt32();if(n>4096 || n>reader.BaseStream.Length-reader.BaseStream.Position)throw new InvalidDataException("ROS string length");return Encoding.UTF8.GetString(reader.ReadBytes((int)n));}
        string frame=Text();
        uint height=reader.ReadUInt32(),width=reader.ReadUInt32(),fields=reader.ReadUInt32();
        if(height==0 || width==0 || (ulong)height*width>500_000 || fields>128 || nsecs>=1_000_000_000) throw new InvalidDataException("ROS cloud dimensions");
        Dictionary<string,(uint Offset,byte Type,uint Count)> layout=[];
        for(uint i=0;i<fields;i++){string name=Text();layout[name]=(reader.ReadUInt32(),reader.ReadByte(),reader.ReadUInt32());}
        bool big=reader.ReadBoolean(); uint step=reader.ReadUInt32(),rowStep=reader.ReadUInt32(),length=reader.ReadUInt32();
        if(step<12 || rowStep<(ulong)width*step || (ulong)rowStep*height!=length || length>28_000_000
            || length>reader.BaseStream.Length-reader.BaseStream.Position-1)throw new InvalidDataException("ROS cloud layout");
        byte[] raw=reader.ReadBytes((int)length); reader.ReadBoolean();
        if(reader.BaseStream.Position!=reader.BaseStream.Length)throw new InvalidDataException("Trailing ROS cloud bytes");
        var axes=new[]{"x","y","z"}.Select(name=>layout.TryGetValue(name,out var field) && field.Type==7 && field.Count==1 && field.Offset<=step-4
            ?field.Offset:throw new InvalidDataException("ROS XYZ must be scalar float32")).ToArray();
        // intensity 可选：驱动正常发布 float32 "intensity"；缺失时反射着色不可用（不视为错误）。
        bool hasIntensity=layout.TryGetValue("intensity",out var iField) && iField.Type==7 && iField.Count==1 && iField.Offset<=step-4;
        int iOffset=hasIntensity?checked((int)iField.Offset):-1;
        byte[] xyz=new byte[checked((int)(width*height)*12)]; using MemoryStream scene=new();
        byte[]? intensity=hasIntensity?new byte[xyz.Length/12*4]:null;
        int index=0,kept=0;
        for(uint r=0;r<height;r++)for(uint c=0;c<width;c++,index++)
        {
            bool finite=true;
            for(int a=0;a<3;a++)
            {
                ReadOnlySpan<byte> data=raw.AsSpan(checked((int)(r*rowStep+c*step+axes[a])),4);
                float value=big?BinaryPrimitives.ReadSingleBigEndian(data):BinaryPrimitives.ReadSingleLittleEndian(data);
                BinaryPrimitives.WriteSingleLittleEndian(xyz.AsSpan(index*12+a*4,4),value); finite &=float.IsFinite(value);
            }
            if(finite)
            {
                scene.Write(xyz,index*12,12);
                if(intensity is not null)
                {
                    ReadOnlySpan<byte> data=raw.AsSpan(checked((int)(r*rowStep+c*step+iOffset)),4);
                    float value=big?BinaryPrimitives.ReadSingleBigEndian(data):BinaryPrimitives.ReadSingleLittleEndian(data);
                    BinaryPrimitives.WriteSingleLittleEndian(intensity.AsSpan(kept++*4,4),value);
                }
            }
        }
        if(intensity is not null)Array.Resize(ref intensity,kept*4);
        if(string.IsNullOrWhiteSpace(frame))throw new InvalidDataException("Missing source frame id");
        return new(Key(seq,secs,nsecs,frame),seq,secs+nsecs/1e9,xyz,scene.ToArray(),FrameCodec.Sha(payload),Stopwatch.GetTimestamp(),
            0,intensity);
    }
    public void Dispose()
    {
        cancel.Cancel(); socket.Abort();
        try { task.GetAwaiter().GetResult(); } catch(OperationCanceledException) { }
        socket.Dispose(); cancel.Dispose();
    }
}
