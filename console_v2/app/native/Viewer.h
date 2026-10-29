#pragma once
#include <QQuick3DGeometry>
#include <QJsonObject>
#include <QDateTime>
#include <QHash>
#include <QString>
#include <QVariantList>
#include <QVariantMap>
#include <QVector>
#include <QVector3D>
#include <QQuaternion>
#include <algorithm>
#include <array>
#include <cfloat>
#include <cmath>
#include <functional>
#include <vector>

// 深度着色固定标尺：径向距离 0.1–8 m（与 2D 距离图同语义），图例必须引用同一对常量。
static constexpr float kDepthColorMinM=0.1f;
static constexpr float kDepthColorMaxM=8.0f;

class CloudGeometry final : public QQuick3DGeometry {
    Q_OBJECT
    // 当前着色实际使用的范围（图例直接读它，不另算一份）：
    // mode / applied / perFrame / lo / hi / reason / points。
    Q_PROPERTY(QVariantMap colorRange READ colorRange NOTIFY colorRangeChanged)
public:
    // 默认 stride + Position 属性：QML 里 geometry 在首帧到达前就会被渲染一次，
    // 不给默认值 Qt 会打 “0 is an invalid stride”（每个 geometry 一条）。
    explicit CloudGeometry(QQuick3DObject *parent=nullptr):QQuick3DGeometry(parent) {
        setStride(12);addAttribute(Attribute::PositionSemantic,0,Attribute::F32Type);
    }
    QVariantMap colorRange() const { return range; }
    // mode 0=单色 1=深度(径向距离0.1–8m,红近蓝远) 2=高度(逐帧z范围) 3=反射(逐帧强度范围)。
    // 着色经 UV 采 256×1 渐变纹理（image://colormap），用原生 DefaultMaterial，免自定义着色器。
    void submit(const QByteArray &scene,const QByteArray &intensity,int mode) {
        clear(); setPrimitiveType(PrimitiveType::Points);
        // Source coordinates are validated by the C# adapter; renderer owns a deep copy.
        setBounds(QVector3D(-10000,-10000,-10000),QVector3D(10000,10000,10000));
        const qsizetype n=scene.size()/12;
        if(n==0) {
            setStride(12); addAttribute(Attribute::PositionSemantic,0,Attribute::F32Type);
            publishRange(mode,false,false,0,0,"empty_frame",0);
            update(); return;
        }
        // 只有反射（mode 3）依赖强度字段：深度用半径、高度用 Z，缺强度不影响它们。
        if(mode<=0 || (mode==3 && intensity.size()<n*4)) {
            setStride(12);
            addAttribute(Attribute::PositionSemantic,0,Attribute::F32Type);
            setVertexData(scene);
            // 单色不是“范围”，反射缺强度字段时明确回退，图例据此说明而不是假装有色带。
            publishRange(mode,mode<=0,false,0,0,mode==3?QStringLiteral("intensity_unavailable"):QString(),n);
            update(); return;
        }
        const float *in=reinterpret_cast<const float*>(scene.constData());
        const float *it=reinterpret_cast<const float*>(intensity.constData());
        float lo=FLT_MAX,hi=-FLT_MAX;
        // 深度的范围是固定常量，不必扫强度（也不读 it，避免无强度帧越界）。
        if(mode!=1)for(qsizetype i=0;i<n;i++) {
            const float v=(mode==2)?in[i*3+2]:it[i];
            lo=std::min(lo,v);hi=std::max(hi,v);
        }
        QByteArray mapped;mapped.resize(n*20);
        float *out=reinterpret_cast<float*>(mapped.data());
        for(qsizetype i=0;i<n;i++) {
            float t;
            if(mode==1) {
                const float r=std::sqrt(in[i*3]*in[i*3]+in[i*3+1]*in[i*3+1]+in[i*3+2]*in[i*3+2]);
                t=std::clamp((r-kDepthColorMinM)/(kDepthColorMaxM-kDepthColorMinM),0.0f,1.0f);
            } else t=(hi>lo)?std::clamp(((mode==2)?in[i*3+2]:it[i])-lo,0.0f,hi-lo)/(hi-lo):0.5f;
            out[i*5]=in[i*3];out[i*5+1]=in[i*3+1];out[i*5+2]=in[i*3+2];out[i*5+3]=t;out[i*5+4]=0.5f;
        }
        setStride(20);
        addAttribute(Attribute::PositionSemantic,0,Attribute::F32Type);
        addAttribute(Attribute::TexCoordSemantic,12,Attribute::F32Type);
        setVertexData(mapped);
        if(mode==1)publishRange(mode,true,false,double(kDepthColorMinM),double(kDepthColorMaxM),QString(),n);
        else publishRange(mode,true,true,double(lo),double(hi),QString(),n);
        update();
    }
signals:
    void colorRangeChanged();
private:
    QVariantMap range;
    void publishRange(int mode,bool applied,bool perFrame,double lo,double hi,const QString &reason,qsizetype points) {
        QVariantMap next{{"mode",mode},{"applied",applied},{"perFrame",perFrame},
                         {"lo",lo},{"hi",hi},{"reason",reason},{"points",double(points)}};
        if(next==range)return;
        range=next;
        emit colorRangeChanged();
    }
};

class SkeletonGeometry final : public QQuick3DGeometry {
    Q_OBJECT
public:
    explicit SkeletonGeometry(QQuick3DObject *parent=nullptr):QQuick3DGeometry(parent) {
        setStride(12);addAttribute(Attribute::PositionSemantic,0,Attribute::F32Type);
    }
    void submit(const QVariantMap &skeleton, bool nodesOnly=false) {
        clear();setStride(12);
        setPrimitiveType(nodesOnly?PrimitiveType::Points:PrimitiveType::Lines);
        addAttribute(Attribute::PositionSemantic,0,Attribute::F32Type);
        const QVariantMap nodes=skeleton.value("nodes").toMap();
        QByteArray bytes;
        QVector3D lo(FLT_MAX,FLT_MAX,FLT_MAX),hi(-FLT_MAX,-FLT_MAX,-FLT_MAX);
        const auto put=[&](const QString &key) {
            const QVariantList xyz=nodes.value(key).toMap().value("xyz").toList();
            if(xyz.size()!=3)return;
            const float p[3]={xyz[0].toFloat(),xyz[1].toFloat(),xyz[2].toFloat()};
            for(int i=0;i<3;i++){lo[i]=std::min(lo[i],p[i]);hi[i]=std::max(hi[i],p[i]);}
            bytes.append(reinterpret_cast<const char*>(p),12);
        };
        if(nodesOnly) {for(auto it=nodes.cbegin();it!=nodes.cend();++it)put(it.key());}
        else for(const QVariant &edge:skeleton.value("edges").toList()) {
            const auto ends=edge.toList();
            if(ends.size()==2 && nodes.contains(ends[0].toString()) && nodes.contains(ends[1].toString())) {
                put(ends[0].toString());put(ends[1].toString());
            }
        }
        if(!bytes.isEmpty())setBounds(lo,hi);
        setVertexData(bytes);update();
    }
};

class BoxGeometry final : public QQuick3DGeometry {
    Q_OBJECT
public:
    explicit BoxGeometry(QQuick3DObject *parent=nullptr):QQuick3DGeometry(parent) {
        setStride(12);addAttribute(Attribute::PositionSemantic,0,Attribute::F32Type);
    }
    void submit(const QVariantMap &box) {
        clear(); setStride(12);
        addAttribute(Attribute::PositionSemantic,0,Attribute::F32Type);
        if(box.isEmpty()) { update(); return; }
        const float x=box["x"].toFloat(),y=box["y"].toFloat(),w=box["w"].toFloat(),h=box["h"].toFloat();
        const float z0=box["zMin"].toFloat(),z1=box["zMax"].toFloat();
        const QVector3D lo(x-w/2,y-h/2,z0),hi(x+w/2,y+h/2,z1);
        QByteArray bytes;
        for(int a=0;a<8;a++)for(int bit=0;bit<3;bit++)if(!(a&(1<<bit))) {
            for(int vertex:{a,a|(1<<bit)}) {
                const float p[3]={(vertex&1)?hi.x():lo.x(),(vertex&2)?hi.y():lo.y(),(vertex&4)?hi.z():lo.z()};
                bytes.append(reinterpret_cast<const char*>(p),12);
            }
        }
        setStride(12);setPrimitiveType(PrimitiveType::Lines);
        setBounds(lo,hi);setVertexData(bytes);update();
    }
};

// 配平框只用于显示：对同帧目标点做与场景一致的旋转，再计算世界轴对齐包围盒。
class LevelBoxGeometry final : public QQuick3DGeometry {
    Q_OBJECT
public:
    explicit LevelBoxGeometry(QQuick3DObject *parent=nullptr):QQuick3DGeometry(parent) {
        setStride(12);addAttribute(Attribute::PositionSemantic,0,Attribute::F32Type);
    }
    void submit(const QByteArray &points) { m_points=points; rebuild(); }
    Q_INVOKABLE void setRotation(const QQuaternion &rotation) { m_rotation=rotation; rebuild(); }
private:
    QByteArray m_points;
    QQuaternion m_rotation;
    void rebuild() {
        clear();setStride(12);setPrimitiveType(PrimitiveType::Lines);
        addAttribute(Attribute::PositionSemantic,0,Attribute::F32Type);
        QVector3D lo(FLT_MAX,FLT_MAX,FLT_MAX),hi(-FLT_MAX,-FLT_MAX,-FLT_MAX);
        qsizetype count=0;
        const float *in=reinterpret_cast<const float*>(m_points.constData());
        for(qsizetype i=0;i<m_points.size()/12;i++,in+=3) {
            if(!std::isfinite(in[0]) || !std::isfinite(in[1]) || !std::isfinite(in[2]))continue;
            const QVector3D p=m_rotation.rotatedVector(QVector3D(in[0],in[2],-in[1]));
            for(int j=0;j<3;j++){lo[j]=std::min(lo[j],p[j]);hi[j]=std::max(hi[j],p[j]);}
            count++;
        }
        if(!count){update();return;}
        QByteArray bytes;
        for(int a=0;a<8;a++)for(int bit=0;bit<3;bit++)if(!(a&(1<<bit))) {
            for(int vertex:{a,a|(1<<bit)}) {
                const float p[3]={(vertex&1)?hi.x():lo.x(),(vertex&2)?hi.y():lo.y(),(vertex&4)?hi.z():lo.z()};
                bytes.append(reinterpret_cast<const char*>(p),12);
            }
        }
        setBounds(lo,hi);setVertexData(bytes);update();
    }
};

// 用户框选：QML 用相机 mapToViewport 探针标定投影模型（纯经验标定，不依赖
// Quick3D 欧拉角/深度约定），C++ 对每帧点云按同一模型重投影并收集矩形内点。
// 框是传感器坐标系里的固定视锥，旋转/缩放视角后仍逐帧跟踪框内目标。
class RectSelection final : public QObject {
    Q_OBJECT
    Q_PROPERTY(QVariantMap info READ info NOTIFY changed)
public:
    QVariantMap infoMap;   // 冒烟自检直接读取
    // params: F(3) u0 v0 a(3) b(3) c(3) D rect(4) —— u(P)=u0+a·(P-F)/(D·(D+c·(P-F)))，v 同理
    Q_INVOKABLE void apply(const QVariantList &params) {
        if(params.size()!=19) { qWarning("RectSelection.apply: expected 19 numbers"); return; }
        for(int i=0;i<19;i++)m_params[size_t(i)]=params[i].toDouble();
        active=true;
        reselect();
    }
    Q_INVOKABLE void clear() {
        active=false;
        infoMap.clear();
        emit changed();
        emit targetReady(QByteArray(),QVariantMap());
    }
    void setFrame(const QByteArray &scene) {
        frame=scene;
        if(active)reselect();
    }
    QVariantMap info() const { return infoMap; }
signals:
    void changed();
    void targetReady(const QByteArray &target,const QVariantMap &box);
private:
    void reselect() {
        infoMap.clear();
        QByteArray chosen;
        const qsizetype total=frame.size()/12;
        if(total>0) {
            QByteArray kept;
            kept.resize(frame.size());
            const float *in=reinterpret_cast<const float*>(frame.constData());
            float *out=reinterpret_cast<float*>(kept.data());
            const double fx=m_params[0],fy=m_params[1],fz=m_params[2];
            const double u0=m_params[3],v0=m_params[4],dist=m_params[14];
            const double x0=m_params[15],y0=m_params[16],x1=m_params[17],y1=m_params[18];
            qsizetype count=0;
            float lo[3]={FLT_MAX,FLT_MAX,FLT_MAX},hi[3]={-FLT_MAX,-FLT_MAX,-FLT_MAX};
            std::vector<float> heights;
            for(qsizetype i=0;i<total;i++,in+=3) {
                const double dx=in[0]-fx,dy=in[1]-fy,dz=in[2]-fz;
                const double w=dist+m_params[11]*dx+m_params[12]*dy+m_params[13]*dz;
                if(w<=0.0)continue;  // 相机平面之后的点投影镜像，不计入
                const double den=dist*w;
                const double u=u0+(m_params[5]*dx+m_params[6]*dy+m_params[7]*dz)/den;
                if(u<x0||u>x1)continue;
                const double v=v0+(m_params[8]*dx+m_params[9]*dy+m_params[10]*dz)/den;
                if(v<y0||v>y1)continue;
                out[count*3]=in[0];out[count*3+1]=in[1];out[count*3+2]=in[2];
                for(int a=0;a<3;a++){lo[a]=std::min(lo[a],in[a]);hi[a]=std::max(hi[a],in[a]);}
                heights.push_back(in[2]);
                count++;
            }
            if(count>0) {
                kept.truncate(count*12);
                chosen=kept;
                std::nth_element(heights.begin(),heights.begin()+std::ptrdiff_t(heights.size()/2),heights.end());
                QVariantMap box;
                box.insert("x",(lo[0]+hi[0])/2.0);box.insert("y",(lo[1]+hi[1])/2.0);
                box.insert("w",hi[0]-lo[0]);box.insert("h",hi[1]-lo[1]);
                box.insert("zMin",lo[2]);box.insert("zMax",hi[2]);
                infoMap.insert("count",int(count));
                infoMap.insert("heightMedianM",double(heights[heights.size()/2]));
                infoMap.insert("box",box);
            } else {
                infoMap.insert("count",0);
                infoMap.insert("heightMedianM",QVariant());
                infoMap.insert("box",QVariantMap());
            }
        } else {
            infoMap.insert("count",0);
            infoMap.insert("heightMedianM",QVariant());
            infoMap.insert("box",QVariantMap());
        }
        emit changed();
        emit targetReady(chosen,infoMap.value("box").toMap());
    }
    std::array<double,19> m_params {};
    bool active=false;
    QByteArray frame;
};

class Viewer final : public QObject {
    Q_OBJECT
    Q_PROPERTY(QVariantMap snapshot READ snapshot NOTIFY changed)
    Q_PROPERTY(QVariantMap joint READ joint NOTIFY changed)
    Q_PROPERTY(QVariantMap gt READ gt NOTIFY gtChanged)
    Q_PROPERTY(QVariantMap video READ video NOTIFY videoChanged)
    Q_PROPERTY(QVariantList sessions READ sessions NOTIFY changed)
    Q_PROPERTY(QString status READ status NOTIFY changed)
    Q_PROPERTY(bool playing READ playing NOTIFY changed)
    Q_PROPERTY(int colorMode READ colorMode WRITE setColorMode NOTIFY colorModeChanged)
    Q_PROPERTY(QVariantMap deleteManifest READ deleteManifest WRITE setDeleteManifest NOTIFY changed)
    // 就近错误提示：按命令序号（seq）归因，最近一次失败（含通道/动作/次数）与按通道索引的记录。
    Q_PROPERTY(QVariantMap alert READ alert NOTIFY alertChanged)
    Q_PROPERTY(QVariantMap alerts READ alerts NOTIFY alertChanged)
    Q_PROPERTY(int staleReplies READ staleReplies NOTIFY alertChanged)
    Q_PROPERTY(int expiredCommands READ expiredCommands NOTIFY alertChanged)
    // 绑定的地面（只读，仅用于显示配平）：正常未绑定或绑定与会话不符时 available=false。
    Q_PROPERTY(QVariantMap ground READ ground NOTIFY groundChanged)
    Q_PROPERTY(QVariantMap localTask READ localTask NOTIFY changed)
public:
    // 一条通道（会话 / 实时 / 录制 / 标注 / 回放）上的失败记录。
    // 30 s 滑动窗口：窗口内 >=3 次才算持续故障；窗口滑走后自动降级，不靠“再失败一次”刷新。
    struct AlertRecord {
        static constexpr qint64 kWindowMs=30000;
        QString channel, action, op, text;
        QVector<qint64> times;      // 只保留窗口附近的失败时刻，用于滑动窗口判定
        int count=0;                // 自上次成功/清除以来的累计次数（“第 N 次”）
        qint64 firstAtMs=0, lastAtMs=0;
        int recentCount(qint64 now) const {
            int n=0;
            for(qint64 t:times)if(now-t<=kWindowMs)n++;
            return n;
        }
        QString state(qint64 now) const {
            if(count<=0)return "none";
            return recentCount(now)>=3 ? "persistent" : "recoverable";
        }
        QVariantMap toMap(qint64 now) const {
            return QVariantMap{{"state",state(now)},{"channel",channel},{"action",action},{"op",op},
                               {"text",text},{"count",count},{"recent",recentCount(now)},
                               {"firstAtMs",double(firstAtMs)},{"lastAtMs",double(lastAtMs)}};
        }
    };
    std::function<void(const QJsonObject &)> send;
    QVariantMap data, jointData, videoData, gtData, groundData, localTaskData;
    QVariantList sessionData;
    QString message;
    QString offlinePreviewPath;
    bool isPlaying=false;
    int mode=0;
    QVariantMap manifest;
    QHash<QString,AlertRecord> alertRecords;
    // 每条被归因的命令拿一个 seq 随命令发出，服务端在终止回包里原样带回；回包按 seq 结算，
    // 不再靠“最后一条命令”猜。poll（后台轮询）也登记，但它的回包不结算、不报错。
    struct PendingReply { QString channel, op; qint64 atMs=0; };
    QHash<qint64,PendingReply> pending;
    qint64 nextSeq=1;
    int stale=0, expired=0;
    QVariantMap snapshot() const { return data; }
    QVariantMap joint() const { return jointData; }
    QVariantMap gt() const { return gtData; }
    QVariantMap ground() const { return groundData; }
    QVariantMap localTask() const { return localTaskData; }
    QVariantMap video() const { return videoData; }
    QVariantList sessions() const { return sessionData; }
    QString status() const { return message; }
    bool playing() const { return isPlaying; }
    int colorMode() const { return mode; }
    void setColorMode(int value) { if(value==mode||value<0||value>3)return; mode=value; emit colorModeChanged(); }
    QVariantMap deleteManifest() const { return manifest; }
    void setDeleteManifest(const QVariantMap &value) { manifest=value; }
    Q_INVOKABLE void command(const QVariantMap &value) { if(send) send(QJsonObject::fromVariantMap(value)); }
    void notify() { emit changed(); }

    // ---- 错误归因：命令带通道与“期待回包”计数，回包只按终止消息结算 ----
    static QString channelOf(const QString &op) {
        static const QHash<QString,QString> table{
            {"open","session"},{"rename","session"},{"deleteProbe","session"},{"deleteConfirm","session"},
            {"liveConnect","live"},{"liveDisconnect","live"},
            {"localAnalysisToggle","replay"},{"localAnalysisRun","replay"},{"localGroundFit","replay"},{"localOfflinePreview","replay"},
            {"jointStart","joint"},{"jointStop","joint"},{"jointStatus","joint"},{"jointPreview","joint"},
            {"annotate","annotation"},{"gtLoad","annotation"},{"gtSave","annotation"},
            {"play","replay"},{"pause","replay"},{"step","replay"},{"seek","replay"},{"speed","replay"}};
        return table.value(op);
    }
    static QString actionOf(const QString &op) {
        static const QHash<QString,QString> table{
            {"open","打开会话"},{"rename","修改会话名称"},{"deleteProbe","查看删除清单"},{"deleteConfirm","删除会话"},
            {"liveConnect","连接实时"},{"liveDisconnect","断开实时"},
            {"jointStart","开始联合录制"},{"jointStop","停止录制"},{"jointStatus","刷新录制状态"},{"jointPreview","开启相机预览"},
            {"annotate","打开网页标注台"},{"gtLoad","载入标注"},{"gtSave","保存标注"},
            {"play","播放"},{"pause","暂停"},{"step","逐帧"},{"seek","跳转"},{"speed","切换倍速"}};
        return table.value(op,QString::fromUtf8("操作"));
    }
    // ack/quit/video* 不发可归因的回包，不参与归因，避免每帧 ack 覆盖真正的失败。
    static bool expectsReply(const QString &op) { return !channelOf(op).isEmpty(); }
    static qint64 nowMs() { return QDateTime::currentMSecsSinceEpoch(); }
    // 超时未结算的命令（回包丢了）到期后不再占位：否则该通道的下一条真实错误会被当成迟到回包。
    static constexpr qint64 kPendingTtlMs=30000;
    void prunePending(qint64 now) {
        for(auto it=pending.begin();it!=pending.end();) {
            if(now-it->atMs>kPendingTtlMs) {expired++;it=pending.erase(it);}
            else ++it;
        }
    }
    // 给需要回包的命令分配 seq 并写回命令本身。后台轮询（USB 页每秒 jointStatus）不带 seq：
    // 它的回包既不能结算用户动作，也不会把录制服务的失败记到别的通道上。
    bool noteSent(QJsonObject &command) {
        const QString op=command.value("op").toString();
        if(command.value("poll").toBool())return false;
        if(!expectsReply(op))return false;
        const qint64 now=nowMs();
        prunePending(now);
        const qint64 seq=nextSeq++;
        command.insert("seq",seq);
        PendingReply item;
        item.channel=channelOf(op);item.op=op;item.atMs=now;
        pending.insert(seq,item);
        return true;
    }
    // 只认服务端回声的 seq：没有 seq 的消息（sessions / video / 未请求的状态）不参与归因，也不计 stale。
    // seq 找不到（迟到 / 无主 / 重复）只计数，不覆盖界面上更新的状态。
    void noteReply(const QJsonObject &reply) {
        // 只认服务端回声的 seq（必须是数字）：没有 seq 的消息（sessions / video / 轮询的 joint）不参与归因。
        const QJsonValue seqValue=reply.value("seq");
        if(!seqValue.isDouble())return;
        const qint64 seq=seqValue.toInteger(-1);
        const qint64 now=nowMs();
        prunePending(now);
        auto it=pending.find(seq);
        if(it==pending.end()) {stale++;emit alertChanged();return;}
        const PendingReply item=*it;
        pending.erase(it);
        if(reply.value("type").toString()=="error") {
            recordFailure(item.channel,item.op,reply.value("message").toString());
            emit alertChanged();
            return;
        }
        // 成功回包只清它自己通道的提示：一条成功动作可以证明该通道恢复了。
        if(alertRecords.remove(item.channel))emit alertChanged();
    }
    void recordFailure(const QString &channel,const QString &op,const QString &text) {
        const qint64 now=nowMs();
        AlertRecord &record=alertRecords[channel];
        QVector<qint64> kept;
        for(qint64 t:record.times)if(now-t<=AlertRecord::kWindowMs)kept.push_back(t);
        kept.push_back(now);
        record.times=kept;
        if(record.count==0)record.firstAtMs=now;
        record.count++;
        record.lastAtMs=now;
        record.channel=channel;
        record.op=op;
        record.action=actionOf(op);
        record.text=text;
    }
    QVariantMap alert() const {
        const qint64 now=nowMs();
        const AlertRecord *latest=nullptr;
        for(auto it=alertRecords.cbegin();it!=alertRecords.cend();++it)
            if(!latest || it->lastAtMs>latest->lastAtMs)latest=&*it;
        if(!latest)return QVariantMap{{"state","none"}};
        return latest->toMap(now);
    }
    QVariantMap alerts() const {
        const qint64 now=nowMs();
        QVariantMap out;
        for(auto it=alertRecords.cbegin();it!=alertRecords.cend();++it)out.insert(it.key(),it->toMap(now));
        return out;
    }
    int staleReplies() const { return stale; }
    int expiredCommands() const { return expired; }
    Q_INVOKABLE void clearAlert(const QString &channel) {
        if(alertRecords.remove(channel))emit alertChanged();
    }
    Q_INVOKABLE void clearAllAlerts() {
        if(alertRecords.isEmpty())return;
        alertRecords.clear();
        emit alertChanged();
    }
signals:
    void changed();
    void colorModeChanged();
    void videoChanged();
    void gtChanged();
    void alertChanged();
    void groundChanged();
};
