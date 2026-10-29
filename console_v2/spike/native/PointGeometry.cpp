#include "PointGeometry.h"
#include <QCryptographicHash>
#include <QElapsedTimer>
#include <QVector3D>
#include <stdexcept>

void PointGeometry::validateLayout(const QJsonArray &descriptors, qint64 capacity)
{
    if (descriptors.size() != 3 || capacity <= 0 || capacity > qint64(3) * 500000 * 12)
        throw std::runtime_error("Invalid shared capacity before mapping");
    qint64 covered = 0;
    for (const QJsonValue &value : descriptors) {
        const QJsonObject frame = value.toObject();
        const qint64 offset = frame["offset"].toInteger(), bytes = frame["bytes"].toInteger();
        const int count = frame["count"].toInt();
        if (offset != covered || bytes <= 0 || count <= 0 || count > 500000 || bytes != qint64(count) * 12 || offset > capacity - bytes)
            throw std::runtime_error("Shared frame outside map");
        covered += bytes;
    }
    if (covered != capacity) throw std::runtime_error("Shared frames do not cover map exactly");
}

void PointGeometry::selfTestLayout()
{
    QJsonArray good;
    for (int i = 0; i < 3; i++) good.append(QJsonObject{{"offset", i * 12}, {"bytes", 12}, {"count", 1}});
    validateLayout(good, 36);
    for (int which = 0; which < 5; which++) {
        QJsonArray bad = good;
        qint64 capacity = 36;
        if (which == 0) capacity = 0;
        if (which == 1) capacity = 18000001;
        if (which >= 2) {
            QJsonObject frame = bad[0].toObject();
            if (which == 2) frame["offset"] = -1;
            if (which == 3) frame["bytes"] = 120;
            if (which == 4) frame["offset"] = 12;
            bad[0] = frame;
        }
        bool rejected = false;
        try { validateLayout(bad, capacity); } catch (const std::runtime_error &) { rejected = true; }
        if (!rejected) throw std::runtime_error("Invalid layout self-test accepted");
    }
}

void PointGeometry::attach(const char *view, const QJsonArray &descriptors, qint64 capacity)
{
    validateLayout(descriptors, capacity);
    if (!view) throw std::runtime_error("No shared mapping view");
    m_view = view; m_frames = descriptors; m_capacity = capacity;
    for (const QJsonValue &value : m_frames) {
        const QJsonObject frame = value.toObject();
        const qint64 offset = frame["offset"].toInteger(), bytes = frame["bytes"].toInteger();
        const QByteArray actual = QCryptographicHash::hash(QByteArray(m_view + offset, bytes), QCryptographicHash::Sha256).toHex();
        if (actual != frame["sha256"].toString().toLatin1()) throw std::runtime_error("Shared frame SHA mismatch");
    }
}

double PointGeometry::submit(int index)
{
    QElapsedTimer timer; timer.start();
    if (index < 0 || index >= m_frames.size()) throw std::runtime_error("Frame index outside probe");
    const QJsonObject frame = m_frames[index].toObject();
    const qint64 offset = frame["offset"].toInteger(), bytes = frame["bytes"].toInteger();
    // This constructor owns a deep copy. The immutable service map remains alive for the whole run too.
    const QByteArray owned(m_view + offset, bytes);
    const QJsonArray low = frame["min"].toArray(), high = frame["max"].toArray();
    const QVector3D lo(float(low[0].toDouble()), float(low[1].toDouble()), float(low[2].toDouble()));
    const QVector3D hi(float(high[0].toDouble()), float(high[1].toDouble()), float(high[2].toDouble()));
    clear();
    setStride(12); setPrimitiveType(QQuick3DGeometry::PrimitiveType::Points);
    addAttribute(QQuick3DGeometry::Attribute::PositionSemantic, 0, QQuick3DGeometry::Attribute::F32Type);
    setBounds(lo, hi); setVertexData(owned); update();
    m_count = frame["count"].toInt(); m_center = (lo + hi) * .5f;
    m_radius = qMax(1.f, (hi - lo).length() * .5f);
    emit changed();
    return double(timer.nsecsElapsed()) / 1e6;
}
