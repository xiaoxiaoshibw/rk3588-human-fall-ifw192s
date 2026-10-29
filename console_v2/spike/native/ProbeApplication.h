#pragma once
#include <QGuiApplication>
#include <QElapsedTimer>
#include <QThread>
#include <stdexcept>

// Pure ledger with injected nanosecond stamps. Draining during an active event accounts
// its prefix immediately; end() adds only the suffix, so a callback is not deferred/doubled.
class GuiWorkLedger {
public:
    void begin(qint64 now) { m_active = true; m_since = now; }
    void end(qint64 now) { m_pending += now - m_since; m_active = false; }
    qint64 drain(qint64 now)
    {
        if (m_active) { m_pending += now - m_since; m_since = now; }
        const qint64 value = m_pending; m_pending = 0; return value;
    }
    static void selfTest()
    {
        GuiWorkLedger test;
        test.begin(100);
        if (test.drain(130) != 30 || test.drain(140) != 10) throw std::runtime_error("GUI active prefix accounting");
        test.end(160);
        if (test.drain(200) != 20) throw std::runtime_error("GUI suffix counted twice or lost");
        test.begin(250); test.end(290);
        if (test.drain(400) != 40 || test.drain(500) != 0) throw std::runtime_error("GUI inactive idle counted");
    }
private:
    bool m_active = false;
    qint64 m_since = 0, m_pending = 0;
};

// Measurement only: GUI-event active wall time between the END of frame callbacks.
// Includes the current callback prefix, nested notify only once; excludes GPU/OS idle.
class ProbeApplication final : public QGuiApplication {
public:
    ProbeApplication(int &argc, char **argv) : QGuiApplication(argc, argv) { m_clock.start(); }
    bool notify(QObject *receiver, QEvent *event) override
    {
        if (QThread::currentThread() != thread()) return QGuiApplication::notify(receiver, event);
        const bool outer = m_depth++ == 0;
        if (outer) m_work.begin(m_clock.nsecsElapsed());
        const bool result = QGuiApplication::notify(receiver, event);
        m_depth--;
        if (outer) m_work.end(m_clock.nsecsElapsed());
        return result;
    }
    double takeFrameWorkMs()
    {
        return double(m_work.drain(m_clock.nsecsElapsed())) / 1e6;
    }
private:
    int m_depth = 0;
    QElapsedTimer m_clock;
    GuiWorkLedger m_work;
};
