using System.Buffers.Binary;
using System.Security.Cryptography;
using System.Text.Json;

internal sealed record RawFrame(int Index, int Count, long Offset, byte[] Raw, byte[] Xyz,
    int NonFinite, string RawSha256, string FieldsSha256);
internal sealed record RenderFrame(int Index, int SourceCount, int Count, byte[] Bytes, float[] Min, float[] Max,
    string Sha256, string Construction);

internal static class FrameCodec
{
    internal static string Sha(ReadOnlySpan<byte> bytes) => Convert.ToHexString(SHA256.HashData(bytes)).ToLowerInvariant();

    internal static RawFrame Decode(int index, int count, long offset, byte[] raw)
    {
        if (count <= 0 || raw.LongLength != checked((long)count * 28))
            throw new InvalidDataException("Expected exact nonempty stride-28 frame");
        byte[] fields = new byte[checked(count * 22)];
        byte[] xyz = new byte[checked(count * 12)];
        int kept = 0;
        for (int row = 0; row < count; row++)
        {
            ReadOnlySpan<byte> input = raw.AsSpan(row * 28, 28);
            Span<byte> values = fields.AsSpan(row * 22, 22);
            for (int column = 0; column < 4; column++)
            {
                float value = BinaryPrimitives.ReadSingleLittleEndian(input.Slice(column * 4, 4));
                BinaryPrimitives.WriteSingleLittleEndian(values.Slice(column * 4, 4), value);
            }
            BinaryPrimitives.WriteUInt16LittleEndian(values.Slice(16, 2), BinaryPrimitives.ReadUInt16LittleEndian(input.Slice(16, 2)));
            BinaryPrimitives.WriteSingleLittleEndian(values.Slice(18, 4), BinaryPrimitives.ReadSingleLittleEndian(input.Slice(20, 4)));
            float x = BinaryPrimitives.ReadSingleLittleEndian(input[..4]);
            float y = BinaryPrimitives.ReadSingleLittleEndian(input.Slice(4, 4));
            float z = BinaryPrimitives.ReadSingleLittleEndian(input.Slice(8, 4));
            if (!float.IsFinite(x) || !float.IsFinite(y) || !float.IsFinite(z)) continue;
            input[..12].CopyTo(xyz.AsSpan(kept * 12, 12));
            kept++;
        }
        Array.Resize(ref xyz, kept * 12);
        return new RawFrame(index, count, offset, raw, xyz, count - kept, Sha(raw), Sha(fields));
    }

    internal static RawFrame[] ReadThree(string directory)
    {
        using JsonDocument document = JsonDocument.Parse(File.ReadAllBytes(Path.Combine(directory, "meta.json")));
        JsonElement meta = document.RootElement;
        int stride = meta.GetProperty("point_layout").GetProperty("stride_bytes").GetInt32();
        if (stride != 28 || meta.GetProperty("point_file").GetString() != "points.bin")
            throw new InvalidDataException("R2 probe accepts only declared points.bin / stride 28");
        using FileStream points = new(Path.Combine(directory, "points.bin"), FileMode.Open, FileAccess.Read, FileShare.Read);
        JsonElement[] frames = meta.GetProperty("frames").EnumerateArray().Take(3).ToArray();
        if (frames.Length != 3) throw new InvalidDataException("Three source frames required");
        var result = new List<RawFrame>();
        for (int i = 0; i < frames.Length; i++)
        {
            int count = frames[i].GetProperty("count_points").GetInt32();
            long offset = frames[i].GetProperty("offset_points").GetInt64();
            long start = checked(offset * stride), size = checked((long)count * stride);
            if (count <= 0 || offset < 0 || size > int.MaxValue || start > points.Length - size)
                throw new InvalidDataException("Frame outside point file");
            points.Position = start;
            byte[] raw = new byte[(int)size];
            points.ReadExactly(raw);
            result.Add(Decode(i, count, offset, raw));
        }
        return result.ToArray();
    }

    internal static RenderFrame Project(RawFrame source, int targetCount)
    {
        int sourceCount = source.Xyz.Length / 12;
        if (sourceCount == 0) throw new InvalidDataException("No finite source XYZ");
        int count = targetCount == 0 ? sourceCount : targetCount;
        if (count < 1 || count > 500_000) throw new ArgumentOutOfRangeException(nameof(targetCount));
        byte[] buffer = new byte[checked(count * 12)];
        float[] min = [float.PositiveInfinity, float.PositiveInfinity, float.PositiveInfinity];
        float[] max = [float.NegativeInfinity, float.NegativeInfinity, float.NegativeInfinity];
        for (int i = 0; i < count; i++)
        {
            int sourceRow = i % sourceCount, tile = targetCount == 0 ? 0 : i / sourceCount;
            for (int c = 0; c < 3; c++)
            {
                float value = BinaryPrimitives.ReadSingleLittleEndian(source.Xyz.AsSpan(sourceRow * 12 + c * 4, 4));
                // Stress only: deterministic tiled copies; this is never called a real 500k-point frame.
                if (tile != 0 && c == 0) value += (tile % 4) * 2f;
                if (tile != 0 && c == 1) value += (tile / 4) * 2f;
                BinaryPrimitives.WriteSingleLittleEndian(buffer.AsSpan(i * 12 + c * 4, 4), value);
                min[c] = Math.Min(min[c], value); max[c] = Math.Max(max[c], value);
            }
        }
        return new RenderFrame(source.Index, sourceCount, count, buffer, min, max, Sha(buffer),
            targetCount == 0 ? "finite source XYZ, source order; zero XYZ retained" :
            "source_row=i%finite_count; tile=i/finite_count; x+=(tile%4)*2m; y+=(tile/4)*2m; synthetic stress only");
    }

    internal static object SelfTest()
    {
        byte[] point = new byte[28];
        float[] expected = [1.25f, -2.5f, 3.75f, 16f];
        for (int i = 0; i < 4; i++) BinaryPrimitives.WriteSingleLittleEndian(point.AsSpan(i * 4, 4), expected[i]);
        BinaryPrimitives.WriteUInt16LittleEndian(point.AsSpan(16, 2), 4095);
        BinaryPrimitives.WriteUInt16LittleEndian(point.AsSpan(18, 2), 0xffff);
        BinaryPrimitives.WriteSingleLittleEndian(point.AsSpan(20, 4), .25f);
        RawFrame decoded = Decode(0, 1, 0, point);
        RenderFrame render = Project(decoded, 50_000);
        byte[] expectedFields = Convert.FromHexString("0000a03f000020c00000704000008041ff0f0000803e");
        if (decoded.FieldsSha256 != Sha(expectedFields) || !decoded.Xyz.AsSpan().SequenceEqual(expectedFields.AsSpan(0, 12))
            || decoded.NonFinite != 0 || render.Count != 50_000 || render.Bytes.Length != 600_000)
            throw new InvalidDataException("Self-test failed");
        bool truncatedRejected = false;
        try { Decode(0, 2, 0, point); } catch (InvalidDataException) { truncatedRejected = true; }
        if (!truncatedRejected) throw new InvalidDataException("Truncation accepted");
        BinaryPrimitives.WriteSingleLittleEndian(point.AsSpan(0, 4), float.NaN);
        if (Decode(0, 1, 0, point).NonFinite != 1) throw new InvalidDataException("NaN not accounted");
        return new { passed = true, cases = new[] { "known stride28/ring/padding/timestamp", "exact 50000 projection", "truncated reject", "nonfinite accounting" } };
    }
}
