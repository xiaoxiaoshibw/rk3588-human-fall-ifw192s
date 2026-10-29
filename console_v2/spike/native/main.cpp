#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <QGuiApplication>
#include <QQmlApplicationEngine>
#include <QQmlContext>
#include <QQuickWindow>
#include <QSGRendererInterface>
#include <QElapsedTimer>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QMutex>
#include <QMutexLocker>
#include <QTimer>
#include <QSurfaceFormat>
#include <QImage>
#include <algorithm>
#include <cmath>
#include <stdexcept>
#include "PointGeometry.h"
#include "ProbeApplication.h"

namespace {
QStringList logs;
QMutex logMutex;
void logMessage(QtMsgType, const QMessageLogContext &, const QString &message)
{
    QMutexLocker guard(&logMutex);
    logs.append(message);
}
void readExact(HANDLE pipe, char *target, DWORD bytes)
{
    while (bytes) {
        DWORD got = 0;
        if (!ReadFile(pipe, target, bytes, &got, nullptr) || !got) throw std::runtime_error("Pipe closed while reading");
        target += got; bytes -= got;
    }
}
void send(HANDLE pipe, const QJsonObject &message)
{
    const QByteArray bytes = QJsonDocument(message).toJson(QJsonDocument::Compact) + '\n';
    DWORD written = 0;
    if (!WriteFile(pipe, bytes.constData(), DWORD(bytes.size()), &written, nullptr) || written != DWORD(bytes.size()))
        throw std::runtime_error("Pipe report failed");
}
QJsonObject distribution(QList<double> values)
{
    std::sort(values.begin(), values.end());
    if (values.isEmpty()) return {{"n", 0}};
    const auto p = [&](double q) { return values[qMax(0, int(std::ceil(q * values.size())) - 1)]; };
    return {{"n", values.size()}, {"p50", p(.50)}, {"p95", p(.95)}, {"p99", p(.99)}, {"max", values.last()}};
}
QJsonArray samples(const QList<double> &values)
{
    QJsonArray result;
    for (const double value : values) result.append(value);
    return result;
}
}

int main(int argc, char **argv)
{
    QElapsedTimer processTimer; processTimer.start();
    qInstallMessageHandler(logMessage);
    QSurfaceFormat format; format.setSwapInterval(0); QSurfaceFormat::setDefaultFormat(format);
    ProbeApplication app(argc, argv);
    const QStringList arguments = app.arguments();
    const auto option = [&](const QString &key, const QString &fallback = QString()) {
        const int index = arguments.indexOf(key);
        return index >= 0 && index + 1 < arguments.size() ? arguments[index + 1] : fallback;
    };
    const QString name = "\\\\.\\pipe\\" + option("--pipe");
    HANDLE pipe = INVALID_HANDLE_VALUE, mapping = nullptr;
    const char *view = nullptr;
    try {
        GuiWorkLedger::selfTest();
        PointGeometry::selfTestLayout();
        if (!WaitNamedPipeW(reinterpret_cast<LPCWSTR>(name.utf16()), 15000)) throw std::runtime_error("Service pipe not available");
        pipe = CreateFileW(reinterpret_cast<LPCWSTR>(name.utf16()), GENERIC_READ | GENERIC_WRITE, 0, nullptr, OPEN_EXISTING, 0, nullptr);
        if (pipe == INVALID_HANDLE_VALUE) throw std::runtime_error("Service pipe open failed");
        quint32 length = 0; readExact(pipe, reinterpret_cast<char *>(&length), sizeof(length));
        if (length < 1 || length > 65536) throw std::runtime_error("Descriptor length invalid");
        QByteArray bytes(qsizetype(length), '\0'); readExact(pipe, bytes.data(), length);
        const QJsonDocument document = QJsonDocument::fromJson(bytes);
        const QJsonObject descriptor = document.object();
        if (descriptor["version"].toInt() != 1 || descriptor["stride"].toInt() != 12) throw std::runtime_error("Protocol mismatch");
        const qint64 capacity = descriptor["bytes"].toInteger();
        const QJsonArray layout = descriptor["frames"].toArray();
        PointGeometry::validateLayout(layout, capacity);
        const QString mapName = descriptor["map"].toString();
        mapping = OpenFileMappingW(FILE_MAP_READ, FALSE, reinterpret_cast<LPCWSTR>(mapName.utf16()));
        if (!mapping) throw std::runtime_error("Shared map not available");
        view = static_cast<const char *>(MapViewOfFile(mapping, FILE_MAP_READ, 0, 0, SIZE_T(capacity)));
        if (!view) throw std::runtime_error("Shared map view failed");
        PointGeometry geometry;
        geometry.attach(view, layout, capacity);
        geometry.submit(0);
        QQmlApplicationEngine engine;
        engine.rootContext()->setContextProperty("cloudGeometry", &geometry);
        engine.rootContext()->setContextProperty("sessionId", option("--sid"));
        engine.rootContext()->setContextProperty("modeLabel", option("--mode").startsWith("synthetic") ?
            QString("Synthetic tiled stress / ") + option("--mode") : QString("Real source frames 0–2 / dynamic upload"));
        engine.load(QUrl("qrc:/Main.qml"));
        if (engine.rootObjects().isEmpty()) throw std::runtime_error("QML did not create window");
        auto *window = qobject_cast<QQuickWindow *>(engine.rootObjects().first());
        if (!window) throw std::runtime_error("Root is not QQuickWindow");
        const bool dynamic = option("--updates", "dynamic") == "dynamic";
        const double warmup = 1.0, duration = option("--duration", "10").toDouble();
        if (duration < 1 || duration > 60) throw std::runtime_error("Duration outside 1..60 seconds");
        QElapsedTimer clock; clock.start();
        QMutex sampleMutex;
        QList<qint64> swaps;
        QList<double> copies, heartbeatExcess, guiFrameWork;
        int submissions = 1, displayIndex = 0;
        bool first = true, finished = false;
        QObject::connect(window, &QQuickWindow::frameSwapped, window, [&] {
            const qint64 stamp = clock.nsecsElapsed();
            QMutexLocker guard(&sampleMutex);
            swaps.append(stamp);
        }, Qt::DirectConnection);
        QObject::connect(window, &QQuickWindow::frameSwapped, window, [&] {
            if (finished) return;
            const double seconds = double(clock.nsecsElapsed()) / 1e9;
            if (first) {
                first = false;
                send(pipe, {{"event", "first_frame"}, {"qt_elapsed_ms", double(processTimer.nsecsElapsed()) / 1e6},
                    {"width", window->width()}, {"height", window->height()}, {"dpr", window->devicePixelRatio()}});
            }
            if (dynamic) {
                displayIndex = (displayIndex + 1) % 3;
                const double cost = geometry.submit(displayIndex);
                if (seconds >= warmup) copies.append(cost);
                submissions++;
            }
            window->setProperty("sceneAngle", -10 + std::sin(seconds * 0.6283185307) * 10);
            window->update();
            const double guiWork = app.takeFrameWorkMs();
            if (seconds >= warmup) guiFrameWork.append(guiWork);
        }, Qt::QueuedConnection);
        QElapsedTimer heartbeatClock; heartbeatClock.start();
        QTimer heartbeat;
        heartbeat.setTimerType(Qt::PreciseTimer); heartbeat.setInterval(1);
        QObject::connect(&heartbeat, &QTimer::timeout, window, [&] {
            const double gap = double(heartbeatClock.nsecsElapsed()) / 1e6; heartbeatClock.restart();
            if (clock.elapsed() >= 1000 && !finished) heartbeatExcess.append(qMax(0.0, gap - 1.0));
        });
        heartbeat.start();
        QTimer::singleShot(2500, window, [&] {
            const QString path = option("--screenshot");
            if (!path.isEmpty()) window->grabWindow().save(path);
        });
        QTimer::singleShot(int((warmup + duration) * 1000), window, [&] {
            finished = true; heartbeat.stop();
            QList<double> intervals;
            int measured = 0;
            qint64 firstStamp = 0, lastStamp = 0;
            {
                QMutexLocker guard(&sampleMutex);
                qint64 previous = 0;
                for (const qint64 stamp : swaps) {
                    if (double(stamp) / 1e9 < warmup || double(stamp) / 1e9 > warmup + duration) continue;
                    if (!firstStamp) firstStamp = stamp;
                    lastStamp = stamp; measured++;
                    if (previous) intervals.append(double(stamp - previous) / 1e6);
                    previous = stamp;
                }
            }
            QJsonArray messages;
            { QMutexLocker guard(&logMutex); for (const QString &line : logs) messages.append(line); }
            const double span = double(lastStamp - firstStamp) / 1e9;
            send(pipe, {{"event", "complete"}, {"mode", option("--mode")}, {"dynamic", dynamic},
                {"points", geometry.pointCount()}, {"warmup_s", warmup}, {"measurement_s", duration},
                {"frame_swapped_count", measured}, {"frame_swapped_fps", span > 0 ? (measured - 1) / span : 0},
                {"submissions_total", submissions}, {"interval_ms", distribution(intervals)},
                {"qt_copy_submit_ms", distribution(copies)}, {"ui_heartbeat_excess_ms", distribution(heartbeatExcess)},
                {"gui_event_work_per_frame_ms", distribution(guiFrameWork)},
                {"interval_ms_raw", samples(intervals)}, {"qt_copy_submit_ms_raw", samples(copies)},
                {"gui_event_work_per_frame_ms_raw", samples(guiFrameWork)},
                {"ui_heartbeat_excess_ms_raw", samples(heartbeatExcess)},
                {"qt_version", qVersion()}, {"graphics_api", int(window->rendererInterface()->graphicsApi())},
                {"self_checks", QJsonObject{{"gui_active_event_accounting", true}, {"layout_before_mapping", true}}},
                {"width", window->width()}, {"height", window->height()}, {"dpr", window->devicePixelRatio()},
                {"qt_logs", messages}, {"percentile", "nearest rank"},
                {"scope", "frameSwapped software presentation; GUI-event active wall time between callback-end drains including active prefix exactly once; heartbeat separate; no photon/GPU timestamp proof"}});
            app.quit();
        });
        window->update();
        const int result = app.exec();
        // Destroy the window while callback captures still exist; its render loop must stop before samples die.
        QObject::disconnect(window, nullptr, window, nullptr);
        delete window;
        // Qt engine and geometry still hold only Qt-owned deep copies, not raw mapped pointers.
        UnmapViewOfFile(view); view = nullptr; CloseHandle(mapping); mapping = nullptr;
        CloseHandle(pipe); pipe = INVALID_HANDLE_VALUE;
        qInstallMessageHandler(nullptr);
        return result;
    } catch (const std::exception &error) {
        if (pipe != INVALID_HANDLE_VALUE) {
            try {
                QJsonArray messages;
                { QMutexLocker guard(&logMutex); for (const QString &line : logs) messages.append(line); }
                send(pipe, {{"event", "error"}, {"detail", error.what()}, {"qt_logs", messages}});
            } catch (...) { }
        }
        if (view) UnmapViewOfFile(view);
        if (mapping) CloseHandle(mapping);
        if (pipe != INVALID_HANDLE_VALUE) CloseHandle(pipe);
        return 2;
    }
}
