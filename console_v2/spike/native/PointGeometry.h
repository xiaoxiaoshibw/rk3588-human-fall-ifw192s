#pragma once
#include <QQuick3DGeometry>
#include <QJsonArray>
#include <QJsonObject>
#include <QVector3D>

class PointGeometry final : public QQuick3DGeometry {
    Q_OBJECT
    Q_PROPERTY(int pointCount READ pointCount NOTIFY changed)
    Q_PROPERTY(QVector3D center READ center NOTIFY changed)
    Q_PROPERTY(float radius READ radius NOTIFY changed)
public:
    static void validateLayout(const QJsonArray &descriptors, qint64 capacity);
    static void selfTestLayout();
    void attach(const char *view, const QJsonArray &descriptors, qint64 capacity);
    double submit(int index);
    int pointCount() const { return m_count; }
    QVector3D center() const { return m_center; }
    float radius() const { return m_radius; }
signals:
    void changed();
private:
    const char *m_view = nullptr;
    QJsonArray m_frames;
    qint64 m_capacity = 0;
    int m_count = 0;
    QVector3D m_center;
    float m_radius = 1;
};
