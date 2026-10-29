using System.Buffers.Binary;
using System.Text.Json;
using System.Text.Encodings.Web;

internal sealed class SessionReader : IDisposable
{
    private readonly FileStream points;
    private readonly JsonDocument meta;
    private readonly JsonDocument? analysis;
    private readonly Dictionary<int, JsonElement> results = [];
    private readonly string? artifactRoot;
    internal byte[]? DepthPreview { get; private set; }
    internal string Id { get; }
    internal string DirectoryPath { get; }
    internal JsonElement[] Frames { get; }
    internal double[] Stamps { get; }
    internal int MaxPoints { get; }
    internal string MetaSha { get; }
    internal string PointsSha { get; }
    internal string AnalysisSha { get; } = "unavailable";
    internal object AnalysisIntervals => analysis is null ? Array.Empty<object>()
        : analysis.RootElement.GetProperty("intervals").Clone();

    internal SessionReader(string directory, string? resultPath)
    {
        directory = Path.GetFullPath(directory);
        DirectoryPath = directory;
        Id = Path.GetFileName(directory);
        byte[] metaBytes = File.ReadAllBytes(Path.Combine(directory, "meta.json"));
        MetaSha = FrameCodec.Sha(metaBytes);
        meta = JsonDocument.Parse(metaBytes);
        JsonElement m = meta.RootElement;
        if (m.GetProperty("point_layout").GetProperty("stride_bytes").GetInt32() != 28
            || m.GetProperty("point_file").GetString() != "points.bin")
            throw new InvalidDataException("Only declared points.bin stride 28 is supported");
        points = new FileStream(Path.Combine(directory, "points.bin"), FileMode.Open, FileAccess.Read, FileShare.Read);
        try
        {
            PointsSha = Convert.ToHexString(System.Security.Cryptography.SHA256.HashData(points)).ToLowerInvariant();
            Frames = m.GetProperty("frames").EnumerateArray().ToArray();
            if (Frames.Length == 0) throw new InvalidDataException("Empty session");
            Stamps = new double[Frames.Length];
            long covered = 0;
            for (int i = 0; i < Frames.Length; i++)
            {
                JsonElement f = Frames[i];
                long offset = f.GetProperty("offset_points").GetInt64();
                int count = f.GetProperty("count_points").GetInt32();
                if (count < 0 || count > 500_000 || offset != covered)
                    throw new InvalidDataException("Invalid frame layout/count");
                covered = checked(covered + count);
                Stamps[i] = f.GetProperty("stamp_sec").GetDouble() + f.GetProperty("stamp_nanosec").GetDouble() / 1e9;
                if (!double.IsFinite(Stamps[i]) || (i > 0 && Stamps[i] <= Stamps[i-1]))
                    throw new InvalidDataException("Non-monotonic source time");
                MaxPoints = Math.Max(MaxPoints, count);
            }
            if (checked(covered * 28) != points.Length) throw new InvalidDataException("Point file length mismatch");
            if (resultPath is not null)
            {
                artifactRoot = Path.GetDirectoryName(Path.GetFullPath(resultPath));
                byte[] bytes = File.ReadAllBytes(resultPath);
                AnalysisSha = FrameCodec.Sha(bytes);
                analysis = JsonDocument.Parse(bytes);
                JsonElement a = analysis.RootElement;
                using MemoryStream canonical = new();
                using (Utf8JsonWriter json = new(canonical, new JsonWriterOptions { Encoder=JavaScriptEncoder.UnsafeRelaxedJsonEscaping }))
                    WriteCanonical(json,a,true);
                if (FrameCodec.Sha(canonical.ToArray()) != a.GetProperty("contentSha256").GetString())
                    throw new InvalidDataException("Analysis content SHA mismatch");
                if (a.GetProperty("format").GetString() != "range_fall_analysis" || a.GetProperty("version").GetInt32() != 1
                    || a.GetProperty("sessionId").GetString() != Id || a.GetProperty("metaSha256").GetString() != MetaSha
                    || a.GetProperty("pointsSha256").GetString() != PointsSha || a.GetProperty("confirmedEnabled").GetBoolean()
                    || a.GetProperty("coordinateFrame").GetString() != "sensor-IFW192S-raw" || a.GetProperty("units").GetString() != "m"
                    || a.GetProperty("sourceFrameCount").GetInt32() != Frames.Length)
                    throw new InvalidDataException("Analysis/source contract mismatch");
                foreach (JsonElement row in a.GetProperty("frames").EnumerateArray())
                {
                    int i = row.GetProperty("frameIndex").GetInt32();
                    if (i < 0 || i >= Frames.Length || row.GetProperty("stampSec").GetDouble() != Stamps[i]
                        || !results.TryAdd(i, row) || row.GetProperty("state").GetString() is not
                            ("unknown" or "upright" or "descending" or "low_posture_unclassified" or "suspected" or "recovering"))
                        throw new InvalidDataException("Analysis frame mismatch");
                }
            }
        }
        catch { Dispose(); throw; }
    }

    internal (byte[] Scene, byte[] Target, byte[] Intensity, object Info) Read(int index, int generation, bool playing, double speed)
    {
        if (index < 0 || index >= Frames.Length) throw new ArgumentOutOfRangeException(nameof(index));
        JsonElement info = Frames[index];
        int count = info.GetProperty("count_points").GetInt32();
        long offset = info.GetProperty("offset_points").GetInt64();
        byte[] raw = new byte[checked(count * 28)];
        points.Position = checked(offset * 28);
        points.ReadExactly(raw);
        byte[] scene = count == 0 ? [] : FrameCodec.Decode(index, count, offset, raw).Xyz;
        // 强度与 scene 同一过滤序（xyz 全有限的行）；布局合同钉死 offset 12 float32（meta point_layout 校验在构造函数）。
        byte[] intensity = new byte[scene.Length / 12 * 4];
        int kept = 0;
        for (int row = 0; row < count; row++)
        {
            ReadOnlySpan<byte> point = raw.AsSpan(row * 28, 28);
            if (!float.IsFinite(BinaryPrimitives.ReadSingleLittleEndian(point[..4]))
                || !float.IsFinite(BinaryPrimitives.ReadSingleLittleEndian(point.Slice(4, 4)))
                || !float.IsFinite(BinaryPrimitives.ReadSingleLittleEndian(point.Slice(8, 4)))) continue;
            point.Slice(12, 4).CopyTo(intensity.AsSpan(kept++ * 4, 4));
        }
        if (kept * 4 != intensity.Length) throw new InvalidDataException("Intensity/scene row mismatch");
        string rawSha = FrameCodec.Sha(raw);
        byte[] target = [];
        DepthPreview = null;
        object? depth = null;
        JsonElement? result = null;
        if (results.TryGetValue(index, out JsonElement r))
        {
            if (r.GetProperty("rawSha256").GetString() != rawSha) throw new InvalidDataException("Frame/result SHA mismatch");
            int[] rows = r.GetProperty("sourceRows").EnumerateArray().Select(v => v.GetInt32()).ToArray();
            if (rows.Distinct().Count() != rows.Length || rows.Any(i => i < 0 || i >= count)
                || r.GetProperty("measured").GetBoolean() != (rows.Length > 0))
                throw new InvalidDataException("Invalid target source rows");
            target = new byte[checked(rows.Length * 12)];
            for (int i = 0; i < rows.Length; i++)
            {
                raw.AsSpan(rows[i]*28, 12).CopyTo(target.AsSpan(i*12));
                for (int c = 0; c < 3; c++)
                    if (!float.IsFinite(BinaryPrimitives.ReadSingleLittleEndian(target.AsSpan(i*12+c*4,4))))
                        throw new InvalidDataException("Nonfinite target");
            }
            JsonElement box=r.GetProperty("box");
            if ((box.ValueKind==JsonValueKind.Object) != (rows.Length>0)) throw new InvalidDataException("Measurement/box mismatch");
            if (rows.Length>0)
            {
                double[] low=[double.PositiveInfinity,double.PositiveInfinity,double.PositiveInfinity];
                double[] high=[double.NegativeInfinity,double.NegativeInfinity,double.NegativeInfinity];
                for(int i=0;i<rows.Length;i++)for(int c=0;c<3;c++)
                {
                    double value=BinaryPrimitives.ReadSingleLittleEndian(target.AsSpan(i*12+c*4,4));
                    low[c]=Math.Min(low[c],value);high[c]=Math.Max(high[c],value);
                }
                double[] expected=[(low[0]+high[0])/2,(low[1]+high[1])/2,high[0]-low[0],high[1]-low[1],low[2],high[2]];
                string[] names=["x","y","w","h","zMin","zMax"];
                if(names.Select((name,i)=>Math.Abs(box.GetProperty(name).GetDouble()-expected[i])).Any(d=>!double.IsFinite(d)||d>1e-9))
                    throw new InvalidDataException("RAW box/source row mismatch");
            }
            var fields=r.EnumerateObject().Where(p=>p.Name!="sourceRows" && p.Name!="bodyCandidates")
                .ToDictionary(p=>p.Name,p=>(object?)p.Value.Clone());
            if(r.TryGetProperty("bodyCandidates",out JsonElement body))
            {
                if(body.GetProperty("semantic").GetString()!="UNKNOWN"
                    || body.GetProperty("method").GetString()!="range_topology_branches_v2")
                    throw new InvalidDataException("Unsupported body candidate semantics");
                HashSet<int> allowed=rows.ToHashSet(),used=[];
                var parts=new List<object>();
                foreach(JsonElement part in body.GetProperty("parts").EnumerateArray())
                {
                    int[] support=part.GetProperty("sourceRows").EnumerateArray().Select(v=>v.GetInt32()).ToArray();
                    if(support.Any(i=>!allowed.Contains(i)||!used.Add(i)))
                        throw new InvalidDataException("Body support/target mismatch");
                    parts.Add(new{part=part.GetProperty("part").GetString(),pointCount=support.Length});
                }
                fields["bodyCandidates"]=new{method=body.GetProperty("method").GetString(),parts};
            }
            if(r.TryGetProperty("groundAlert",out JsonElement alert)
                && (alert.GetProperty("confirmedEnabled").GetBoolean() || alert.GetProperty("semantic").GetString()!="UNKNOWN"
                    || alert.GetProperty("variant").GetString()!="ground_alert_v1"
                    || (alert.GetProperty("active").GetBoolean() && rows.Length==0)))
                throw new InvalidDataException("Unsupported low posture hint");
            result = JsonSerializer.SerializeToElement(fields);
            if(r.TryGetProperty("skeleton",out JsonElement skeleton)) ValidateSkeleton(skeleton,rows,raw);
            if(r.TryGetProperty("depth",out JsonElement d))
            {
                int depthVersion=d.GetProperty("version").GetInt32();
                bool orientationOk=(depthVersion==1 && d.GetProperty("orientation").GetString()=="row=ring,column=calibration_native_order")
                    || (depthVersion==2 && d.GetProperty("orientation").GetString()=="native_grid_rotated_180_for_view"
                        && d.GetProperty("nativeTransform").GetString()=="rotate180");
                if(d.GetProperty("format").GetString()!="lidar_range_image" || !orientationOk
                    || d.GetProperty("frameIndex").GetInt32()!=index || d.GetProperty("stampSec").GetDouble()!=Stamps[index]
                    || d.GetProperty("sessionId").GetString()!=Id || d.GetProperty("rawSha256").GetString()!=rawSha
                    || d.GetProperty("width").GetInt32()!=256 || d.GetProperty("height").GetInt32()!=192
                    || d.GetProperty("gridSha256").GetString()!=analysis!.RootElement.GetProperty("sourceBinding").GetProperty("grid_sha256").GetString()
                    || d.GetProperty("quantity").GetString()!="radial_range" || d.GetProperty("units").GetString()!="m"
                    || d.GetProperty("scaleM").GetDouble()!=.001 || d.GetProperty("invalidValue").GetInt32()!=0
                    || d.GetProperty("overflowValue").GetInt32()!=65535)
                    throw new InvalidDataException("Depth/source contract mismatch");
                DepthPreview=ReadAsset(d.GetProperty("preview"));
                depth=new { metadata=d.Clone(), previewSha256=FrameCodec.Sha(DepthPreview),
                    exportUrl=new Uri(artifactRoot!+Path.DirectorySeparatorChar).AbsoluteUri };
            }
        }
        return (scene, target, intensity, new { sessionId=Id, frameIndex=index, frameCount=Frames.Length,
            stampSec=Stamps[index], timeSec=Stamps[index]-Stamps[0], generation, playing, speed,
            sourceCount=count, sceneCount=scene.Length/12, targetCount=target.Length/12,
            rawSha256=rawSha, xyzSha256=FrameCodec.Sha(scene), targetSha256=FrameCodec.Sha(target),
            intensitySha256=FrameCodec.Sha(intensity), intensityAvailable=intensity.Length>0,
            result, depth, analysisIntervals=AnalysisIntervals, mode="replay", semantic="UNKNOWN", confirmedEnabled=false });
    }

    private byte[] ReadAsset(JsonElement asset)
    {
        string relative=asset.GetProperty("path").GetString()!;
        if(Path.IsPathRooted(relative) || relative.Contains(':') || relative.Split('/', '\\').Contains(".."))
            throw new InvalidDataException("Invalid depth path");
        string path=Path.GetFullPath(Path.Combine(artifactRoot!,relative));
        if(!path.StartsWith(artifactRoot!+Path.DirectorySeparatorChar,StringComparison.OrdinalIgnoreCase))
            throw new InvalidDataException("Depth path escaped artifact root");
        for(string? p=path;p is not null;p=Path.GetDirectoryName(p))
        {
            if((File.GetAttributes(p)&FileAttributes.ReparsePoint)!=0)throw new InvalidDataException("Depth links unsupported");
            if(string.Equals(p,artifactRoot,StringComparison.OrdinalIgnoreCase))break;
        }
        if(new FileInfo(path).Length>262144)throw new InvalidDataException("Depth preview too large");
        byte[] bytes=File.ReadAllBytes(path);
        if(bytes.Length!=asset.GetProperty("bytes").GetInt32() || FrameCodec.Sha(bytes)!=asset.GetProperty("sha256").GetString())
            throw new InvalidDataException("Depth asset SHA mismatch");
        return bytes;
    }

    internal static void ValidateSkeleton(JsonElement pose,int[] targetRows,byte[] raw,int pointStep=28)
    {
        if(pose.GetProperty("version").GetString()!="0.1.0"
            || pose.GetProperty("semantic").GetString()!="GEOMETRIC_REGIONS"
            || pose.GetProperty("anatomicalJoints").GetString()!="UNKNOWN")
            throw new InvalidDataException("Unsupported skeleton semantics");
        HashSet<int> allowed=targetRows.ToHashSet();
        JsonElement nodes=pose.GetProperty("nodes");
        if(nodes.EnumerateObject().Count()>12)throw new InvalidDataException("Too many skeleton nodes");
        foreach(JsonProperty node in nodes.EnumerateObject())
        {
            int[] support=node.Value.GetProperty("sourceRows").EnumerateArray().Select(v=>v.GetInt32()).ToArray();
            double[] xyz=node.Value.GetProperty("xyz").EnumerateArray().Select(v=>v.GetDouble()).ToArray();
            if(support.Length<6 || support.Length!=node.Value.GetProperty("supportCount").GetInt32()
                || support.Distinct().Count()!=support.Length || support.Any(i=>!allowed.Contains(i)) || xyz.Length!=3)
                throw new InvalidDataException("Skeleton support/target mismatch");
            for(int c=0;c<3;c++)
            {
                double[] values=support.Select(i=>(double)BinaryPrimitives.ReadSingleLittleEndian(raw.AsSpan(i*pointStep+c*4,4))).Order().ToArray();
                double median=(values[(values.Length-1)/2]+values[values.Length/2])/2;
                if(!double.IsFinite(xyz[c]) || Math.Abs(xyz[c]-median)>1e-9)
                    throw new InvalidDataException("Skeleton position/support mismatch");
            }
            if(node.Value.TryGetProperty("imageXY",out JsonElement pixel))
            {
                double[] xy=pixel.EnumerateArray().Select(v=>v.GetDouble()).ToArray();
                if(xy.Length!=2 || xy.Any(v=>!double.IsFinite(v)) || xy[0]<0 || xy[0]>255 || xy[1]<0 || xy[1]>191)
                    throw new InvalidDataException("Skeleton pixel outside range image");
            }
        }
        foreach(JsonElement edge in pose.GetProperty("edges").EnumerateArray())
        {
            string[] ends=edge.EnumerateArray().Select(v=>v.GetString()!).ToArray();
            if(ends.Length!=2 || ends[0]==ends[1] || ends.Any(k=>!nodes.TryGetProperty(k,out _)))
                throw new InvalidDataException("Skeleton edge mismatch");
        }
    }

    public void Dispose() { points?.Dispose(); meta?.Dispose(); analysis?.Dispose(); }

    private static void WriteCanonical(Utf8JsonWriter writer,JsonElement value,bool root=false)
    {
        if(value.ValueKind==JsonValueKind.Object)
        {
            writer.WriteStartObject();
            foreach(JsonProperty p in value.EnumerateObject().OrderBy(p=>p.Name,StringComparer.Ordinal))
            {if(root && p.Name=="contentSha256")continue;writer.WritePropertyName(p.Name);WriteCanonical(writer,p.Value);}
            writer.WriteEndObject();
        }
        else if(value.ValueKind==JsonValueKind.Array)
        {writer.WriteStartArray();foreach(JsonElement item in value.EnumerateArray())WriteCanonical(writer,item);writer.WriteEndArray();}
        else value.WriteTo(writer);
    }
}
