using System.Text.Json;
using System.Text;

internal sealed class JointCaptureClient : IDisposable
{
    private readonly HttpClient http = new() { Timeout = TimeSpan.FromSeconds(12) };
    internal string PreviewUrl => new Uri(http.BaseAddress!,"api/preview").AbsoluteUri;
    internal JointCaptureClient(string url)
    {
        Uri uri = new(url);
        if (!uri.IsLoopback || uri.Scheme != "http" || !string.IsNullOrEmpty(uri.UserInfo)
            || uri.AbsolutePath != "/" || !string.IsNullOrEmpty(uri.Query))
            throw new ArgumentException("Joint recorder must be an explicitly configured local HTTP service");
        http.BaseAddress = uri;
    }
    internal async Task<JsonElement> Request(string action, JsonElement? body=null)
    {
        if (action is not ("status" or "start" or "stop" or "preview-config")) throw new ArgumentException("Unknown joint command");
        using StringContent content=new(JsonSerializer.Serialize(body ?? JsonSerializer.SerializeToElement(new { })),Encoding.UTF8,"application/json");
        using HttpResponseMessage response = action == "status"
            ? await http.GetAsync("api/status")
            : await http.PostAsync("api/" + action, content);
        string text = await response.Content.ReadAsStringAsync();
        if (!response.IsSuccessStatusCode) throw new IOException($"Recorder HTTP {(int)response.StatusCode}: {text}");
        return JsonSerializer.Deserialize<JsonElement>(text);
    }
    public void Dispose() => http.Dispose();
}
