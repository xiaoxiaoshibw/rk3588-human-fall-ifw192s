using System.Diagnostics;
using System.IO.MemoryMappedFiles;
using System.IO.Pipes;
using System.IO.Compression;
using System.Reflection;
using System.Text.Json;
using System.Text.RegularExpressions;

internal static class Program
{
    private static string Required(Dictionary<string, string> options, string name) =>
        options.TryGetValue(name, out string? value) ? value : throw new ArgumentException("Missing " + name);

    private static Dictionary<string, string> Arguments(string[] args)
    {
        var result = new Dictionary<string, string>(StringComparer.Ordinal);
        for (int i = 0; i < args.Length; i += 2)
        {
            if (!args[i].StartsWith("--", StringComparison.Ordinal) || i + 1 >= args.Length || !result.TryAdd(args[i], args[i + 1]))
                throw new ArgumentException("Expected unique --key value options");
        }
        return result;
    }

    private static void WriteJson(string path, object value) => EvidenceFiles.WriteJson(path, value);

    private static string ExtractHost(string directory)
    {
        directory = EvidenceFiles.ExtractionPath(directory);
        using Stream payload = Assembly.GetExecutingAssembly().GetManifestResourceStream("QtPayload.zip")
            ?? throw new FileNotFoundException("No embedded Qt payload; provide --host for development");
        string hash;
        using (var sha = System.Security.Cryptography.SHA256.Create())
            hash = Convert.ToHexString(sha.ComputeHash(payload)).ToLowerInvariant();
        payload.Position = 0;
        string root = Path.GetFullPath(Path.Combine(directory, "qt-" + hash[..16]));
        using Stream manifestStream = Assembly.GetExecutingAssembly().GetManifestResourceStream("QtPayload.manifest.json")
            ?? throw new InvalidDataException("No embedded payload manifest");
        var manifest = JsonSerializer.Deserialize<Dictionary<string, string>>(manifestStream)
            ?? throw new InvalidDataException("Invalid embedded manifest");
        if (!File.Exists(Path.Combine(root, "complete.sha256")))
        {
            if (Directory.Exists(root)) throw new IOException("Incomplete existing extraction retained; choose a fresh extraction root");
            Directory.CreateDirectory(root);
            using var archive = new ZipArchive(payload, ZipArchiveMode.Read, leaveOpen: true);
            foreach (ZipArchiveEntry entry in archive.Entries)
            {
                string target = Path.GetFullPath(Path.Combine(root, entry.FullName));
                if (!target.StartsWith(root + Path.DirectorySeparatorChar, StringComparison.OrdinalIgnoreCase))
                    throw new InvalidDataException("Embedded payload traversal");
                Directory.CreateDirectory(Path.GetDirectoryName(target)!);
                if (!entry.FullName.EndsWith('/')) entry.ExtractToFile(target, overwrite: false);
            }
            EvidenceFiles.VerifyPayload(root, manifest);
            File.WriteAllText(Path.Combine(root, "complete.sha256"), hash);
        }
        else EvidenceFiles.VerifyPayload(root, manifest);
        return Path.Combine(root, "QtSpike.exe");
    }

    public static int Main(string[] args)
    {
        var timer = Stopwatch.StartNew();
        var phases = new List<object>();
        void Mark(string stage) => phases.Add(new { stage, elapsed_ms = timer.Elapsed.TotalMilliseconds });
        string? report = null;
        Process? ownedChild = null;
        try
        {
            var options = Arguments(args);
            report = EvidenceFiles.ReportPath(Required(options, "--report"), ".json");
            if (options.TryGetValue("--screenshot", out string? screenshot) && screenshot.Length != 0)
                EvidenceFiles.ReportPath(screenshot, ".png");
            if (options.GetValueOrDefault("--self-test") == "1")
            {
                WriteJson(report, FrameCodec.SelfTest()); return 0;
            }
            int count = int.Parse(options.GetValueOrDefault("--count", "0"), System.Globalization.CultureInfo.InvariantCulture);
            if (count is not (0 or 50_000 or 500_000))
                throw new ArgumentException("--count must be 0, 50000 or 500000");
            string updates = options.GetValueOrDefault("--updates", "dynamic");
            if (updates is not ("dynamic" or "static"))
                throw new ArgumentException("--updates must be dynamic or static");
            string source = Path.GetFullPath(Required(options, "--session"));
            RawFrame[] raw = FrameCodec.ReadThree(source);
            Mark("three_frames_read_decoded_hashed");
            RenderFrame[] frames = raw.Select(f => FrameCodec.Project(f, count)).ToArray();
            Mark("three_render_buffers_built_hashed");
            string sid = Path.GetFileName(source.TrimEnd(Path.DirectorySeparatorChar));
            if (!Regex.IsMatch(sid, "^[A-Za-z0-9_-]{1,100}$")) throw new InvalidDataException("Invalid session basename");
            object[] decoded = raw.Select((f, i) => (object)new
            {
                frame = f.Index, count = f.Count, offset_points = f.Offset, nonfinite_xyz = f.NonFinite,
                raw_sha256 = f.RawSha256, canonical_fields_sha256 = f.FieldsSha256,
                xyz_sha256 = FrameCodec.Sha(f.Xyz), projected_sha256 = frames[i].Sha256,
                projected_count = frames[i].Count, construction = frames[i].Construction
            }).ToArray();
            if (options.GetValueOrDefault("--decode-only") == "1")
            {
                WriteJson(report, new { stage = "decode_only", sid, stride = 28, frames = decoded, elapsed_ms = timer.Elapsed.TotalMilliseconds });
                return 0;
            }
            string runId = Guid.NewGuid().ToString("N");
            string mapName = "Local\\ConsoleV2.Spike." + runId, pipeName = "ConsoleV2.Spike." + runId;
            long bytes = frames.Sum(f => (long)f.Bytes.Length);
            using MemoryMappedFile map = MemoryMappedFile.CreateNew(mapName, bytes, MemoryMappedFileAccess.ReadWrite);
            using MemoryMappedViewAccessor writer = map.CreateViewAccessor(0, bytes, MemoryMappedFileAccess.Write);
            long offset = 0;
            var descriptions = new List<object>();
            foreach (RenderFrame frame in frames)
            {
                writer.WriteArray(offset, frame.Bytes, 0, frame.Bytes.Length);
                descriptions.Add(new { frame = frame.Index, offset, bytes = frame.Bytes.Length, count = frame.Count,
                    min = frame.Min, max = frame.Max, sha256 = frame.Sha256 });
                offset += frame.Bytes.Length;
            }
            writer.Flush();
            Mark("shared_map_populated");
            using var pipe = new NamedPipeServerStream(pipeName, PipeDirection.InOut, 1, PipeTransmissionMode.Byte,
                PipeOptions.Asynchronous | PipeOptions.CurrentUserOnly);
            string host = options.TryGetValue("--host", out string? developmentHost) ? Path.GetFullPath(developmentHost) :
                ExtractHost(Required(options, "--extract-root"));
            Mark("qt_payload_verified_or_extracted");
            var start = new ProcessStartInfo(host) { UseShellExecute = false, CreateNoWindow = true,
                RedirectStandardOutput = true, RedirectStandardError = true, WorkingDirectory = Path.GetDirectoryName(host)! };
            foreach (string item in new[] { "--pipe", pipeName, "--duration", options.GetValueOrDefault("--duration", "10"),
                "--updates", updates, "--mode", count == 0 ? "real3" : "synthetic" + count,
                "--sid", sid, "--screenshot", options.GetValueOrDefault("--screenshot", "") }) start.ArgumentList.Add(item);
            start.Environment["QT_QPA_PLATFORM_PLUGIN_PATH"] = Path.Combine(Path.GetDirectoryName(host)!, "platforms");
            start.Environment["QML2_IMPORT_PATH"] = Path.Combine(Path.GetDirectoryName(host)!, "qml");
            Process child = ownedChild = Process.Start(start) ?? throw new InvalidOperationException("Qt host did not start");
            Mark("qt_process_started");
            Task<string> childOut = child.StandardOutput.ReadToEndAsync(), childError = child.StandardError.ReadToEndAsync();
            using var timeout = new CancellationTokenSource(TimeSpan.FromSeconds(90));
            Task connected = pipe.WaitForConnectionAsync(timeout.Token);
            Task stopped = child.WaitForExitAsync(timeout.Token);
            Task.WhenAny(connected, stopped).GetAwaiter().GetResult();
            if (!connected.IsCompletedSuccessfully)
                throw new InvalidOperationException("Qt exited before pipe connect: " + childError.GetAwaiter().GetResult());
            connected.GetAwaiter().GetResult();
            Mark("qt_process_connected_pipe");
            using var output = new BinaryWriter(pipe, System.Text.Encoding.UTF8, leaveOpen: true);
            byte[] descriptor = JsonSerializer.SerializeToUtf8Bytes(new { version = 1, map = mapName, bytes, stride = 12,
                source = sid, frames = descriptions });
            output.Write(descriptor.Length); output.Write(descriptor); output.Flush();
            using var input = new StreamReader(pipe, System.Text.Encoding.UTF8, leaveOpen: true);
            var messages = new List<JsonElement>();
            while (true)
            {
                string? line = input.ReadLineAsync(timeout.Token).AsTask().GetAwaiter().GetResult();
                if (line is null) break;
                using JsonDocument message = JsonDocument.Parse(line);
                JsonElement value = message.RootElement.Clone();
                if (value.GetProperty("event").GetString() == "first_frame")
                {
                    Mark("first_frame_message_received");
                    messages.Add(JsonSerializer.SerializeToElement(new { @event = "first_frame", service_elapsed_ms = timer.Elapsed.TotalMilliseconds }));
                    WriteJson(report + ".first.json", new { service_elapsed_ms = timer.Elapsed.TotalMilliseconds,
                        process_start_utc = Process.GetCurrentProcess().StartTime.ToUniversalTime(), observed_utc = DateTime.UtcNow });
                }
                messages.Add(value);
                if (value.GetProperty("event").GetString() == "complete") break;
            }
            if (!child.WaitForExit(10000)) throw new TimeoutException("Qt host did not close");
            WriteJson(report, new { stage = "B_QtCpp_CSharpService", sid, count, frames = decoded,
                messages, child_exit_code = child.ExitCode, elapsed_ms = timer.Elapsed.TotalMilliseconds,
                startup_phases = phases,
                qt_stdout = childOut.GetAwaiter().GetResult(), qt_stderr = childError.GetAwaiter().GetResult(),
                runtime = System.Runtime.InteropServices.RuntimeInformation.FrameworkDescription, worker = "none", board_calls = 0 });
            return child.ExitCode;
        }
        catch (Exception error)
        {
            if (report is not null && !File.Exists(report))
                WriteJson(report, new { stage = "failed", detail = error.ToString(), elapsed_ms = timer.Elapsed.TotalMilliseconds });
            Console.Error.WriteLine(error); return 2;
        }
        finally
        {
            if (ownedChild is not null)
            {
                if (!ownedChild.HasExited) { ownedChild.Kill(entireProcessTree: true); ownedChild.WaitForExit(); }
                ownedChild.Dispose();
            }
        }
    }
}
