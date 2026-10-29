using System.Diagnostics;
using System.Text.Json;
using Qml.Net;

var timer = Stopwatch.StartNew();
try
{
    // Deliberately no DiscoverOrDownloadSuitableQtRuntime: R2 supplies Qt 6 only.
    using var app = new QGuiApplication(args);
    using var engine = new QQmlApplicationEngine();
    engine.Load(Path.Combine(AppContext.BaseDirectory, "Probe.qml"));
    Console.WriteLine(JsonSerializer.Serialize(new { stage = "qml_engine_loaded", elapsed_ms = timer.Elapsed.TotalMilliseconds }));
    return app.Exec();
}
catch (Exception error)
{
    Console.Error.WriteLine(JsonSerializer.Serialize(new
    {
        stage = "A_QmlNet_Qt6_load", elapsed_ms = timer.Elapsed.TotalMilliseconds,
        exception = error.GetType().FullName, detail = error.ToString()
    }));
    return 2;
}
