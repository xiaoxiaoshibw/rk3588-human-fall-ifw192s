using System.Security.Cryptography;
using System.Text.Json;

internal static class EvidenceFiles
{
    private static string? Repository()
    {
        for (DirectoryInfo? at = new(AppContext.BaseDirectory); at is not null; at = at.Parent)
            if (File.Exists(Path.Combine(at.FullName, "docs", "PROJECT_WORKFLOW.md"))) return at.FullName;
        return null;
    }

    private static void Allowed(string path, IEnumerable<string> roots)
    {
        string full = Path.GetFullPath(path);
        if (!roots.Any(root => full.StartsWith(Path.GetFullPath(root).TrimEnd(Path.DirectorySeparatorChar)
            + Path.DirectorySeparatorChar, StringComparison.OrdinalIgnoreCase)))
            throw new UnauthorizedAccessException("Spike outputs must be inside application-owned scratch directories");
        for (DirectoryInfo? at = new(Path.GetDirectoryName(full)!); at is not null; at = at.Parent)
            if (at.Exists && (at.Attributes & FileAttributes.ReparsePoint) != 0)
                throw new UnauthorizedAccessException("Output directory link rejected");
    }

    internal static string ReportPath(string path, string extension)
    {
        var roots = new List<string> { Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "ConsoleV2", "SpikeEvidence") };
        string? repository = Repository();
        if (repository is not null)
        {
            roots.Add(Path.Combine(repository, "console_v2", ".tools", "spike-evidence"));
        }
        Allowed(path, roots);
        string full = Path.GetFullPath(path);
        if (Path.GetExtension(full) != extension || File.Exists(full)) throw new IOException("Output must be a new " + extension + " file");
        if (!Directory.Exists(Path.GetDirectoryName(full))) throw new DirectoryNotFoundException("Output parent must already exist");
        return full;
    }

    internal static string ExtractionPath(string directory)
    {
        var roots = new List<string> { Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "ConsoleV2", "SpikeRuntime") };
        string? repository = Repository();
        if (repository is not null) roots.Add(Path.Combine(repository, "console_v2", ".tools", "extracted"));
        // Validate a prospective child, allowing directory itself to be the approved root.
        Allowed(Path.Combine(Path.GetFullPath(directory), "payload"), roots);
        return Path.GetFullPath(directory);
    }

    internal static void WriteJson(string path, object value)
    {
        string checkedPath = ReportPath(path, ".json");
        using FileStream stream = new(checkedPath, FileMode.CreateNew, FileAccess.Write, FileShare.Read);
        JsonSerializer.Serialize(stream, value, new JsonSerializerOptions { WriteIndented = true });
    }

    internal static void VerifyPayload(string directory, IReadOnlyDictionary<string, string> manifest)
    {
        foreach ((string relative, string expected) in manifest)
        {
            string path = Path.GetFullPath(Path.Combine(directory, relative));
            if (!path.StartsWith(directory + Path.DirectorySeparatorChar, StringComparison.OrdinalIgnoreCase))
                throw new InvalidDataException("Payload manifest traversal");
            using FileStream stream = File.OpenRead(path);
            if (Convert.ToHexString(SHA256.HashData(stream)).ToLowerInvariant() != expected)
                throw new InvalidDataException("Payload SHA mismatch: " + relative);
        }
    }
}
