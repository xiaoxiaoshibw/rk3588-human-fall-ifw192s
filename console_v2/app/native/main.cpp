#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <QGuiApplication>
#include <QKeySequence>
#include <QtTest/QTest>
#include <QQmlApplicationEngine>
#include <QQmlContext>
#include <QQuickWindow>
#include <QQuickStyle>
#include <QLocalSocket>
#include <QtEndian>
#include <QJsonDocument>
#include <QJsonArray>
#include <QCryptographicHash>
#include <QTimer>
#include <QImage>
#include <QQuickImageProvider>
#include <QQmlEngine>
#include <QFileInfo>
#include <QDir>
#include <QElapsedTimer>
#include <QFileSystemWatcher>
#include <QFile>
#include <QDesktopServices>
#include <QVector4D>
#include <QQuaternion>
#include <QAccessible>
#include <memory>
#include <stdexcept>
#include "Viewer.h"
#include "AnnotationView.h"
#include "CameraChecks.h"
#include "WorkspaceChecks.h"
#include "Preview.h"
#include "MediaChecks.h"

class DepthImages final : public QQuickImageProvider {
public:
    DepthImages():QQuickImageProvider(QQuickImageProvider::Image){}
    QImage current;
    QImage requestImage(const QString &,QSize *size,const QSize &) override {
        if(size)*size=current.size();
        return current;
    }
};

// 自检用的普通函数：不捕获任何外部状态，参数显式传窗口，避免把 lambda 引用跨层嵌套。
static QQuickItem *namedItem(QQuickWindow *window,const char *name) {
    return window?window->findChild<QQuickItem*>(name):nullptr;
}
static QObject *namedObject(QQuickWindow *window,const char *name) {
    return window?window->findChild<QObject*>(name):nullptr;
}
static QString namedText(QQuickWindow *window,const char *name) {
    QObject *object=namedObject(window,name);
    return object?object->property("text").toString():QString();
}
static bool namedVisible(QQuickWindow *window,const char *name) {
    QQuickItem *item=namedItem(window,name);
    return item && item->isVisible();
}
// 已经实例化并可见的会话行（objectName 带 sid）；只读实际渲染出来的 delegate。
// ListView 的官方读取接口：count 是模型条数，itemAtIndex 返回已实例化的行。
static int sessionCount(QQuickWindow *window) {
    QObject *list=namedObject(window,"sessionList");
    return list?list->property("count").toInt():-1;
}
static QQuickItem *sessionRowAt(QQuickWindow *window,int index) {
    QObject *list=namedObject(window,"sessionList");
    QQuickItem *row=nullptr;
    if(!list || index<0)return nullptr;
    if(!QMetaObject::invokeMethod(list,"itemAtIndex",Q_RETURN_ARG(QQuickItem*,row),Q_ARG(int,index)))return nullptr;
    return row;
}
static QString rowSessionKey(QQuickItem *row,const QVariantList &sessions) {
    if(!row)return QString();
    const QVariantMap data=row->property("modelData").toMap();
    if(!data.value("id").toString().isEmpty())return data.value("id").toString();
    const QString label=row->property("accessibleLabel").toString();
    for(const QVariant &entry:sessions) {
        const QString id=entry.toMap().value("id").toString();
        if(!id.isEmpty() && label.contains(id))return id;
    }
    return QString();
}
static QList<QQuickItem*> sessionRows(QQuickWindow *window) {
    QList<QQuickItem*> rows;
    const int count=sessionCount(window);
    for(int index=0;index<count;index++) {
        QQuickItem *row=sessionRowAt(window,index);
        if(row)rows.append(row);
    }
    return rows;
}
static QQuickItem *sessionRowFor(QQuickWindow *window,const QVariantList &sessions,const QString &sid) {
    for(auto *row:sessionRows(window))
        if(rowSessionKey(row,sessions)==sid)return row;
    return nullptr;
}
// 按 QML 同一规则（名称或编号包含、忽略大小写）独立算一遍期望的过滤结果。
// ---- 巡检/告警自检用的自由函数：不捕获任何状态，窗口或 Viewer 显式传入 ----
static QString shortcutSequence(QQuickWindow *window,const char *name) {
    QObject *shortcut=namedObject(window,name);
    if(!shortcut)return QString("missing");
    return shortcut->property("sequence").value<QKeySequence>().toString(QKeySequence::PortableText);
}
static int sectionOf(QQuickWindow *window) {
    return window?window->property("section").toInt():-1;
}
// QTest 只有 QWidget 版 keyClicks；QWindow 上按字符逐个发真实按键事件。
static void typeInto(QQuickWindow *window,const QString &text) {
    if(!window)throw std::runtime_error("no window for typing");
    for(const QChar &ch:text)QTest::keyClick(window,ch.toLatin1());
}
// 3D 坐标轴方向：走 QML 的 axisDirections（相机 mapToViewport 实测投影）。
static std::array<QVector4D,3> axisDirectionVectors(QQuickWindow *window) {
    QVariant result;
    if(!window || !QMetaObject::invokeMethod(window,"axisDirections",Q_RETURN_ARG(QVariant,result)))
        throw std::runtime_error("axisDirections not invokable");
    const QVariantMap dirs=result.toMap();
    const auto one=[&](const char *key) {
        const QVariantList values=dirs.value(QString::fromLatin1(key)).toList();
        if(values.size()!=4)throw std::runtime_error("axisDirections missing axes");
        return QVector4D(values[0].toFloat(),values[1].toFloat(),values[2].toFloat(),values[3].toFloat());
    };
    return std::array<QVector4D,3>{one("x"),one("y"),one("z")};
}
// 与着色计算对照用的真实范围（当前帧原始字节），不是从图例反读。
static QPointF sceneRange(const QByteArray &xyz,const QByteArray &intensity,bool height) {
    const QByteArray &bytes=height?xyz:intensity;
    double lo=DBL_MAX,hi=-DBL_MAX;
    if(height) {
        const float *data=reinterpret_cast<const float*>(bytes.constData());
        for(qsizetype i=0;i<bytes.size()/12;i++) {const double v=data[i*3+2];lo=std::min(lo,v);hi=std::max(hi,v);}
    } else {
        const float *data=reinterpret_cast<const float*>(bytes.constData());
        for(qsizetype i=0;i<bytes.size()/4;i++) {const double v=data[i];lo=std::min(lo,v);hi=std::max(hi,v);}
    }
    return QPointF(lo,hi);
}
// 就近提示与真实点击（自检用）。
static QString hintTextOf(QQuickWindow *window,const char *alertName) {
    QQuickItem *hint=namedItem(window,alertName);
    QQuickItem *label=hint?hint->findChild<QQuickItem*>("alertText"):nullptr;
    return label?label->property("text").toString():QString("missing");
}
static void clickWindowItem(QQuickWindow *window,QQuickItem *item) {
    if(!window || !item || !item->isVisible() || !item->isEnabled())
        throw std::runtime_error("Unavailable control");
    // 与 workspaceClick 一致：直接投递到窗口（巡检窗口是 WindowTransparentForInput，
    // 走 QWindowSystemInterface 的 QTest 鼠标事件会被丢掉）。
    const QPointF at=item->mapToScene(QPointF(item->width()/2,item->height()/2));
    for(auto type:{QEvent::MouseButtonPress,QEvent::MouseButtonRelease}) {
        QMouseEvent event(type,at,window->mapToGlobal(at.toPoint()),Qt::LeftButton,
            type==QEvent::MouseButtonPress?Qt::LeftButton:Qt::NoButton,Qt::NoModifier);
        QCoreApplication::sendEvent(window,&event);
    }
}
static void clickAlertClear(QQuickWindow *window,const char *alertName) {
    QQuickItem *hint=namedItem(window,alertName);
    clickWindowItem(window,hint?hint->findChild<QQuickItem*>("alertClear"):nullptr);
}
// 配平后地面法向与世界竖直的夹角（度）；0 = 已配平。
static double levelResidualOf(QQuickWindow *window) {
    QVariant result;
    if(!window || !QMetaObject::invokeMethod(window,"levelResidual",Q_RETURN_ARG(QVariant,result)))return -1.0;
    return result.toDouble();
}
static QVariantMap alertFor(const Viewer &viewer,const char *channel) {
    return viewer.alerts().value(QString::fromLatin1(channel)).toMap();
}
static QJsonObject commandOf(const QString &op) {
    QJsonObject command;
    command.insert(QStringLiteral("op"),QJsonValue(op));
    return command;
}
// 回包必须带服务端回声的 seq 才参与归因；不带 seq 的迟到/无主回包由 noteReply 只计数。
static QJsonObject errorReplyOf(qint64 seq,const QString &text) {
    QJsonObject reply;
    reply.insert(QStringLiteral("type"),QJsonValue(QStringLiteral("error")));
    reply.insert(QStringLiteral("message"),QJsonValue(text));
    reply.insert(QStringLiteral("seq"),QJsonValue(seq));
    return reply;
}
static QJsonObject okReplyOf(qint64 seq) {
    QJsonObject reply;
    reply.insert(QStringLiteral("type"),QJsonValue(QStringLiteral("status")));
    reply.insert(QStringLiteral("seq"),QJsonValue(seq));
    return reply;
}

static QVariantList filteredSessionIds(const QVariantList &sessions,const QString &query) {
    const QString needle=query.trimmed().toLower();
    QVariantList ids;
    for(const QVariant &entry:sessions) {
        const QVariantMap item=entry.toMap();
        if(needle.length()) {
            const QString haystack=(item.value("name").toString()+" "+item.value("id").toString()).toLower();
            if(!haystack.contains(needle))continue;
        }
        ids.append(item.value("id").toString());
    }
    return ids;
}

int main(int argc,char **argv) {
    QGuiApplication app(argc,argv);
    QQuickStyle::setStyle("Fusion");
    qmlRegisterType<AnnotationView>("ConsoleV2",1,0,"AnnotationView");
    const auto args=app.arguments();
    const auto option=[&](const QString &key){int i=args.indexOf(key);return i>=0&&i+1<args.size()?args[i+1]:QString();};
    HANDLE mapping=nullptr;const char *view=nullptr;
    int result=2;
    try {
        // QLocalSocket uses asynchronous named-pipe IO on Windows: no GUI-thread WriteFile.
        QLocalSocket socket;
        socket.connectToServer(option("--pipe"));
        if(!socket.waitForConnected(15000))throw std::runtime_error("Service connection failed");
        QByteArray pending;
        const auto messageSize=[&]()->quint32 {
            if(pending.size()<4)return 0;
            const quint32 n=qFromLittleEndian<quint32>(reinterpret_cast<const uchar*>(pending.constData()));
            if(n<2 || n>1024*1024)throw std::runtime_error("Invalid service message length");
            return n;
        };
        // The only blocking wait happens before creating a window.
        do {
            if(!socket.waitForReadyRead(15000))throw std::runtime_error("Service hello timed out");
            pending+=socket.readAll();
        } while(pending.size()<4 || pending.size()<messageSize()+4);
        const quint32 helloSize=messageSize();
        const QJsonObject hello=QJsonDocument::fromJson(pending.mid(4,helloSize)).object();
        pending.remove(0,helloSize+4);
        const qint64 capacity=hello["capacity"].toInteger();
        if(hello["type"]!="hello" || hello["version"].toInt()!=1 || capacity<=0 || capacity>12000000)
            throw std::runtime_error("Invalid app protocol");
        const QString mapName=hello["map"].toString();
        mapping=OpenFileMappingW(FILE_MAP_READ,FALSE,reinterpret_cast<LPCWSTR>(mapName.utf16()));
        if(!mapping)throw std::runtime_error("Mapping open failed");
        view=static_cast<const char*>(MapViewOfFile(mapping,FILE_MAP_READ,0,0,SIZE_T(capacity)));
        if(!view)throw std::runtime_error("Mapping view failed");
        Viewer ui;CloudGeometry cloud,target,picked;BoxGeometry box,pickedBox;LevelBoxGeometry levelBox;RectSelection pick;CameraPreview preview;
        SkeletonGeometry skeleton,skeletonNodes;
        bool closing=false;
        qint64 replayCommands=0;
        double seekBurstEnqueueMs=-1;
        QByteArray currentScene,currentIntensity;
        const auto applyCloud=[&]{ cloud.submit(currentScene,currentIntensity,ui.colorMode()); };
        QObject::connect(&ui,&Viewer::colorModeChanged,&ui,applyCloud);
        QObject::connect(&pick,&RectSelection::targetReady,&ui,
            [&](const QByteArray &target,const QVariantMap &box) {picked.submit(target,{},0);pickedBox.submit(box);});
        ui.send=[&](QJsonObject message) {
            if(closing)return;
            if(QStringList{"play","pause","step","seek"}.contains(message["op"].toString()))replayCommands++;
            // 归因：noteSent 给命令写入 seq（轮询不写），服务端在终止回包里带回，回包按 seq 结算。
            ui.noteSent(message);
            if(socket.bytesToWrite()>512*1024) {ui.message="命令积压，连接已停止";ui.notify();app.exit(2);return;}
            const QByteArray bytes=QJsonDocument(message).toJson(QJsonDocument::Compact)+'\n';
            if(socket.write(bytes)!=bytes.size())app.exit(2);
        };
        ui.sessionData=hello["sessions"].toArray().toVariantList();
        // 绑定的地面文件（只读）：只用于“配平视图”的显示旋转，不改点云、不改判定。
        {
            const QString groundPath=option("--ground");
            QVariantMap ground{{"available",false},{"reason",QStringLiteral("no_ground_file")}};
            if(!groundPath.isEmpty()) {
                QFile file(groundPath);
                if(!file.open(QIODevice::ReadOnly))ground.insert("reason",QStringLiteral("ground_unreadable"));
                else {
                    const QJsonDocument document=QJsonDocument::fromJson(file.readAll());
                    const QJsonObject object=document.object();
                    const QJsonArray normal=object.value("normal").toArray();
                    if(!document.isObject() || normal.size()!=3 || object.value("status").toString()!="valid")
                        ground.insert("reason",QStringLiteral("ground_invalid"));
                    else {
                        ground.insert("available",true);
                        ground.insert("reason",QString());
                        ground.insert("normal",QVariantList{normal[0].toDouble(),normal[1].toDouble(),normal[2].toDouble()});
                        ground.insert("offsetM",object.value("offset_m").toDouble());
                        ground.insert("sessionId",object.value("binding").toObject().value("session").toString());
                        ground.insert("frame",object.value("frame").toString());
                    }
                }
            }
            ui.groundData=ground;
        }
        ui.jointData.insert("configured",hello["jointConfigured"].toBool());
        const QString qmlFile=option("--qml-file");
        std::unique_ptr<QQmlApplicationEngine> engine;
        QQuickWindow *window=nullptr;
        int reloads=0;
        QVariantMap cameraState;
        QByteArray loadedQml;
        QImage currentDepth;
        QVariantMap liveGroundBinding;
        QString depthUrl, depthSession;
        int depthFrame=-1, depthRotation=0;
        qint64 depthSubmission=0, lastSubmission=0;
        QImage currentVideo;
        AnnotationView *annotationView=nullptr;
        qint64 videoRevision=0;
        qint64 frameCopies=0;
        qint64 annotationCopies=0;
        QString videoSha;
        DepthImages *depthImages=nullptr;
        DepthImages *cameraImages=nullptr,*videoImages=nullptr;
        QObject::connect(&preview,&CameraPreview::changed,&ui,[&]{if(engine && cameraImages)cameraImages->current=preview.current;});
        const auto loadQml=[&]() {
            // Dev hot reload rebuilds only the engine; Viewer, geometries and the
            // pipe keep running, so a reload never re-handshakes or re-reads data.
            if(window)for(const char *name:{"yaw","pitch","distance","focusPoint"})cameraState.insert(name,window->property(name));
            if(!qmlFile.isEmpty()) {QFile file(qmlFile);if(file.open(QIODevice::ReadOnly))loadedQml=file.readAll();}
            window=nullptr;cameraImages=nullptr;videoImages=nullptr;depthImages=nullptr;annotationView=nullptr;
            engine=std::make_unique<QQmlApplicationEngine>();
            depthImages=new DepthImages;depthImages->current=currentDepth;
            engine->addImageProvider("depth",depthImages);
            cameraImages=new DepthImages;cameraImages->current=preview.current;
            engine->addImageProvider("camera",cameraImages);
            videoImages=new DepthImages;videoImages->current=currentVideo;
            engine->addImageProvider("video",videoImages);
            engine->rootContext()->setContextProperty("viewer",&ui);
            engine->rootContext()->setContextProperty("cloudGeometry",&cloud);
            engine->rootContext()->setContextProperty("targetGeometry",&target);
            engine->rootContext()->setContextProperty("boxGeometry",&box);
            engine->rootContext()->setContextProperty("levelBoxGeometry",&levelBox);
            engine->rootContext()->setContextProperty("skeletonGeometry",&skeleton);
            engine->rootContext()->setContextProperty("skeletonNodesGeometry",&skeletonNodes);
            engine->rootContext()->setContextProperty("pickGeometry",&picked);
            engine->rootContext()->setContextProperty("pickBoxGeometry",&pickedBox);
            engine->rootContext()->setContextProperty("pick",&pick);
            engine->rootContext()->setContextProperty("cameraPreviewFeed",&preview);
            if(!option("--camera-report").isEmpty() || !option("--camera-reload-report").isEmpty() || !option("--workspace-report").isEmpty()
                || !option("--video-report").isEmpty() || !option("--preview-report").isEmpty() || !option("--annotation-report").isEmpty() || !option("--local-report").isEmpty() || !option("--offline-preview-report").isEmpty()) {
                QVariantMap props{{"flags",QVariant::fromValue(Qt::WindowFlags(Qt::Window|Qt::WindowDoesNotAcceptFocus|Qt::WindowTransparentForInput))},
                                  {"headlessChecks",true}};
                if(option("--video-report").isEmpty()){props["videoWindowOpen"]=false;props["autoVideo"]=false;}
                engine->setInitialProperties(props);
            }
            engine->load(qmlFile.isEmpty()?QUrl("qrc:/Main.qml"):QUrl::fromLocalFile(qmlFile));
            if(engine->rootObjects().isEmpty()) {
                if(qmlFile.isEmpty())throw std::runtime_error("QML failed to load");
                engine.reset();qWarning("QML reload failed: fix the file, the next save retries");return;
            }
            window=qobject_cast<QQuickWindow*>(engine->rootObjects().first());reloads++;
            const QString liveEndpoint=option("--smoke-live").isEmpty()?option("--live-url"):option("--smoke-live");
            if(window && !liveEndpoint.isEmpty())window->setProperty("liveEndpoint",liveEndpoint);
            if(window)for(auto it=cameraState.cbegin();it!=cameraState.cend();++it)window->setProperty(it.key().toUtf8().constData(),it.value());
            // 标注画布复用当前帧点云（同一份共享内存副本），不额外读盘。
            annotationView=window?window->findChild<AnnotationView*>("annotationView"):nullptr;
            if(annotationView && window->property("section").toInt()==3) {
                annotationView->setFrame(currentScene,ui.data.value("frameIndex").toInt());annotationCopies++;
            }
            if(args.contains("--smoke-depth"))engine->rootObjects().first()->setProperty("showDepth",true);
        };
        loadQml();
        // 标注画布只在标注页可见时同步点云：section 变化后补一次当前帧（150ms 足够，不逐帧轮询）。
        int watchedSection=-1;
        QTimer sectionWatch;sectionWatch.setInterval(150);
        QObject::connect(&sectionWatch,&QTimer::timeout,&ui,[&] {
            if(!window)return;
            const int section=window->property("section").toInt();
            if(section==watchedSection)return;
            watchedSection=section;
            if(section==3 && annotationView) {
                annotationView->setFrame(currentScene,ui.data.value("frameIndex").toInt());annotationCopies++;
            }
        });
        sectionWatch.start();
        QFileSystemWatcher watcher;QTimer debounce;debounce.setSingleShot(true);QString watchDir;
        if(!qmlFile.isEmpty()) {
            watchDir=QFileInfo(qmlFile).absolutePath();
            watcher.addPath(qmlFile);watcher.addPath(watchDir);
            const auto changed=[&]{debounce.start(300);};
            QObject::connect(&watcher,&QFileSystemWatcher::fileChanged,&debounce,changed);
            QObject::connect(&watcher,&QFileSystemWatcher::directoryChanged,&debounce,changed);
            QObject::connect(&debounce,&QTimer::timeout,&debounce,[&] {
                if(closing)return;
                // Editors replace files: re-arm paths an editor save may have dropped.
                if(!watcher.files().contains(qmlFile))watcher.addPath(qmlFile);
                if(!watcher.directories().contains(watchDir))watcher.addPath(watchDir);
                QFile source(qmlFile);
                if(!source.open(QIODevice::ReadOnly) || source.readAll()==loadedQml)return;
                loadQml();
            });
        }
        const auto consume=[&] {
            try {
                pending+=socket.readAll();
                while(!closing && pending.size()>=4) {
                    const quint32 n=messageSize();
                    if(pending.size()<n+4)break;
                    QJsonParseError error;
                    const QJsonDocument document=QJsonDocument::fromJson(pending.mid(4,n),&error);
                    pending.remove(0,n+4);
                    if(error.error!=QJsonParseError::NoError || !document.isObject())throw std::runtime_error("Invalid service JSON");
                    const QJsonObject message=document.object();
                    const QString type=message["type"].toString();
                    // 错误/成功回包在这里结算：提示落在发起动作的通道上，迟到回包不改新状态。
                    ui.noteReply(message);
                    if(type=="close") {closing=true;app.quit();return;}
                    if(type=="frame") {
                        QElapsedTimer timer;timer.start();
                        const qint64 sceneBytes=message["sceneBytes"].toInteger(-1),targetBytes=message["targetBytes"].toInteger(-1),
                            intensityBytes=message["intensityBytes"].toInteger(-1);
                        if(sceneBytes<0 || targetBytes<0 || intensityBytes<0 || sceneBytes%12 || targetBytes%12
                            || sceneBytes>capacity-targetBytes-intensityBytes)
                            throw std::runtime_error("Frame outside shared slot");
                        const QByteArray scene(view,sceneBytes),selected(view+sceneBytes,targetBytes),
                            intensity(intensityBytes?view+sceneBytes+targetBytes:view,intensityBytes);
                        const QJsonObject info=message["info"].toObject();
                        lastSubmission=message["submissionId"].toInteger();
                        if(ui.data.value("sessionId").toString()!=info["sessionId"].toString()
                            || ui.data.value("generation").toInt()!=info["generation"].toInt()) {
                            currentVideo=QImage();videoSha.clear();if(engine)videoImages->current=currentVideo;
                            ui.videoData.remove("imageSource");emit ui.videoChanged();
                        }
                        const auto sha=[](const QByteArray &b){return QCryptographicHash::hash(b,QCryptographicHash::Sha256).toHex();};
                        if(sha(scene)!=info["xyzSha256"].toString().toLatin1() || sha(selected)!=info["targetSha256"].toString().toLatin1()
                            || sha(intensity)!=info["intensitySha256"].toString().toLatin1())
                            throw std::runtime_error("Shared frame checksum mismatch");
                        frameCopies++;
                        currentScene=scene;currentIntensity=intensity;applyCloud();target.submit(selected,{},0);ui.data=info.toVariantMap();
                        if(info["mode"].toString()=="live")ui.data.insert("liveGroundStatus",liveGroundBinding);
                        // 标注页不可见时不拷贝整帧；切到标注台时由 section 轮询补一次当前帧。
                        if(annotationView && window && window->property("section").toInt()==3) {
                            annotationView->setFrame(scene,info["frameIndex"].toInt());annotationCopies++;
                        }
                        const QByteArray preview=QByteArray::fromBase64(message["depthPreview"].toString().toLatin1());
                        const QString frameSession=info["sessionId"].toString();
                        if(frameSession!=depthSession) {
                            currentDepth=QImage();depthUrl.clear();depthFrame=-1;depthSubmission=0;depthSession=frameSession;
                        }
                        if(!preview.isEmpty()) {
                            const auto d=info["depth"].toObject();
                            QImage img=QImage::fromData(preview,"PNG");
                            if(img.size()!=QSize(256,192) || sha(preview)!=d["previewSha256"].toString().toLatin1())
                                throw std::runtime_error("Depth preview checksum/size mismatch");
                            currentDepth=img;depthSubmission=message["submissionId"].toInteger();
                            depthFrame=info["frameIndex"].toInt();
                            depthRotation=d["metadata"].toObject()["version"].toInt()==1?180:0;
                            depthUrl="image://depth/"+QString::number(depthSubmission);
                        }
                        // 深度图按可用帧更新：实时识别结果缺同帧预览时保留上一张，由 depthStale
                        // 明确标出它属于哪一帧，避免 2D 页每帧闪空。
                        ui.data.insert("depthImage",depthUrl);
                        ui.data.insert("depthStale",!preview.isEmpty()?false:(depthFrame>=0));
                        ui.data.insert("depthFrame",depthFrame);
                        ui.data.insert("depthRotation",depthRotation);
                        if(engine)depthImages->current=currentDepth;
                        box.submit(info["result"].toObject()["box"].toObject().toVariantMap());
                        levelBox.submit(selected);
                        const auto pose=info["result"].toObject()["skeleton"].toObject().toVariantMap();
                        skeleton.submit(pose);skeletonNodes.submit(pose,true);
                        pick.setFrame(scene);   // 框选按同一视锥对每帧重选（实时跟踪框内人体）。
                        ui.isPlaying=info["playing"].toBool();ui.notify();
                        if(option("--ack-fault")=="missing-live" && info["mode"].toString()=="live") {
                            QFile held(QFileInfo(option("--screenshot")).absolutePath()+"/ACK_HELD.json");
                            if(held.open(QIODevice::WriteOnly|QIODevice::NewOnly)) {
                                QVariantMap diagnostic=ui.data;
                                diagnostic.insert("levelAvailable",window->property("levelAvailable"));
                                diagnostic.insert("levelGround",window->property("ground"));
                                held.write(QJsonDocument(QJsonObject::fromVariantMap(diagnostic)).toJson());
                            }
                        }
                        if(option("--ack-fault")!="missing" && !(option("--ack-fault")=="missing-live" && info["mode"].toString()=="live"))ui.send({{"op","ack"},{"submissionId",option("--ack-fault")=="bad"?QJsonValue(message["submissionId"].toInteger()+1):message["submissionId"]},{"frameIndex",info["frameIndex"]},
                            {"xyzSha256",info["xyzSha256"]},{"targetSha256",info["targetSha256"]},{"intensitySha256",info["intensitySha256"]},
                            {"depthSha256",info["depth"].toObject()["previewSha256"]},
                            {"copyCompletedMs",double(timer.nsecsElapsed())/1e6},{"seekBurstEnqueueMs",seekBurstEnqueueMs}});
                    } else if(type=="depth") {
                        // 只刷新已经在屏幕上的那一帧的深度图；submission 不符即丢弃。
                        const qint64 sub=message["submissionId"].toInteger();
                        const QJsonObject info=message["info"].toObject();
                        const QByteArray preview=QByteArray::fromBase64(message["depthPreview"].toString().toLatin1());
                        if(sub==lastSubmission && !preview.isEmpty()) {
                            const auto sha=[](const QByteArray &b){return QCryptographicHash::hash(b,QCryptographicHash::Sha256).toHex();};
                            const QJsonObject d=info["depth"].toObject();
                            QImage img=QImage::fromData(preview,"PNG");
                            if(img.size()!=QSize(256,192) || sha(preview)!=d["previewSha256"].toString().toLatin1())
                                throw std::runtime_error("Depth update checksum/size mismatch");
                            if(info["sessionId"].toString()!=depthSession) throw std::runtime_error("Depth update session mismatch");
                            currentDepth=img;depthSubmission=sub;depthFrame=info["frameIndex"].toInt();
                            depthRotation=d["metadata"].toObject()["version"].toInt()==1?180:0;
                            depthUrl="image://depth/"+QString::number(sub);
                            if(engine)depthImages->current=currentDepth;
                            ui.data.insert("depth",d.toVariantMap());
                            ui.data.insert("depthImage",depthUrl);
                            ui.data.insert("depthStale",false);
                            ui.data.insert("depthFrame",depthFrame);
                            ui.data.insert("depthRotation",depthRotation);
                            ui.notify();
                        }
                    } else if(type=="joint") {
                        ui.jointData=message["status"].toObject().toVariantMap();ui.jointData.insert("configured",true);
                        ui.jointData.insert("previewUrl",message["previewUrl"].toString());
                    } else if(type=="videoInfo") {
                        ui.videoData=message["info"].toObject().toVariantMap();
                        if(!message["active"].toBool())ui.videoData["available"]=false;
                        currentVideo=QImage();videoSha.clear();if(engine)videoImages->current=currentVideo;
                        emit ui.videoChanged();continue;
                    } else if(type=="videoError" || type=="videoClear") {
                        currentVideo=QImage();videoSha.clear();if(engine)videoImages->current=currentVideo;
                        ui.videoData.remove("imageSource");ui.videoData.remove("reason");ui.videoData["state"]="";
                        ui.videoData["error"]=message["message"].toString();emit ui.videoChanged();continue;
                    } else if(type=="videoFrame") {
                        const auto packet=message["packet"].toObject();
                        if(ui.data.value("mode").toString()!="replay" || packet["sessionId"].toString()!=ui.data.value("sessionId").toString()
                            || packet["generation"].toInt()!=ui.data.value("generation").toInt()
                            || packet["mediaVersion"].toInt()!=ui.videoData.value("mediaVersion").toInt())continue;
                        const QByteArray jpeg=QByteArray::fromBase64(packet["jpeg"].toString().toLatin1());
                        if(jpeg.size()>512*1024 || QCryptographicHash::hash(jpeg,QCryptographicHash::Sha256).toHex()!=packet["jpegSha256"].toString().toLatin1())
                            throw std::runtime_error("Invalid video JPEG payload");
                        const auto videoInfo=packet["info"].toObject();
                        ui.videoData.remove("error");
                        for(auto it=videoInfo.begin();it!=videoInfo.end();++it)ui.videoData[it.key()]=it.value().toVariant();
                        ui.videoData["sourceFrameIndex"]=packet["sourceFrameIndex"].toInt();
                        if(jpeg.isEmpty()) {currentVideo=QImage();videoSha.clear();ui.videoData.remove("imageSource");}
                        else if(videoSha!=packet["jpegSha256"].toString()) {
                            QImage image=QImage::fromData(jpeg,"JPEG");
                            if(image.isNull() || image.width()>1280 || image.height()>720)throw std::runtime_error("Invalid video dimensions");
                            currentVideo=image;videoSha=packet["jpegSha256"].toString();
                            ui.videoData["imageSource"]="image://video/"+QString::number(++videoRevision);
                        }
                        if(engine)videoImages->current=currentVideo;
                        emit ui.videoChanged();continue;
                    } else if(type=="deleteManifest") {
                        ui.setDeleteManifest(message["manifest"].toObject().toVariantMap());ui.notify();
                    } else if(type=="openUrl") {
                        const QUrl url(message["url"].toString());
                        if(url.scheme()!="http" || (url.host()!="127.0.0.1" && url.host()!="localhost"))
                            throw std::runtime_error("Invalid local annotation URL");
                        ui.data.insert("annotationUrl",url.toString());
                        if(!args.contains("--no-external-open") && !QDesktopServices::openUrl(url))
                            ui.message="无法打开浏览器，请复制标注台地址："+url.toString();
                    } else if(type=="gt" || type=="gtSaved") {
                        // 标注文档只走本地标注 store；QML 据此刷新行内标注台，不自动打开浏览器。
                        ui.gtData=message.toVariantMap();emit ui.gtChanged();continue;
                    } else if(type=="sessions") {
                        ui.sessionData=message["sessions"].toArray().toVariantList();
                    } else if(type=="localTask") {
                        ui.localTaskData=message.toVariantMap();
                    } else if(type=="ground") {
                        ui.groundData=message["ground"].toObject().toVariantMap();emit ui.groundChanged();
                    } else if(type=="openOfflinePreview") {
                        const QString path=QFileInfo(message["path"].toString()).canonicalFilePath();
                        const QString base=QFileInfo(QDir::currentPath()+"/console_v2/.tools/local-analysis").canonicalFilePath();
                        if(path.isEmpty() || base.isEmpty() || !path.startsWith(base+"/",Qt::CaseInsensitive) || !path.endsWith("/preview/index.html",Qt::CaseInsensitive))
                            throw std::runtime_error("Invalid offline preview path");
                        ui.offlinePreviewPath=path;
                        if(!args.contains("--no-external-open") && !QDesktopServices::openUrl(QUrl::fromLocalFile(path)))
                            ui.message="无法打开离线预览："+path;
                    } else {
                        // 命令错误也走 gt 通道：标注台据此解除「保存中/载入中」，不会永久卡住按钮。
                        if(type=="error") {ui.gtData=message.toVariantMap();emit ui.gtChanged();}
                        ui.message=message["message"].toString();
                        if(message.contains("groundBinding")) {
                            liveGroundBinding=message["groundBinding"].toObject().toVariantMap();
                            ui.data.insert("liveGroundStatus",liveGroundBinding);
                        }
                        if(message.contains("playing"))ui.isPlaying=message["playing"].toBool();
                        if(message["clearTarget"].toBool()) {target.submit({},{},0);box.submit({});levelBox.submit({});skeleton.submit({});skeletonNodes.submit({},true);ui.data.insert("result",QVariant());ui.data.insert("targetCount",0);ui.data.insert("depth",QVariant());ui.data.insert("depthImage",QString());ui.data.insert("depthStale",false);ui.data.insert("depthFrame",-1);currentDepth=QImage();depthUrl.clear();depthFrame=-1;depthSession.clear();if(engine)depthImages->current=currentDepth;}
                    }
                    ui.notify();
                }
            } catch(const std::exception &error) {
                qCritical("%s",error.what());closing=true;app.exit(2);
            }
        };
        QObject::connect(&socket,&QLocalSocket::readyRead,&ui,consume);
        QObject::connect(&socket,&QLocalSocket::disconnected,&ui,[&]{if(!closing){closing=true;app.exit(2);}});
        QTimer::singleShot(0,&ui,consume);
        if(!option("--video-report").isEmpty())startVideoChecks(window,ui,option("--video-report"),currentVideo);
        if(!option("--preview-report").isEmpty())startPreviewChecks(window,ui,preview,option("--preview-report"),frameCopies,args.contains("--preview-stale"));
        if(!option("--offline-preview-report").isEmpty()) {
            struct OfflineTest {QElapsedTimer clock;int stage=0;bool groundRejected=false;};
            auto test=std::make_shared<OfflineTest>();test->clock.start();auto *timer=new QTimer(&ui);timer->setInterval(100);
            const QString path=option("--offline-preview-report");
            QObject::connect(timer,&QTimer::timeout,&ui,[window,&ui,timer,test,path] {
                const QString state=ui.localTask().value("state").toString();
                if(test->stage==0 && state=="failed") {test->groundRejected=true;workspaceClick(window,"localOfflinePreviewButton");test->stage=1;}
                else if(test->stage==1 && state=="running")test->stage=2;
                else if((test->stage==2 && (state=="done" || state=="failed")) || test->clock.elapsed()>90000) {
                    const bool passed=test->groundRejected && state=="done" && !ui.offlinePreviewPath.isEmpty();
                    timer->stop();QFile file(path);if(file.open(QIODevice::WriteOnly|QIODevice::NewOnly))
                        file.write(QJsonDocument(QJsonObject{{"status",passed?"PASS":"FAIL"},{"task",QJsonObject::fromVariantMap(ui.localTask())}}).toJson());
                    window->grabWindow().save(QFileInfo(path).absolutePath()+"/offline_preview.png");
                    if(passed)ui.command({{"op","quit"}});else QCoreApplication::exit(2);
                }
            });timer->start();
        }
        if(!option("--local-report").isEmpty()) {
            struct LocalTest {QElapsedTimer clock;int stage=0;QJsonArray checks;};
            auto test=std::make_shared<LocalTest>();test->clock.start();
            auto *timer=new QTimer(&ui);timer->setInterval(100);
            const QString path=option("--local-report");
            QObject::connect(timer,&QTimer::timeout,&ui,[window,&ui,timer,test,path] {
                auto check=[&](const QString &name,bool pass){test->checks.append(QJsonObject{{"case",name},{"passed",pass}});};
                auto finish=[&](bool pass){timer->stop();QFile file(path);if(file.open(QIODevice::WriteOnly|QIODevice::NewOnly))file.write(QJsonDocument(QJsonObject{{"status",pass?"PASS":"FAIL"},{"checks",test->checks},{"task",QJsonObject::fromVariantMap(ui.localTask())}}).toJson());if(pass)ui.command({{"op","quit"}});else QCoreApplication::exit(2);};
                if(test->clock.elapsed()>180000 || ui.localTask().value("state").toString()=="failed") {check("task_completed",false);finish(false);return;}
                if(test->stage==0 && test->clock.elapsed()>800) {if(ui.localTask().value("state").toString()!="running")workspaceClick(window,"localGroundButton");test->stage=1;}
                else if(test->stage==1 && ui.localTask().value("state").toString()=="done" && ui.ground().value("available").toBool()) {
                    check("session_ground_available",ui.ground().value("sessionId").toString()==ui.data.value("sessionId").toString());
                    workspaceClick(window,"localEmptyPrefix");workspaceClick(window,"localAnalysisButton");test->stage=2;
                } else if(test->stage==2 && ui.localTask().value("state").toString()=="running")test->stage=3;
                else if(test->stage==3 && ui.localTask().value("state").toString()=="done" && ui.localTask().value("enabled").toBool()) {
                    check("analysis_enabled",true);ui.command({{"op","seek"},{"index",200}});test->stage=4;
                } else if(test->stage==4 && ui.data.value("frameIndex").toInt()==200 && ui.data.value("targetCount").toInt()>0) {
                    check("same_frame_target",ui.data.value("targetCount").toInt()==2449);
                    check("level_available",window->property("levelAvailable").toBool());
                    check("automatic_level_rotation",window->property("levelActive").toBool() && levelResidualOf(window)<0.01);
                    workspaceClick(window,"levelButton");check("switch_to_raw",!window->property("levelActive").toBool());
                    workspaceClick(window,"levelButton");check("level_rotation",window->property("levelActive").toBool() && levelResidualOf(window)<0.01);
                    window->setProperty("showDepth",true);window->grabWindow().save(QFileInfo(path).absolutePath()+"/local_depth.png");
                    workspaceClick(window,"localAnalysisButton");test->stage=5;
                } else if(test->stage==5 && !ui.localTask().value("enabled").toBool() && ui.data.value("targetCount").toInt()==0) {
                    check("algorithm_off_clears_target",true);
                    ui.command({{"op","open"},{"sessionId","cap_20261017_113516"}});test->stage=6;
                } else if(test->stage==6 && ui.data.value("sessionId").toString()=="cap_20261017_113516") {
                    check("session_switch_no_old_ground",!ui.ground().value("available").toBool() || ui.ground().value("sessionId").toString()=="cap_20261017_113516");test->stage=7;
                } else if(test->stage==7 && ui.ground().value("sessionId").toString()=="cap_20261017_113516" && window->property("levelActive").toBool()) {
                    check("second_session_automatic_level",levelResidualOf(window)<0.01);
                    bool pass=true;for(const auto &v:test->checks)pass&=v.toObject()["passed"].toBool();finish(pass);
                }
            });timer->start();
        }
        if(!option("--live-url").isEmpty() && !args.contains("--smoke"))
            QTimer::singleShot(250,&ui,[&]{if(window)window->setProperty("section",1);ui.command({{"op","liveConnect"},{"url",option("--live-url")},{"prefix","/single_target_live/"},{"points","/innolidar_points"}});});
        if(!option("--workspace-report").isEmpty()) {
            const auto checks=std::make_shared<QJsonArray>();
            const auto width=std::make_shared<double>(0);
            const auto require=[checks](const QString &name,bool passed) {checks->append(QJsonObject{{"case",name},{"passed",passed}});};
            const auto safe=[checks](auto action) {
                try{action();}catch(const std::exception &error){checks->append(QJsonObject{{"case",error.what()},{"passed",false}});}
            };
            QTimer::singleShot(500,&ui,[&,width,safe]{safe([&]{
                *width=window->findChild<QQuickItem*>("cloudViewport")->width();
                workspaceClick(window,"sidebarButton");
            });});
            QTimer::singleShot(850,&ui,[&,width,require,safe]{safe([&]{
                require("sidebar_collapse_expands_cloud",window->findChild<QQuickItem*>("cloudViewport")->width()>*width+200);
                window->grabWindow().save(QFileInfo(option("--workspace-report")).absolutePath()+"/workspace_wide.png");
                workspaceClick(window,"toolsButton");
            });});
            QTimer::singleShot(1200,&ui,[&,require,safe]{safe([&]{
                auto *drawer=window->findChild<QObject*>("toolsDrawer");
                require("feature_drawer_opens",drawer && drawer->property("visible").toBool());
                window->grabWindow().save(QFileInfo(option("--workspace-report")).absolutePath()+"/workspace_drawer.png");
                QMetaObject::invokeMethod(window,"chooseSection",Q_ARG(QVariant,3));
            });});
            QTimer::singleShot(1550,&ui,[&,require,safe]{safe([&]{
                require("annotation_section_restores_sidebar",window->property("section").toInt()==3 && window->property("sidebarOpen").toBool());
                workspaceClick(window,"renameButton");
            });});
            QTimer::singleShot(1900,&ui,[&,require,safe]{safe([&]{
                auto *dialog=window->findChild<QObject*>("renameDialog");
                auto *field=window->findChild<QObject*>("sessionName");
                require("rename_dialog_opens",dialog && dialog->property("visible").toBool());
                if(!field || !dialog)throw std::runtime_error("Missing rename dialog controls");
                field->setProperty("text",QString::fromUtf8("客厅 · 躺倒测试"));
                QMetaObject::invokeMethod(dialog,"accept");
            });});
            QTimer::singleShot(2400,&ui,[&,require,safe]{safe([&]{
                bool renamed=false;for(const auto &item:ui.sessionData)renamed|=item.toMap()["name"].toString()==QString::fromUtf8("客厅 · 躺倒测试");
                require("rename_persists_and_refreshes_list",renamed);
                workspaceClick(window,"annotateButton");
            });});
            QTimer::singleShot(5500,&ui,[&,checks,require,safe]{safe([&]{
                const QUrl url(ui.data.value("annotationUrl").toString());
                require("annotation_opens_local_session_link",url.host()=="127.0.0.1" && url.query().contains("sid="));
                window->grabWindow().save(QFileInfo(option("--workspace-report")).absolutePath()+"/workspace_annotation.png");
            });
                bool passed=true;for(const auto &row:*checks)passed&=row.toObject()["passed"].toBool();
                QFile file(option("--workspace-report"));
                if(!file.open(QIODevice::WriteOnly|QIODevice::NewOnly))passed=false;
                else file.write(QJsonDocument(QJsonObject{{"status",passed?"PASS":"FAIL"},{"checks",*checks},{"annotationUrl",ui.data.value("annotationUrl").toString()}}).toJson());
                if(passed)ui.command({{"op","quit"}});else {closing=true;app.exit(2);}
            });
        }
        if(!option("--annotation-report").isEmpty()) {
            // 真事件自检：切到标注台 → 窗口级鼠标拖出框 → 保存 → 重载 → 旧版本保存必须被拒。
            const auto annotationChecks=std::make_shared<QJsonArray>();
            const auto boxesBefore=std::make_shared<int>(-1);
            const auto intervalsBefore=std::make_shared<int>(-1);
            const auto versionBefore=std::make_shared<int>(-1);
            const auto boxId=std::make_shared<QString>();
            const auto boxStartX=std::make_shared<double>(0),boxStartY=std::make_shared<double>(0),
                boxStartW=std::make_shared<double>(0);
            const auto require=[annotationChecks](const QString &name,bool passed,const QString &detail=QString()) {
                annotationChecks->append(QJsonObject{{"case",name},{"passed",passed},{"detail",detail}});
            };
            const auto safe=[annotationChecks](auto action) {
                try{action();}catch(const std::exception &error){annotationChecks->append(QJsonObject{{"case",error.what()},{"passed",false}});}
            };
            const auto drag=[&](const QPointF &from,const QPointF &to) {
                QMouseEvent press(QEvent::MouseButtonPress,from,window->mapToGlobal(from.toPoint()),Qt::LeftButton,Qt::LeftButton,Qt::NoModifier);
                QCoreApplication::sendEvent(window,&press);
                for(int step=1;step<=6;step++) {
                    const QPointF at=from+(to-from)*(double(step)/6.0);
                    QMouseEvent move(QEvent::MouseMove,at,window->mapToGlobal(at.toPoint()),Qt::NoButton,Qt::LeftButton,Qt::NoModifier);
                    QCoreApplication::sendEvent(window,&move);
                }
                QMouseEvent release(QEvent::MouseButtonRelease,to,window->mapToGlobal(to.toPoint()),Qt::LeftButton,Qt::NoButton,Qt::NoModifier);
                QCoreApplication::sendEvent(window,&release);
            };
            QTimer::singleShot(450,&ui,[&]{if(window)QMetaObject::invokeMethod(window,"chooseSection",Q_ARG(QVariant,3));});
            QTimer::singleShot(1000,&ui,[&,require,safe,drag,boxesBefore,intervalsBefore,versionBefore] {
                safe([&] {
                    auto *view=window?window->findChild<QQuickItem*>("annotationView"):nullptr;
                    require("annotation_view_visible",view && view->isVisible() && view->width()>240 && view->height()>200,
                        view?QString("%1x%2").arg(view->width()).arg(view->height()):QString("missing"));
                    if(!view)throw std::runtime_error("missing annotation view");
                    *boxesBefore=int(window->property("gtBoxes").toList().size());
                    *intervalsBefore=int(window->property("gtIntervals").toList().size());
                    *versionBefore=window->property("gtVersion").toInt();
                    // 已有草稿时先跳到该人物没有框的帧：格式不允许同人物同帧多个框。
                    QMetaObject::invokeMethod(window,"annotationEnsureFreeFrame");
                });
            });
            QTimer::singleShot(1600,&ui,[&,safe,drag] {
                safe([&] {
                    auto *view=window?window->findChild<QQuickItem*>("annotationView"):nullptr;
                    if(!view)throw std::runtime_error("missing annotation view");
                    drag(view->mapToScene(QPointF(view->width()*0.34,view->height()*0.34)),
                         view->mapToScene(QPointF(view->width()*0.62,view->height()*0.72)));
                });
            });
            QTimer::singleShot(2100,&ui,[&,require,safe,boxesBefore,boxId,boxStartX,boxStartY,boxStartW,drag] {
                safe([&] {
                    const QVariantList boxes=window->property("gtBoxes").toList();
                    require("drag_creates_one_box",boxes.size()==*boxesBefore+1,
                        QString("%1 -> %2").arg(*boxesBefore).arg(boxes.size()));
                    require("drag_marks_dirty",window->property("gtDirty").toBool());
                    const QVariantMap box=boxes.isEmpty()?QVariantMap():boxes.value(boxes.size()-1).toMap();
                    require("box_has_metric_extent",box.value("w").toDouble()>0.05 && box.value("h").toDouble()>0.05,
                        QString("%1 x %2 m").arg(box.value("w").toDouble()).arg(box.value("h").toDouble()));
                    *boxId=box.value("boxId").toString();
                    *boxStartX=box.value("x").toDouble();
                    *boxStartY=box.value("y").toDouble();
                    *boxStartW=box.value("w").toDouble();
                    // 在框身内拖动 = 移动框（真实窗口鼠标事件，抓角才是缩放）。
                    auto *view=window->findChild<QQuickItem*>("annotationView");
                    if(!view)throw std::runtime_error("missing annotation view");
                    QVariantMap screen;
                    if(!QMetaObject::invokeMethod(view,"boxScreenRect",Q_RETURN_ARG(QVariantMap,screen),Q_ARG(QString,*boxId)))
                        throw std::runtime_error("boxScreenRect unavailable");
                    const QPointF center=view->mapToScene(QPointF(screen.value("x").toDouble(),screen.value("y").toDouble()));
                    drag(center,center+QPointF(60,30));
                });
            });
            QTimer::singleShot(2700,&ui,[&,require,safe,boxId,boxStartX,boxStartY,boxStartW] {
                safe([&] {
                    QVariantMap moved;
                    const QVariantList boxes=window->property("gtBoxes").toList();
                    for(const QVariant &entry:boxes)
                        if(entry.toMap().value("boxId").toString()==*boxId)moved=entry.toMap();
                    require("box_move_changes_center",
                        std::abs(moved.value("x").toDouble()-*boxStartX)>0.01 || std::abs(moved.value("y").toDouble()-*boxStartY)>0.01,
                        QString("dx %1 / dy %2 m").arg(moved.value("x").toDouble()-*boxStartX).arg(moved.value("y").toDouble()-*boxStartY));
                    require("box_move_keeps_size",std::abs(moved.value("w").toDouble()-*boxStartW)<1e-6,
                        QString("%1 -> %2 m").arg(*boxStartW).arg(moved.value("w").toDouble()));
                    window->grabWindow().save(QFileInfo(option("--annotation-report")).absolutePath()+"/annotation_page.png");
                    workspaceClick(window,"annotationSaveButton");
                });
            });
            QTimer::singleShot(2900,&ui,[&,require,safe,versionBefore] {
                safe([&] {
                    const int version=window->property("gtVersion").toInt();
                    require("save_bumps_version",version==*versionBefore+1,
                        QString("%1 -> %2").arg(*versionBefore).arg(version));
                    require("save_clears_dirty",!window->property("gtDirty").toBool());
                    require("save_releases_saving_flag",!window->property("gtSaving").toBool());
                    workspaceClick(window,"annotationReloadButton");
                });
            });
            QTimer::singleShot(3000,&ui,[&,require,safe,versionBefore] {
                safe([&] {
                    // 跨会话保护：别的会话的 gt / gtSaved 回包必须被丢弃，不改版本、框和选中会话。
                    const QString current=window->property("selectedSessionId").toString();
                    const int version=window->property("gtVersion").toInt();
                    const int boxes=int(window->property("gtBoxes").toList().size());
                    QVariantMap foreign{{"type","gt"},{"sessionId","other_session"},{"version",99},
                        {"doc",QVariantMap{{"persons",QVariantList{}},{"boxes",QVariantList{}},{"intervals",QVariantList{}}}}};
                    QMetaObject::invokeMethod(window,"applyGtMessage",Q_ARG(QVariant,foreign));
                    QVariantMap foreignSaved{{"type","gtSaved"},{"sessionId","other_session"},{"version",99}};
                    QMetaObject::invokeMethod(window,"applyGtMessage",Q_ARG(QVariant,foreignSaved));
                    require("foreign_session_response_ignored",
                        window->property("gtVersion").toInt()==version
                        && int(window->property("gtBoxes").toList().size())==boxes
                        && window->property("selectedSessionId").toString()==current,
                        QString("V%1 / %2 框").arg(window->property("gtVersion").toInt()).arg(window->property("gtBoxes").toList().size()));
                    // 该会话还没载入完时不能保存（否则会把当前空模型 / 别的会话的框写成本会话 V+1）。
                    window->setProperty("gtLoadedSessionId","");
                    QMetaObject::invokeMethod(window,"saveGt");
                    const QString blocked=window->property("gtStatus").toString();
                    const int blockedVersion=window->property("gtVersion").toInt();
                    window->setProperty("gtLoadedSessionId",current);
                    require("save_blocked_until_loaded",
                        blocked.contains(QString::fromUtf8("还没载入")) && blockedVersion==version,blocked);
                });
            });
            QTimer::singleShot(3800,&ui,[&,require,safe,boxesBefore,versionBefore] {
                safe([&] {
                    require("reload_keeps_box",int(window->property("gtBoxes").toList().size())==*boxesBefore+1,
                        QString::number(window->property("gtBoxes").toList().size()));
                    require("reload_reports_saved_version",window->property("gtVersion").toInt()>=*versionBefore+1,
                        QString("%1 -> %2").arg(*versionBefore).arg(window->property("gtVersion").toInt()));
                    // 区间：第 0 帧为起点，第 24 帧（越界会被钳到末帧）为终点。
                    ui.command({{"op","seek"},{"index",0}});
                    workspaceClick(window,"annotationIntervalStart");
                });
            });
            QTimer::singleShot(4200,&ui,[&,safe] {
                safe([&] {ui.command({{"op","seek"},{"index",24}});});
            });
            QTimer::singleShot(4900,&ui,[&,require,safe,intervalsBefore] {
                safe([&] {
                    require("selection_cleared_off_frame",window->property("selectedBoxId").toString().isEmpty(),
                        window->property("selectedBoxId").toString());
                    workspaceClick(window,"annotationIntervalEnd");
                    workspaceClick(window,"annotationIntervalAdd");
                    const int intervals=int(window->property("gtIntervals").toList().size());
                    require("interval_added",intervals==*intervalsBefore+1,QString("%1 -> %2").arg(*intervalsBefore).arg(intervals));
                    window->grabWindow().save(QFileInfo(option("--annotation-report")).absolutePath()+"/annotation_intervals.png");
                    workspaceClick(window,"annotationSaveButton");
                });
            });
            QTimer::singleShot(5800,&ui,[&,require,safe,intervalsBefore,versionBefore] {
                safe([&] {
                    require("interval_saved",window->property("gtVersion").toInt()>=*versionBefore+2,
                        QString::number(window->property("gtVersion").toInt()));
                    require("interval_kept_in_model",int(window->property("gtIntervals").toList().size())==*intervalsBefore+1);
                    // 用过期版本号再保存：必须被拒绝，而不是覆盖已有版本。
                    window->setProperty("gtVersion",0);
                    QMetaObject::invokeMethod(window,"saveGt");
                });
            });
            QTimer::singleShot(6400,&ui,[&,require,safe] {
                safe([&] {
                    require("stale_save_rejected",ui.message.contains(QString::fromUtf8("版本冲突")),ui.message);
                    // 重载把界面版本恢复成磁盘版本，再做字段校验探针：
                    // 这样 invalid_box_rejected 只可能来自字段校验，不会与版本冲突混在一起。
                    workspaceClick(window,"annotationReloadButton");
                });
            });
            QTimer::singleShot(6800,&ui,[&,require,safe,versionBefore] {
                safe([&] {
                    require("reload_restores_disk_version",window->property("gtVersion").toInt()==*versionBefore+2,
                        QString::number(window->property("gtVersion").toInt()));
                    QMetaObject::invokeMethod(window,"annotationInvalidProbe");
                });
            });
            QTimer::singleShot(7200,&ui,[&,checks=annotationChecks,require,safe,versionBefore] {
                safe([&] {
                    require("invalid_box_rejected",ui.message.contains(QString::fromUtf8("zMax")),ui.message);
                    // 探针带着与磁盘一致的 baseVersion 被拒，且界面版本没被改动：拒绝来自字段校验本身。
                    require("invalid_probe_keeps_version",window->property("gtVersion").toInt()==*versionBefore+2,
                        QString::number(window->property("gtVersion").toInt()));
                });
                bool passed=true;for(const auto &row:*checks)passed&=row.toObject()["passed"].toBool();
                QFile file(option("--annotation-report"));
                if(!file.open(QIODevice::WriteOnly|QIODevice::NewOnly))passed=false;
                else file.write(QJsonDocument(QJsonObject{{"status",passed?"PASS":"FAIL"},{"checks",*checks},
                    {"version",window?window->property("gtVersion").toInt():0},
                    {"boxes",int(window?window->property("gtBoxes").toList().size():0)},
                    {"intervals",int(window?window->property("gtIntervals").toList().size():0)},
                    {"message",ui.message}}).toJson());
                if(passed)ui.command({{"op","quit"}});else {closing=true;app.exit(2);}
            });
        }
        if(!option("--tour-report").isEmpty()) {
            // 默认落地 + 功能页巡检：真实窗口里只看「启动状态 / 切四个功能页 / 播放-暂停-逐帧」，
            // 不打开额外窗口、不写任何数据。stderr 里出现 QML/Qt 告警由 Python 用例判失败。
            const auto checks=std::make_shared<QJsonArray>();
            const auto frameBefore=std::make_shared<int>(-1);
            const auto hiddenCopies=std::make_shared<qint64>(-1);
            const auto commandsBefore=std::make_shared<qint64>(-1);
            // before/after 对照用：截图时的会话与帧号单独留档。
            const auto screenshotId=std::make_shared<QString>();
            const auto screenshotFrameIndex=std::make_shared<int>(-1);
            const auto screenshotFrameCount=std::make_shared<int>(-1);
            const auto require=[checks](const QString &name,bool passed,const QString &detail=QString()) {
                checks->append(QJsonObject{{"case",name},{"passed",passed},{"detail",detail}});
            };
            const auto safe=[checks](auto action) {
                try{action();}catch(const std::exception &error){checks->append(QJsonObject{{"case",error.what()},{"passed",false}});}
            };
            QTimer::singleShot(900,&ui,[&,require,checks] {
                try {
                    const QVariantMap snap=window->property("snap").toMap();
                    QQuickItem *cloud=window->findChild<QQuickItem*>("cloudViewport");
                    QQuickItem *annotation=window->findChild<QQuickItem*>("annotationView");
                    QObject *video=window->findChild<QObject*>("replayVideoWindow");
                    QObject *statusBar=window->findChild<QObject*>("statusBar");
                    QObject *frameReadout=window->findChild<QObject*>("frameReadout");
                    QObject *analysisBadge=window->findChild<QObject*>("analysisBadge");
                    require("default_section_is_replay",sectionOf(window)==0,QString::number(sectionOf(window)));
                    require("default_sidebar_open",window->property("sidebarOpen").toBool());
                    require("default_details_open",window->property("detailsOpen").toBool());
                    require("default_mode_is_replay",snap.value("mode").toString()=="replay",snap.value("mode").toString());
                    require("default_session_loaded",!snap.value("sessionId").toString().isEmpty(),snap.value("sessionId").toString());
                    require("default_paused_at_first_frame",snap.value("frameIndex").toInt()==0 && !ui.playing(),
                        QString("frame %1 / playing %2").arg(snap.value("frameIndex").toInt()).arg(ui.playing()?1:0));
                    require("default_session_list_populated",ui.sessionData.size()>0,QString::number(ui.sessionData.size()));
                    require("default_annotation_page_hidden",!annotation || !annotation->isVisible());
                    require("default_cloud_viewport_visible",cloud && cloud->width()>400,cloud?QString::number(cloud->width()):QString("missing"));
                    // 没有视频的会话不应自己弹出第二个窗口；有视频时会话窗口自动打开（既有行为，由 test_video 覆盖）。
                    const bool videoAvailable=ui.videoData.value("available").toBool();
                    require("default_no_unexpected_window",video && (videoAvailable || !video->property("visible").toBool()),
                        video?QString("visible=%1 available=%2").arg(video->property("visible").toBool()).arg(videoAvailable):QString("missing"));
                    // 状态条 + 帧号读数 + 未注册结果提示（本轮 P0 的三个可见改动）。
                    require("status_bar_visible",statusBar && statusBar->property("visible").toBool()
                        && statusBar->property("width").toDouble()>300,
                        statusBar?QString::number(statusBar->property("width").toDouble()):QString("missing"));
                    const QString frameText=frameReadout?frameReadout->property("text").toString():QString();
                    require("frame_readout_in_status_bar",frameText.startsWith(QString::fromUtf8("帧 0 / ")),frameText);
                    require("analysis_badge_shown",analysisBadge && analysisBadge->property("visible").toBool());
                    bool bodySize=true;
                    for(const char *name:{"statusMode","statusSession","frameReadout","statusTarget","statusAlarm","analysisBadgeText","statusPage"}) {
                        auto *text=window->findChild<QObject*>(name);
                        bodySize &= text && text->property("font").value<QFont>().pixelSize()>=12;
                    }
                    require("status_body_at_least_12px",bodySize);
                    require("status_fields_match_snapshot",namedText(window,"statusMode")==QString::fromUtf8("回放")
                        && !namedText(window,"statusSession").isEmpty() && namedText(window,"statusTarget")==QString::fromUtf8("无结果")
                        && namedText(window,"statusPage")==QString::fromUtf8("会话回放"));
                    require("analysis_badge_text",namedText(window,"analysisBadgeText")==QString::fromUtf8("未注册分析"));
                    require("frame_readout_by_slider",namedText(window,"frameReadoutSlider")==QString("0 / %1").arg(snap.value("frameCount").toInt()));
                    auto *alarm=window->findChild<QQuickItem*>("statusAlarm");
                    require("status_alarm_hidden_without_hint",alarm && !alarm->isVisible() && namedText(window,"statusAlarm")==QString::fromUtf8("低位提示"));
                    require("hidden_annotation_not_initialized",annotationCopies==0);
                    require("shortcuts_registered",
                        shortcutSequence(window,"shortcutPlay")=="Space" && shortcutSequence(window,"shortcutPrev")=="Left"
                        && shortcutSequence(window,"shortcutNext")=="Right" && shortcutSequence(window,"shortcutFirst")=="Home"
                        && shortcutSequence(window,"shortcutLast")=="End" && shortcutSequence(window,"shortcutCancel")=="Esc",
                        shortcutSequence(window,"shortcutPlay")+"/"+shortcutSequence(window,"shortcutPrev")+"/"+shortcutSequence(window,"shortcutNext")
                        +"/"+shortcutSequence(window,"shortcutFirst")+"/"+shortcutSequence(window,"shortcutLast")+"/"+shortcutSequence(window,"shortcutCancel"));
                    // ---- P1-1：会话列表单行 + 名称/编号/分析状态 + 正文 ≥12px ----
                    require("session_list_model_count",sessionCount(window)==ui.sessionData.size(),
                        QString("%1/%2").arg(sessionCount(window)).arg(ui.sessionData.size()));
                    require("session_filter_count_total",
                        namedText(window,"sessionFilterCount")==QString::fromUtf8("共 %1 个会话").arg(ui.sessionData.size()),
                        namedText(window,"sessionFilterCount"));
                    require("session_filter_starts_empty",
                        namedText(window,"sessionFilter").isEmpty() && int(sessionRows(window).size())==ui.sessionData.size(),
                        QString::number(int(sessionRows(window).size())));
                    require("session_no_match_hidden_initially",!namedVisible(window,"sessionNoMatch"));
                    require("session_alert_hidden_initially",!namedVisible(window,"sessionAlert"));
                    // ---- P1-2：色带图例 + 坐标轴（几何位置先查，方向在 5950/6100 查） ----
                    QQuickItem *legend=window->findChild<QQuickItem*>("colorLegend");
                    require("legend_visible_in_3d",legend && legend->isVisible() && legend->width()>70,
                        legend?QString::number(legend->width()):QString("missing"));
                    require("legend_single_color_text",
                        namedText(window,"colorLegendText")==QString::fromUtf8("单色 · 不分层"),namedText(window,"colorLegendText"));
                    require("legend_above_cloud_not_overlapping",
                        legend && cloud && legend->mapToScene(QPointF(0,legend->height())).y()
                            <= cloud->mapToScene(QPointF(0,0)).y());
                    QQuickItem *gizmo=window->findChild<QQuickItem*>("axisGizmoBox");
                    require("axis_gizmo_visible",gizmo && gizmo->isVisible() && gizmo->width()<=90 && gizmo->height()<=90,
                        gizmo?QString("%1x%2").arg(gizmo->width()).arg(gizmo->height()):QString("missing"));
                    if(gizmo && cloud) {
                        const QPointF corner=gizmo->mapToScene(QPointF(0,0));
                        const QPointF view=cloud->mapToScene(QPointF(0,0));
                        require("axis_gizmo_in_corner",
                            corner.x()+gizmo->width()>=view.x()+cloud->width()-24
                            && corner.y()+gizmo->height()>=view.y()+cloud->height()-24,
                            QString("%1,%2").arg(corner.x()).arg(corner.y()));
                    }
                    require("axis_labels_present",
                        namedText(window,"axisLabelX")=="X" && namedText(window,"axisLabelY")=="Y" && namedText(window,"axisLabelZ")=="Z"
                        && namedText(window,"axisUnit").startsWith("m"),
                        namedText(window,"axisLabelX")+namedText(window,"axisLabelY")+namedText(window,"axisLabelZ")+"/"+namedText(window,"axisUnit"));
                    QQuickItem *focusButton=window->findChild<QQuickItem*>("focusTargetButton");
                    QQuickItem *selectButton=window->findChild<QQuickItem*>("selectTargetButton");
                    require("view_buttons_moved_to_toolbar",
                        focusButton && selectButton && cloud
                        && focusButton->mapToScene(QPointF(0,0)).y()<cloud->mapToScene(QPointF(0,0)).y()
                        && selectButton->mapToScene(QPointF(0,0)).y()<cloud->mapToScene(QPointF(0,0)).y());
                    require("status_alert_hidden_without_error",
                        window->property("alertState").toString()=="none"
                        && !window->findChild<QQuickItem*>("statusAlertDot")->isVisible());
                } catch(const std::exception &error) {
                    checks->append(QJsonObject{{"case",error.what()},{"passed",false}});
                }
            });
            QTimer::singleShot(1150,&ui,[&,require,safe] {
                safe([&] {
                    QMetaObject::invokeMethod(window,"chooseSection",Q_ARG(QVariant,1));
                    require("section_live_selected",sectionOf(window)==1,QString::number(sectionOf(window)));
                });
            });
            QTimer::singleShot(1400,&ui,[&,require,safe] {
                safe([&] {
                    QMetaObject::invokeMethod(window,"chooseSection",Q_ARG(QVariant,2));
                    require("section_joint_selected",sectionOf(window)==2,QString::number(sectionOf(window)));
                });
            });
            QTimer::singleShot(1650,&ui,[&,require,safe] {
                safe([&] {
                    QMetaObject::invokeMethod(window,"chooseSection",Q_ARG(QVariant,3));
                    require("section_annotation_selected",sectionOf(window)==3,QString::number(sectionOf(window)));
                });
            });
            QTimer::singleShot(1950,&ui,[&,require,safe,hiddenCopies] {
                safe([&] {
                    QQuickItem *annotation=window->findChild<QQuickItem*>("annotationView");
                    require("annotation_page_usable",annotation && annotation->isVisible() && annotation->width()>240,
                        annotation?QString("%1x%2").arg(annotation->width()).arg(annotation->height()):QString("missing"));
                    const QVariantMap view=annotation?annotation->property("view").toMap():QVariantMap();
                    require("annotation_receives_current_points",view.value("points").toInt()>0
                        && view.value("points").toInt()==currentScene.size()/12
                        && view.value("frame").toInt()==ui.data.value("frameIndex").toInt(),
                        QString("points=%1 frame=%2").arg(view.value("points").toInt()).arg(view.value("frame").toInt()));
                    *hiddenCopies=annotationCopies;
                    QMetaObject::invokeMethod(window,"chooseSection",Q_ARG(QVariant,0));
                    require("back_to_replay",sectionOf(window)==0,QString::number(sectionOf(window)));
                    window->requestActivate();window->contentItem()->forceActiveFocus();
                });
            });
            QTimer::singleShot(2250,&ui,[&]{QTest::keyClick(window,Qt::Key_Space);});
            QTimer::singleShot(2750,&ui,[&,require,safe] {
                safe([&] {
                    const int frame=window->property("snap").toMap().value("frameIndex").toInt();
                    require("playback_advances_frames",frame>0,QString::number(frame));
                    require("playback_reports_playing",ui.playing());
                    require("space_starts_playback",ui.playing());
                    QTest::keyClick(window,Qt::Key_Space);
                });
            });
            QTimer::singleShot(2950,&ui,[&,require,safe,frameBefore] {
                safe([&] {
                    require("pause_stops_playing",!ui.playing());
                    *frameBefore=window->property("snap").toMap().value("frameIndex").toInt();
                    QTest::keyClick(window,Qt::Key_Right);
                });
            });
            QTimer::singleShot(3250,&ui,[&,require,safe,frameBefore] {
                safe([&] {
                    const int frame=window->property("snap").toMap().value("frameIndex").toInt();
                    require("step_moves_one_frame",*frameBefore>=0 && frame==*frameBefore+1,
                        QString("%1 -> %2").arg(*frameBefore).arg(frame));
                    QTest::keyClick(window,Qt::Key_Left);
                });
            });
            QTimer::singleShot(3500,&ui,[&,require,safe,frameBefore,hiddenCopies] {
                safe([&] {
                    require("left_moves_one_frame",ui.data.value("frameIndex").toInt()==*frameBefore);
                    require("hidden_annotation_not_copied_during_playback",annotationCopies==*hiddenCopies);
                    workspaceClick(window,"playButton");
                });
            });
            QTimer::singleShot(3750,&ui,[&,require,safe] {
                safe([&] {require("play_button_starts_playback",ui.playing());workspaceClick(window,"playButton");});
            });
            QTimer::singleShot(4000,&ui,[&,require,safe,frameBefore,commandsBefore] {
                safe([&] {
                    require("play_button_pauses_playback",!ui.playing());
                    *frameBefore=ui.data.value("frameIndex").toInt();*commandsBefore=replayCommands;
                    workspaceClick(window,"renameButton");
                    auto *field=window->findChild<QQuickItem*>("sessionName");
                    if(!field)throw std::runtime_error("Missing rename input");
                    field->setProperty("text","ab");field->forceActiveFocus();field->setProperty("cursorPosition",1);
                    QTest::keyClick(window,Qt::Key_Space);
                    require("rename_space_edits_text",field->property("text").toString()=="a b");
                    QTest::keyClick(window,Qt::Key_Left);
                    require("rename_left_moves_cursor",field->property("cursorPosition").toInt()==1);
                    QTest::keyClick(window,Qt::Key_Right);
                    require("rename_right_moves_cursor",field->property("cursorPosition").toInt()==2);
                    QTest::keyClick(window,Qt::Key_Home);QTest::keyClick(window,Qt::Key_End);
                });
            });
            QTimer::singleShot(4400,&ui,[&,require,safe,frameBefore,commandsBefore] {
                safe([&] {
                    require("rename_keys_do_not_control_replay",replayCommands==*commandsBefore
                        && !ui.playing() && ui.data.value("frameIndex").toInt()==*frameBefore);
                    auto *dialog=window->findChild<QObject*>("renameDialog");
                    QMetaObject::invokeMethod(dialog,"reject");
                    window->findChild<QQuickItem*>("cloudMouseArea")->forceActiveFocus();
                    QTest::keyClick(window,Qt::Key_End);
                });
            });
            QTimer::singleShot(4700,&ui,[&,require,safe] {
                safe([&] {require("end_seeks_last_frame",ui.data.value("frameIndex").toInt()==ui.data.value("frameCount").toInt()-1);
                    require("rename_dialog_closed",!window->findChild<QObject*>("renameDialog")->property("visible").toBool());
                    QTest::keyClick(window,Qt::Key_Home);});
            });
            QTimer::singleShot(5000,&ui,[&,require,safe] {
                safe([&] {
                    require("home_seeks_first_frame",ui.data.value("frameIndex").toInt()==0);
                    window->setProperty("selectMode",true);QTest::keyClick(window,Qt::Key_Escape);
                    require("escape_cancels_selection",!window->property("selectMode").toBool(),
                        QString("focus=%1 active=%2").arg(window->activeFocusItem()?window->activeFocusItem()->metaObject()->className():"none").arg(window->isActive()));
                    // 仅模拟 UI 的 live 快照；不连接设备。真实按键必须不向服务发送任何回放命令。
                    const auto saved=ui.data;const qint64 count=replayCommands;
                    ui.data.insert("mode","live");ui.notify();
                    window->findChild<QQuickItem*>("cloudMouseArea")->forceActiveFocus();
                    for(auto key:{Qt::Key_Space,Qt::Key_Left,Qt::Key_Right,Qt::Key_Home,Qt::Key_End})QTest::keyClick(window,key);
                    require("live_shortcuts_send_no_replay_commands_mock_snapshot",replayCommands==count);
                    ui.data=saved;ui.notify();
                    window->resize(1360,749); // 与历史 before.png 保持相同窗口尺寸。
                    ui.command({{"op","seek"},{"index",3}});
                });
            });
            QTimer::singleShot(5450,&ui,[&,require,safe,hiddenCopies,screenshotId,screenshotFrameIndex,screenshotFrameCount] {
                safe([&] {
                    require("same_frame_screenshot_at_3",ui.data.value("frameIndex").toInt()==3 && !ui.playing());
                    *screenshotId=ui.data.value("sessionId").toString();
                    *screenshotFrameIndex=ui.data.value("frameIndex").toInt();
                    *screenshotFrameCount=ui.data.value("frameCount").toInt();
                    require("screenshot_has_no_dialog",!window->findChild<QObject*>("renameDialog")->property("visible").toBool());
                    require("hidden_annotation_stays_uncopied",annotationCopies==*hiddenCopies);
                    require("tour_screenshot_saved",window->grabWindow().save(QFileInfo(option("--tour-report")).absolutePath()+"/tour.png"));
                });
            });
            QTimer::singleShot(5550,&ui,[&,require,safe] {
                safe([&] {
                    QQuickItem *row=sessionRowFor(window,ui.sessionData,QStringLiteral("cap_20261018_110029"));
                    QQuickItem *nameText=row?row->findChild<QQuickItem*>("sessionRowName"):nullptr;
                    require("session_row_truncates_long_name",
                        nameText && nameText->property("truncated").toBool()
                        && row->property("accessibleLabel").toString().contains(QString::fromUtf8("进入挥手退出")),
                        QString("truncated=%1 label=%2")
                            .arg(nameText?nameText->property("truncated").toBool():false)
                            .arg(row?row->property("accessibleLabel").toString():QString("missing")));
                });
            });
            QTimer::singleShot(5700,&ui,[&,require,safe] {
                safe([&] {require("native_window_alive",window && window->isVisible());});
            });
            // ---- 配平视图：回放应用离线地面后自动配平；下面验证自动态、手动关/开和切回 ----
            QTimer::singleShot(5750,&ui,[&,require,safe] {
                safe([&] {
                    const QVariantMap ground=ui.ground();
                    const int normalCount=ground.value("normal").toList().size();
                    require("level_ground_bound",
                        ground.value("available").toBool()
                        && ground.value("sessionId").toString()==QStringLiteral("cap_20261018_110029")
                        && normalCount==3,
                        QString("%1/%2/%3").arg(ground.value("available").toBool())
                            .arg(ground.value("sessionId").toString()).arg(normalCount));
                    require("level_available_for_current_session",
                        window->property("levelAvailable").toBool()
                        && window->findChild<QQuickItem*>("levelButton")->isEnabled());
                    // 离线地面一应用，QML 就自动 levelView=true；这里先验证自动态，再手动关掉。
                    const double autoResidual=levelResidualOf(window);
                    require("level_auto_applied",
                        window->property("levelActive").toBool()
                        && autoResidual>=0.0 && autoResidual<0.01,
                        QString::number(autoResidual));
                    require("level_auto_label",
                        namedText(window,"axisUnit")==QString::fromUtf8("m·配平")
                        && namedText(window,"viewFrameHint").contains(QString::fromUtf8("配平显示")),
                        namedText(window,"axisUnit")+"|"+namedText(window,"viewFrameHint"));
                    require("level_auto_rotation",
                        window->property("levelRotation").value<QQuaternion>()!=QQuaternion(),
                        QString::number(window->property("levelRotation").value<QQuaternion>().scalar()));
                    // 同帧目标点在配平世界坐标求包围盒；旋转改变时必须立即重算，空目标清框。
                    LevelBoxGeometry probe;
                    const float samples[]={0,0,0, 1,0,1, -1,1,2};
                    probe.submit(QByteArray(reinterpret_cast<const char*>(samples),sizeof(samples)));
                    const QByteArray before=probe.vertexData();
                    const QQuaternion rotation=QQuaternion::fromAxisAndAngle(QVector3D(0,0,1),30);
                    probe.setRotation(rotation);
                    const QByteArray after=probe.vertexData();
                    bool encloses=after.size()==24*12;
                    QVector3D lo(FLT_MAX,FLT_MAX,FLT_MAX),hi(-FLT_MAX,-FLT_MAX,-FLT_MAX);
                    const float *v=reinterpret_cast<const float*>(after.constData());
                    for(int i=0;encloses && i<24;i++)for(int j=0;j<3;j++) {
                        lo[j]=std::min(lo[j],v[3*i+j]);hi[j]=std::max(hi[j],v[3*i+j]);
                    }
                    for(int i=0;i<3 && encloses;i++) {
                        const QVector3D p=rotation.rotatedVector(QVector3D(samples[3*i],samples[3*i+2],-samples[3*i+1]));
                        for(int j=0;j<3;j++)encloses=encloses && p[j]>=lo[j]-1e-5 && p[j]<=hi[j]+1e-5;
                    }
                    require("level_box_encloses_rotated_target",encloses && before!=after);
                    probe.submit({});
                    require("level_box_clears_without_target",probe.vertexData().isEmpty());
                    require("level_does_not_change_frame",
                        ui.data.value("sessionId").toString()==QStringLiteral("cap_20261018_110029")
                        && ui.data.value("frameIndex").toInt()==3);
                    require("level_screenshot_saved",
                        window->grabWindow().save(QFileInfo(option("--tour-report")).absolutePath()+"/tour_leveled.png"));
                    workspaceClick(window,"levelButton");
                });
            });
            QTimer::singleShot(5850,&ui,[&,require,safe] {
                safe([&] {
                    const double residual=levelResidualOf(window);
                    require("level_off_residual",
                        !window->property("levelActive").toBool()
                        && residual>10.0 && residual<80.0,
                        QString::number(residual));
                    require("level_off_label",
                        namedText(window,"axisUnit")==QString::fromUtf8("m·原始")
                        && namedText(window,"viewFrameHint").contains(QString::fromUtf8("未配平")),
                        namedText(window,"axisUnit")+"|"+namedText(window,"viewFrameHint"));
                    // 坐标轴方向按传感器原始轴验证：先确保配平关闭。
                    window->setProperty("yaw",0.0);window->setProperty("pitch",25.0);
                });
            });
            // ---- P1-2：坐标轴方向（配平已关闭，yaw/pitch 由 5850 设置） ----
            QTimer::singleShot(5950,&ui,[&,require,safe] {
                safe([&] {
                    // 单位化方向（nx,ny）才是几何含义；像素幅度受距离/FOV 影响，不能当门限。
                    const auto dirs=axisDirectionVectors(window);
                    const QVector4D x=dirs[0],y=dirs[1],z=dirs[2];
                    require("axis_x_horizontal_at_yaw0",std::abs(x.x())>0.7 && x.x()>0,
                        QString("%1/%2").arg(x.x()).arg(x.y()));
                    require("axis_y_not_horizontal_at_yaw0",std::abs(y.x())<0.6,
                        QString("%1/%2").arg(y.x()).arg(y.y()));
                    require("axis_z_points_up",z.y()<-0.6,QString("%1/%2").arg(z.x()).arg(z.y()));
                    // 归一化会把“朝观察者”的轴拉得和竖直轴一样长：yaw=0 时 Y 与 Z 都落在屏幕竖线上，
                    // 只能靠投影长度分开。这里直接量两个标签的像素距离（画布按投影长度缩放箭头）。
                    auto *labelY=window->findChild<QQuickItem*>("axisLabelY");
                    auto *labelZ=window->findChild<QQuickItem*>("axisLabelZ");
                    const double labelGap=labelY && labelZ
                        ? std::abs(labelY->x()-labelZ->x())+std::abs(labelY->y()-labelZ->y()) : -1.0;
                    require("axis_labels_do_not_overlap",labelGap>=6.0,QString::number(labelGap));
                    window->setProperty("yaw",90.0);
                });
            });
            QTimer::singleShot(6050,&ui,[&,require,safe] {
                safe([&] {
                    const auto dirs=axisDirectionVectors(window);
                    const QVector4D x=dirs[0],y=dirs[1],z=dirs[2];
                    require("axis_y_horizontal_at_yaw90",std::abs(y.x())>0.7 && y.x()>0,
                        QString("%1/%2").arg(y.x()).arg(y.y()));
                    require("axis_x_not_horizontal_at_yaw90",std::abs(x.x())<0.6,
                        QString("%1/%2").arg(x.x()).arg(x.y()));
                    require("axis_z_points_up_at_yaw90",z.y()<-0.6,QString("%1/%2").arg(z.x()).arg(z.y()));
                    window->setProperty("yaw",-35.0);window->setProperty("pitch",25.0);
                    workspaceClick(window,"levelButton");
                });
            });
            QTimer::singleShot(6150,&ui,[&,require,safe] {
                safe([&] {
                    const double residual=levelResidualOf(window);
                    require("level_on_again",
                        window->property("levelActive").toBool()
                        && residual>=0.0 && residual<0.01,
                        QString::number(residual));
                    require("level_on_label",
                        namedText(window,"axisUnit")==QString::fromUtf8("m·配平")
                        && namedText(window,"viewFrameHint").contains(QString::fromUtf8("配平显示")),
                        namedText(window,"axisUnit")+"|"+namedText(window,"viewFrameHint"));
                    require("level_on_rotation",
                        window->property("levelRotation").value<QQuaternion>()!=QQuaternion(),
                        QString::number(window->property("levelRotation").value<QQuaternion>().scalar()));
                    workspaceClick(window,"levelButton");
                });
            });
            QTimer::singleShot(6250,&ui,[&,require,safe] {
                safe([&] {
                    require("level_toggle_back_to_sensor_frame",
                        !window->property("levelActive").toBool()
                        && levelResidualOf(window)>10.0
                        && namedText(window,"axisUnit")==QString::fromUtf8("m·原始"),
                        QString::number(levelResidualOf(window)));
                });
            });
            // ---- P1-1：过滤只用真实输入框，不改已加载会话 / 播放位置 / 数据 ----
            QTimer::singleShot(6300,&ui,[&,require,safe] {
                safe([&] {
                    auto *field=window->findChild<QQuickItem*>("sessionFilter");
                    if(!field)throw std::runtime_error("Missing session filter field");
                    field->forceActiveFocus();
                    typeInto(window,QStringLiteral("20261013"));
                    require("filter_typed_by_real_keys",field->property("text").toString()==QStringLiteral("20261013"),
                        field->property("text").toString());
                });
            });
            QTimer::singleShot(6500,&ui,[&,require,safe,frameBefore] {
                safe([&] {
                    const QVariantList ids=filteredSessionIds(ui.sessionData,namedText(window,"sessionFilter"));
                    const int expected=ids.size();
                    require("filter_by_id_matches_name_or_id",
                        expected>0 && expected<ui.sessionData.size() && int(sessionRows(window).size())==expected,
                        QString("%1/%2/%3").arg(expected).arg(int(sessionRows(window).size())).arg(ui.sessionData.size()));
                    bool allMatch=true,renderedMatch=true;
                    for(const QVariant &id:ids)allMatch&=id.toString().contains(QStringLiteral("20261013"));
                    const QList<QQuickItem*> rows=sessionRows(window);
                    for(auto *row:rows)
                        renderedMatch&=ids.contains(rowSessionKey(row,ui.sessionData)) && row->height()<=30;
                    require("filter_rendered_rows_match_model",allMatch && renderedMatch && rows.size()>0 && rows.size()<=expected,
                        QString::number(rows.size()));
                    // 单行布局与正文 ≥12px、名称省略、可访问名带完整 sid（真实 delegate 上查）。
                    if(!rows.isEmpty()) {
                        QQuickItem *row=rows.first();
                        require("session_row_single_line",row->height()>=20 && row->height()<=30,
                            QString::number(row->height()));
                        bool bodySize=true,oneLine=true;int texts=0;
                        for(auto *child:row->findChildren<QQuickItem*>()) {
                            const QVariant font=child->property("font");
                            if(!font.isValid())continue;
                            const QVariant lines=child->property("maximumLineCount");
                            if(!lines.isValid())continue;   // Button 等控件没有行数限制，不算文本
                            texts++;
                            bodySize&=font.value<QFont>().pixelSize()>=12;
                            if(lines.toInt()>1 && lines.toInt()<1000000)oneLine=false;
                        }
                        require("session_row_texts_at_least_12px",bodySize && texts>=2,QString::number(texts));
                        QStringList offenders;
                        for(auto *child:row->findChildren<QQuickItem*>()) {
                            const QVariant lines=child->property("maximumLineCount");
                            if(lines.isValid() && lines.toInt()>1 && lines.toInt()<1000000)
                                offenders.append(child->objectName()+QString(":%1").arg(lines.toInt()));
                        }
                        require("session_row_single_line_text",oneLine,offenders.join(","));
                        const QString accessible=row->property("accessibleLabel").toString();
                        require("session_row_accessible_name",
                            accessible.contains(QStringLiteral("20261013")) && !accessible.isEmpty(),accessible);
                        QQuickItem *nameText=row->findChild<QQuickItem*>("sessionRowName");
                        require("session_row_name_elides",
                            nameText && nameText->property("elide").toInt()!=0
                            && nameText->property("maximumLineCount").toInt()==1
                            && !nameText->property("text").toString().isEmpty(),
                            nameText?QString("%1 elide=%2 lines=%3").arg(nameText->property("text").toString())
                                .arg(nameText->property("elide").toInt())
                                .arg(nameText->property("maximumLineCount").toInt()):QString("missing"));
                    }
                    require("filter_shows_match_count",
                        namedText(window,"sessionFilterCount")==QString::fromUtf8("匹配 %1 / %2").arg(expected).arg(ui.sessionData.size()),
                        namedText(window,"sessionFilterCount"));
                    require("filter_does_not_change_loaded_session",
                        ui.data.value("sessionId").toString()==QStringLiteral("cap_20261018_110029")
                        && ui.data.value("frameIndex").toInt()==3 && !ui.playing()
                        && ui.sessionData.size()==12 && ui.data.value("frameCount").toInt()>0,
                        ui.data.value("sessionId").toString()+QString("/%1").arg(ui.data.value("frameIndex").toInt()));
                });
            });
            QTimer::singleShot(6650,&ui,[&,require,safe] {
                safe([&] {
                    workspaceClick(window,"sessionFilterClear");
                    QTest::qWait(80);
                    require("filter_clear_button_restores_all",int(sessionRows(window).size())==ui.sessionData.size()
                        && namedText(window,"sessionFilter").isEmpty() && !window->findChild<QQuickItem*>("sessionFilterClear")->isEnabled(),
                        QString::number(int(sessionRows(window).size())));
                    auto *field=window->findChild<QQuickItem*>("sessionFilter");
                    field->forceActiveFocus();
                    typeInto(window,QStringLiteral("zzz"));
                });
            });
            QTimer::singleShot(6800,&ui,[&,require,safe,frameBefore] {
                safe([&] {
                    require("filter_no_match_hint",int(sessionRows(window).size())==0
                        && window->findChild<QQuickItem*>("sessionNoMatch")->isVisible()
                        && namedText(window,"sessionNoMatch")==QString::fromUtf8("没有匹配的会话"),
                        QString("%1/%2").arg(int(sessionRows(window).size())).arg(namedText(window,"sessionNoMatch")));
                    require("filter_no_match_keeps_state",
                        ui.data.value("sessionId").toString()==QStringLiteral("cap_20261018_110029")
                        && ui.data.value("frameIndex").toInt()==3 && !ui.playing());
                    workspaceClick(window,"sessionFilterClear");
                });
            });
            QTimer::singleShot(6950,&ui,[&,require,safe] {
                safe([&] {
                    auto *field=window->findChild<QObject*>("sessionFilter");
                    field->setProperty("text",QStringLiteral("cap_20261013_082623"));
                    const QVariantList ids=filteredSessionIds(ui.sessionData,namedText(window,"sessionFilter"));
                    require("filter_single_match",ids.size()==1 && ids.first().toString()==QStringLiteral("cap_20261013_082623"),
                        QString::number(ids.size()));
                });
            });
            // 过滤后等布局完成再点行；切换会话时服务要重建视频 worker，首帧可能慢 1–3 秒，
            // 因此后续检查留足余量，并把图例检查放在新会话上做（不影响已存的 before/after 截图）。
            QTimer::singleShot(7050,&ui,[&,require,safe] {
                safe([&] {
                    QQuickItem *row=sessionRowFor(window,ui.sessionData,QStringLiteral("cap_20261013_082623"));
                    require("filtered_row_present_after_filter",row!=nullptr,QString::number(sessionCount(window)));
                    clickWindowItem(window,row);
                    require("filtered_click_updates_selection",
                        window->property("selectedSessionId").toString()==QStringLiteral("cap_20261013_082623"),
                        window->property("selectedSessionId").toString()+QString(" count=%1").arg(sessionCount(window)));
                });
            });
            QTimer::singleShot(10500,&ui,[&,require,safe] {
                safe([&] {
                    const QString sid=ui.data.value("sessionId").toString();
                    require("filtered_row_click_opens_session",
                        sid==QStringLiteral("cap_20261013_082623") && !ui.playing(),
                        sid+QString("/%1").arg(ui.data.value("frameIndex").toInt()));
                    require("filtered_session_frame_count",
                        ui.data.value("frameCount").toInt()>0,QString::number(ui.data.value("frameCount").toInt()));
                    window->findChild<QObject*>("sessionFilter")->setProperty("text",QString());
                    require("filter_clear_after_select_keeps_session",
                        window->property("selectedSessionId").toString()==QStringLiteral("cap_20261013_082623"));
                });
            });
            // ---- P1-2：图例范围必须等于实际着色计算用的范围（同一帧、同一模式切换路径） ----
            QTimer::singleShot(10900,&ui,[&,require,safe] {
                safe([&] {
                    require("legend_frame_available",ui.data.value("frameIndex").toInt()>=0
                        && !currentScene.isEmpty(),QString::number(currentScene.size()));
                    ui.setColorMode(2);
                });
            });
            QTimer::singleShot(11300,&ui,[&,require,safe] {
                safe([&] {
                    const QPointF measured=sceneRange(currentScene,currentIntensity,true);
                    const QVariantMap range=cloud.colorRange();
                    require("legend_height_uses_per_frame_range",
                        range.value("mode").toInt()==2 && range.value("perFrame").toBool()
                        && range.value("applied").toBool()
                        && std::abs(range.value("lo").toDouble()-measured.x())<1e-3
                        && std::abs(range.value("hi").toDouble()-measured.y())<1e-3,
                        QString("range %1..%2 measured %3..%4").arg(range.value("lo").toDouble())
                            .arg(range.value("hi").toDouble()).arg(measured.x()).arg(measured.y()));
                    require("legend_height_text_matches",namedText(window,"colorLegendText").contains(QString::number(measured.x(),'f',2))
                        && namedText(window,"colorLegendText").contains(QString::number(measured.y(),'f',2))
                        && namedText(window,"colorLegendText").contains(QString::fromUtf8("非离地高度")),
                        namedText(window,"colorLegendText"));
                    require("legend_strip_uses_height_map",
                        window->findChild<QObject*>("colorLegendStrip")->property("source").toUrl().toString()
                            .endsWith(QStringLiteral("colormap_height.png")),
                        window->findChild<QObject*>("colorLegendStrip")->property("source").toUrl().toString());
                    ui.setColorMode(3);
                });
            });
            QTimer::singleShot(11600,&ui,[&,require,safe] {
                safe([&] {
                    const QPointF measured=sceneRange(currentScene,currentIntensity,false);
                    const QVariantMap range=cloud.colorRange();
                    require("legend_intensity_uses_per_frame_range",
                        range.value("mode").toInt()==3 && range.value("perFrame").toBool()
                        && std::abs(range.value("lo").toDouble()-measured.x())<1e-3
                        && std::abs(range.value("hi").toDouble()-measured.y())<1e-3,
                        QString("range %1..%2 measured %3..%4").arg(range.value("lo").toDouble())
                            .arg(range.value("hi").toDouble()).arg(measured.x()).arg(measured.y()));
                    require("legend_intensity_not_confidence",
                        namedText(window,"colorLegendText").contains(QString::fromUtf8("非置信度")),namedText(window,"colorLegendText"));
                    // 无强度字段（live 流）时确实走回退分支：图例说明回退，而不是给一个假范围。
                    cloud.submit(currentScene,QByteArray(),3);
                    require("legend_fallback_without_intensity",
                        cloud.colorRange().value("applied").toBool()==false
                        && cloud.colorRange().value("reason").toString()==QStringLiteral("intensity_unavailable")
                        && namedText(window,"colorLegendText").contains(QString::fromUtf8("回退单色")),
                        namedText(window,"colorLegendText"));
                    // 高度和深度都不依赖强度：同一帧清空强度后仍必须按 Z / 固定范围着色。
                    ui.setColorMode(2);
                    cloud.submit(currentScene,QByteArray(),2);
                    const QPointF zRange=sceneRange(currentScene,QByteArray(),true);
                    const QVariantMap heightNoIntensity=cloud.colorRange();
                    require("legend_height_without_intensity",
                        heightNoIntensity.value("applied").toBool()
                        && heightNoIntensity.value("mode").toInt()==2
                        && std::abs(heightNoIntensity.value("lo").toDouble()-zRange.x())<1e-3
                        && std::abs(heightNoIntensity.value("hi").toDouble()-zRange.y())<1e-3
                        && namedText(window,"colorLegendText").contains(QString::fromUtf8("非离地高度")),
                        QString("%1/%2/%3").arg(heightNoIntensity.value("applied").toBool())
                            .arg(heightNoIntensity.value("reason").toString())
                            .arg(namedText(window,"colorLegendText")));
                    ui.setColorMode(1);
                    cloud.submit(currentScene,QByteArray(),1);
                    require("legend_depth_without_intensity",
                        cloud.colorRange().value("applied").toBool()
                        && cloud.colorRange().value("mode").toInt()==1
                        && std::abs(cloud.colorRange().value("lo").toDouble()-0.1)<1e-6,
                        QString("%1/%2").arg(cloud.colorRange().value("applied").toBool())
                            .arg(cloud.colorRange().value("reason").toString()));
                    cloud.submit(currentScene,currentIntensity,ui.colorMode());
                    ui.setColorMode(1);
                });
            });
            QTimer::singleShot(11900,&ui,[&,require,safe] {
                safe([&] {
                    const QVariantMap range=cloud.colorRange();
                    require("legend_depth_fixed_range",
                        range.value("mode").toInt()==1 && !range.value("perFrame").toBool()
                        && std::abs(range.value("lo").toDouble()-0.1)<1e-6
                        && std::abs(range.value("hi").toDouble()-8.0)<1e-6
                        // 文案必须由实际着色范围拼出来，不能写死（改常量时图例要跟着变）。
                        && namedText(window,"colorLegendText").contains(QString::number(range.value("lo").toDouble(),'f',2))
                        && namedText(window,"colorLegendText").contains(QString::number(range.value("hi").toDouble(),'f',2)),
                        namedText(window,"colorLegendText"));
                    ui.setColorMode(0);
                    require("legend_back_to_single_color",
                        namedText(window,"colorLegendText")==QString::fromUtf8("单色 · 不分层"),namedText(window,"colorLegendText"));
                });
            });
            QTimer::singleShot(12200,&ui,[&,checks,require,safe,screenshotId,screenshotFrameIndex,screenshotFrameCount] {
                safe([&] {
                    require("native_window_alive",window && window->isVisible());
                    // 指示器只随相机/配平/尺寸刷新：整轮 12.2s 含 4 次切页、3 次配平切换和播放，
                    // 逐帧刷新会 ≥ 帧数（386+）。当前实测 53，阈值放到 80 仍能抓住逐帧回归。
                    auto *gizmo=window->findChild<QQuickItem*>("axisGizmoBox");
                    const int refreshes=gizmo?gizmo->property("refreshCount").toInt():-1;
                    require("axis_refresh_not_per_frame",refreshes>0 && refreshes<=80,QString::number(refreshes));
                });
                bool passed=true;for(const auto &row:*checks)passed&=row.toObject()["passed"].toBool();
                QFile file(option("--tour-report"));
                if(!file.open(QIODevice::WriteOnly|QIODevice::NewOnly))passed=false;
                else {
                    const QVariantMap snap=window?window->property("snap").toMap():QVariantMap();
                    file.write(QJsonDocument(QJsonObject{{"status",passed?"PASS":"FAIL"},{"checks",*checks},
                        {"section",window?window->property("section").toInt():-1},
                        {"mode",snap.value("mode").toString()},
                        {"sessionId",snap.value("sessionId").toString()},
                        {"frameIndex",snap.value("frameIndex").toInt()},
                        {"frameCount",snap.value("frameCount").toInt()},
                        {"screenshotSessionId",*screenshotId},
                        {"screenshotFrameIndex",*screenshotFrameIndex},
                        {"screenshotFrameCount",*screenshotFrameCount},
                        {"colorRange",QJsonObject::fromVariantMap(cloud.colorRange())},
                        {"alert",QJsonObject::fromVariantMap(ui.alert())},
                        {"staleReplies",ui.staleReplies()},
                        {"expiredCommands",ui.expiredCommands()},
                        {"annotationCopies",annotationCopies},
                        {"frameCopies",frameCopies},
                        {"message",ui.message}}).toJson());
                    file.close();
                }
                // 报告已落盘：失败也让服务正常退出。否则 GUI 先退会让服务写管道失败，
                // 真正的失败原因被 "Pipe is broken" 盖住（仅 tour 路径，以报告 status 为准）。
                ui.command({{"op","quit"}});
            });
        }
        if(!option("--alert-report").isEmpty()) {
            // 就近错误提示自检：本机 mock 录制服务返回失败 → 真实按钮点击 → 检查发起动作的控件旁
            // 出现原因、状态条出现红点、正常路径清除、连续失败升级为持续故障、迟到回包不改新状态。
            const auto checks=std::make_shared<QJsonArray>();
            const auto require=[checks](const QString &name,bool passed,const QString &detail=QString()) {
                checks->append(QJsonObject{{"case",name},{"passed",passed},{"detail",detail}});
            };
            const auto safe=[checks](auto action) {
                try{action();}catch(const std::exception &error){checks->append(QJsonObject{{"case",error.what()},{"passed",false}});}
            };
            QTimer::singleShot(700,&ui,[&,require,safe] {
                safe([&] {
                    QMetaObject::invokeMethod(window,"chooseSection",Q_ARG(QVariant,2));
                    require("alert_joint_section_selected",window->property("section").toInt()==2,
                        QString::number(window->property("section").toInt()));
                    auto *root=window->findChild<QObject*>("jointOutputRoot");
                    if(!root)throw std::runtime_error("Missing joint output root field");
                    root->setProperty("text",QStringLiteral("Z:/mock-only"));
                    require("alert_start_without_error",window->property("alertState").toString()=="none");
                    workspaceClick(window,"jointStartButton");
                });
            });
            QTimer::singleShot(1500,&ui,[&,require,safe] {
                safe([&] {
                    const QVariantMap alert=alertFor(ui,"joint");
                    require("alert_attributed_to_start_action",
                        alert.value("state").toString()=="recoverable"
                        && alert.value("channel").toString()=="joint"
                        && alert.value("action").toString()==QString::fromUtf8("开始联合录制")
                        && alert.value("text").toString().contains(QStringLiteral("Recorder HTTP")),
                        QString("%1/%2/%3").arg(alert.value("state").toString(),alert.value("action").toString(),
                                               alert.value("text").toString()));
                    require("alert_shown_next_to_joint_controls",
                        window->findChild<QQuickItem*>("jointAlert")->isVisible()
                        && hintTextOf(window,"jointAlert").contains(QString::fromUtf8("开始联合录制")),
                        hintTextOf(window,"jointAlert"));
                    auto *hint=window->findChild<QQuickItem*>("jointAlert");
                    auto *start=window->findChild<QQuickItem*>("jointStartButton");
                    require("alert_hint_near_action_control",
                        hint && start && std::abs(hint->mapToScene(QPointF(0,0)).y()-start->mapToScene(QPointF(0,0)).y())<260
                        && std::abs(hint->mapToScene(QPointF(0,0)).x()-start->mapToScene(QPointF(0,0)).x())<280,
                        hint&&start?QString("%1,%2 vs %3,%4").arg(hint->mapToScene(QPointF(0,0)).x())
                            .arg(hint->mapToScene(QPointF(0,0)).y()).arg(start->mapToScene(QPointF(0,0)).x())
                            .arg(start->mapToScene(QPointF(0,0)).y()):QString("missing"));
                    require("alert_red_dot_in_status_bar",
                        window->findChild<QQuickItem*>("statusAlertDot")->isVisible()
                        && window->findChild<QQuickItem*>("statusAlertText")->property("text").toString()
                            ==QString::fromUtf8("开始联合录制失败"),
                        window->findChild<QQuickItem*>("statusAlertText")->property("text").toString());
                    require("alert_only_on_failing_channel",
                        ui.alerts().size()==1 && ui.alerts().contains(QStringLiteral("joint"))
                        && !window->findChild<QQuickItem*>("liveAlert")->isVisible()
                        && !window->findChild<QQuickItem*>("sessionAlert")->isVisible()
                        && !window->findChild<QQuickItem*>("annotationAlert")->isVisible(),
                        QString::number(ui.alerts().size()));
                    // 用户点「清除」应只清这一条，不牵动其他状态。
                    clickAlertClear(window,"jointAlert");
                });
            });
            QTimer::singleShot(1850,&ui,[&,require,safe] {
                safe([&] {
                    require("alert_clear_button_clears_hint",
                        alertFor(ui,"joint").isEmpty() && window->property("alertState").toString()=="none"
                        && !window->findChild<QQuickItem*>("statusAlertDot")->isVisible());
                });
            });
            // 连续 3 次失败 → 持续故障（同一动作 30 秒窗口内），颜色与文案升级。
            for(int round=0;round<3;round++)
                QTimer::singleShot(2100+round*900,&ui,[&,safe] {
                    safe([&] {workspaceClick(window,"jointStartButton");});
                });
            QTimer::singleShot(5000,&ui,[&,require,safe] {
                safe([&] {
                    require("alert_persistent_after_repeats",
                        alertFor(ui,"joint").value("state").toString()=="persistent"
                        && alertFor(ui,"joint").value("count").toInt()>=3,
                        QString("%1/%2").arg(alertFor(ui,"joint").value("state").toString())
                            .arg(alertFor(ui,"joint").value("count").toInt()));
                    require("alert_persistent_still_attributed",
                        alertFor(ui,"joint").value("action").toString()==QString::fromUtf8("开始联合录制")
                        && window->findChild<QQuickItem*>("jointAlert")->isVisible()
                        && hintTextOf(window,"jointAlert").contains(QString::fromUtf8("持续失败")),
                        hintTextOf(window,"jointAlert"));
                    // 成功动作清除同通道错误：刷新状态走 mock 服务的 200。
                    workspaceClick(window,"jointStatusButton");
                });
            });
            QTimer::singleShot(5800,&ui,[&,require,safe] {
                safe([&] {
                    require("alert_success_clears_persistent",
                        alertFor(ui,"joint").isEmpty() && window->property("alertState").toString()=="none",
                        alertFor(ui,"joint").value("state").toString());
                    // ---- 回包归因（单元级，合成的 seq/时刻；真实按钮路径已在上面的 503 段覆盖） ----
                    // 1) 无主回包：没有登记过的 seq 只计数，不覆盖界面上的正常状态。
                    const int staleIdle=ui.staleReplies();
                    ui.noteReply(errorReplyOf(900001,QStringLiteral("orphan failure")));
                    require("alert_orphan_reply_ignored",
                        ui.staleReplies()==staleIdle+1 && ui.alert().value("state").toString()=="none",
                        QString("stale %1").arg(ui.staleReplies()));
                    // 2) 跨通道：先发「打开会话」再发「开始联合录制」，错误属于前者的 seq，
                    //    必须记在 session 通道（打开会话），不能记到录制按钮下面。
                    QJsonObject openCmd=commandOf(QStringLiteral("open"));
                    QJsonObject jointCmd=commandOf(QStringLiteral("jointStart"));
                    const bool sentOpen=ui.noteSent(openCmd), sentJoint=ui.noteSent(jointCmd);
                    const qint64 openSeq=openCmd.value("seq").toInteger(-1), jointSeq=jointCmd.value("seq").toInteger(-1);
                    require("alert_commands_carry_seq",sentOpen && sentJoint && openSeq>0 && jointSeq>openSeq,
                        QString("%1/%2").arg(openSeq).arg(jointSeq));
                    ui.noteReply(errorReplyOf(openSeq,QStringLiteral("open failed late")));
                    require("alert_error_goes_to_its_own_channel",
                        alertFor(ui,"session").value("op").toString()=="open"
                        && alertFor(ui,"session").value("action").toString()==QString::fromUtf8("打开会话")
                        && alertFor(ui,"joint").isEmpty()
                        && ui.alert().value("channel").toString()=="session",
                        QString("%1/%2").arg(alertFor(ui,"session").value("op").toString(),ui.alert().value("channel").toString()));
                    // 3) 另一条命令的成功回包只清它自己：不能把 session 的失败顺手清掉。
                    ui.noteReply(okReplyOf(jointSeq));
                    require("alert_success_correlation_kept_other_channel",
                        alertFor(ui,"session").value("op").toString()=="open" && alertFor(ui,"joint").isEmpty(),
                        QString::number(ui.alerts().size()));
                    // 4) 重复/迟到回包：同一 seq 再来一次只计数，不重复弹提示。
                    const int staleAfterDuplicate=ui.staleReplies();
                    ui.noteReply(errorReplyOf(openSeq,QStringLiteral("duplicate")));
                    require("alert_duplicate_reply_counted",
                        ui.staleReplies()==staleAfterDuplicate+1
                        && alertFor(ui,"session").value("text").toString()==QStringLiteral("open failed late"),
                        QString("stale %1 text %2").arg(ui.staleReplies())
                            .arg(alertFor(ui,"session").value("text").toString()));
                    // 5) 超时未结算的命令不再占位（否则该通道的下一条真实错误会被当成迟到回包）。
                    const int expiredBefore=ui.expiredCommands();
                    Viewer::PendingReply stale;
                    stale.channel=QStringLiteral("joint");stale.op=QStringLiteral("jointStart");
                    stale.atMs=Viewer::nowMs()-31000;
                    ui.pending.insert(900002,stale);
                    ui.noteReply(errorReplyOf(900003,QStringLiteral("prune probe")));
                    require("alert_expired_command_reported",
                        ui.expiredCommands()==expiredBefore+1, QString::number(ui.expiredCommands()));
                    ui.pending.clear();
                    // 6) 30 s 滑动窗口：合成时刻，不靠等待。窗口内 3 次才是持续故障，滑走后自动降级。
                    Viewer::AlertRecord windowRecord;
                    windowRecord.count=3;
                    windowRecord.times=QVector<qint64>{1000,11000,21000};
                    require("alert_window_sliding_unit",
                        windowRecord.state(31000)=="persistent"      // 1000/11000/21000 都在 30 s 窗口内
                        && windowRecord.recentCount(31000)==3
                        && windowRecord.state(45000)=="recoverable"  // 只剩 21000 在窗口内
                        && windowRecord.recentCount(45000)==1
                        && windowRecord.state(52000)=="recoverable"  // 全部滑出窗口
                        && windowRecord.recentCount(52000)==0,
                        QString("%1/%2/%3").arg(windowRecord.state(31000),windowRecord.state(45000))
                            .arg(windowRecord.recentCount(45000)));
                    // 20 s 节奏永远不会凑成“30 s 内 3 次”，这与文案一致，不是漏升级。
                    Viewer::AlertRecord slowRecord;
                    slowRecord.count=3;
                    slowRecord.times=QVector<qint64>{0,20000,40000};
                    require("alert_window_requires_three_in_window",
                        slowRecord.state(40000)=="recoverable" && slowRecord.recentCount(40000)==2,
                        QString::number(slowRecord.recentCount(40000)));
                    ui.clearAllAlerts();
                });
            });
            QTimer::singleShot(6600,&ui,[&,checks,require,safe] {
                safe([&] {require("alert_window_alive",window && window->isVisible());});
                bool passed=true;for(const auto &row:*checks)passed&=row.toObject()["passed"].toBool();
                QFile file(option("--alert-report"));
                if(!file.open(QIODevice::WriteOnly|QIODevice::NewOnly))passed=false;
                else {
                    file.write(QJsonDocument(QJsonObject{{"status",passed?"PASS":"FAIL"},{"checks",*checks},
                        {"alert",QJsonObject::fromVariantMap(ui.alert())},
                        {"staleReplies",ui.staleReplies()},
                        {"expiredCommands",ui.expiredCommands()},
                        {"serviceMessage",ui.message}}).toJson());
                    file.close();
                }
                ui.command({{"op","quit"}});
            });
        }
        if(!option("--camera-report").isEmpty()) {
            QTimer::singleShot(1200,&ui,[&] {
                const QJsonObject report=runCameraChecks(window);
                QFile output(option("--camera-report"));
                if(!output.open(QIODevice::WriteOnly|QIODevice::NewOnly)) {closing=true;app.exit(2);return;}
                output.write(QJsonDocument(report).toJson());output.close();
                if(report["status"]=="PASS")ui.command({{"op","quit"}});
                else {closing=true;app.exit(2);}
            });
        }
        if(!option("--camera-reload-report").isEmpty()) {
            const QString privateQml=QFileInfo(option("--camera-reload-report")).absolutePath()+"/qml/";
            if(qmlFile.isEmpty() || !QFileInfo(qmlFile).canonicalFilePath().startsWith(privateQml))
                throw std::runtime_error("Camera reload check requires a private qml/ copy next to its report");
            const QByteArray original=loadedQml;
            auto checks=std::make_shared<QJsonArray>();
            const auto check=[&,checks](const QString &name,bool pass) {
                QJsonObject row{{"case",name},{"passed",pass},{"reloads",reloads},{"window",window!=nullptr}};
                if(window) {
                    const QVector3D f=window->property("focusPoint").value<QVector3D>();
                    row["yaw"]=window->property("yaw").toDouble();row["pitch"]=window->property("pitch").toDouble();
                    row["distance"]=window->property("distance").toDouble();row["focus"]=QJsonArray{f.x(),f.y(),f.z()};
                }
                checks->append(row);
            };
            const auto samePose=[&] {
                return window && std::abs(window->property("yaw").toDouble()-73)<1e-9
                    && std::abs(window->property("pitch").toDouble()+22)<1e-9
                    && std::abs(window->property("distance").toDouble()-8)<1e-9
                    && window->property("focusPoint").value<QVector3D>()==QVector3D(1,2,3);
            };
            QTimer::singleShot(500,&ui,[&] {
                if(!window)return;
                window->setProperty("yaw",73);window->setProperty("pitch",-22);
                window->setProperty("distance",8);window->setProperty("focusPoint",QVariant::fromValue(QVector3D(1,2,3)));
            });
            QTimer::singleShot(700,&ui,[&] {
                QFile neighbour(QFileInfo(qmlFile).absolutePath()+"/unrelated.tmp");
                if(neighbour.open(QIODevice::WriteOnly|QIODevice::NewOnly))neighbour.write("directory event only");
            });
            QTimer::singleShot(1600,&ui,[&,check,samePose] {
                check("unrelated_directory_change",reloads==1 && samePose());
                QFile file(qmlFile);if(file.open(QIODevice::WriteOnly|QIODevice::Append))file.write("\n// camera reload check\n");
            });
            QTimer::singleShot(2600,&ui,[&,check,samePose] {
                check("reload_preserves_pose",reloads==2 && samePose());
                QFile file(qmlFile);if(file.open(QIODevice::WriteOnly|QIODevice::Truncate))file.write("invalid QML for recovery check");
            });
            QTimer::singleShot(3600,&ui,[&,check,original] {
                check("invalid_qml_keeps_process",!window && !engine);
                QFile file(qmlFile);if(file.open(QIODevice::WriteOnly|QIODevice::Truncate))file.write(original+"\n// restored camera check\n");
            });
            QTimer::singleShot(4700,&ui,[&,check,samePose,checks] {
                check("recovery_preserves_pose",reloads==3 && samePose());
                bool pass=true;for(const auto &row:*checks)pass&=row.toObject()["passed"].toBool();
                QFile file(option("--camera-reload-report"));
                if(file.open(QIODevice::WriteOnly|QIODevice::NewOnly))file.write(QJsonDocument(QJsonObject{{"status",pass?"PASS":"FAIL"},{"checks",*checks}}).toJson());
                else pass=false;
                if(pass)ui.command({{"op","quit"}});else {closing=true;app.exit(2);}
            });
        }
        if(args.contains("--smoke")) {
            const bool liveSmoke=!option("--smoke-live").isEmpty() || !option("--live-url").isEmpty();
            if(liveSmoke) {
                QTimer::singleShot(250,&ui,[&]{
                    const QString url=option("--smoke-live").isEmpty()?option("--live-url"):option("--smoke-live");
                    auto *field=window?window->findChild<QObject*>("liveUrl"):nullptr;
                    if(!field || field->property("text").toString()!=url) {qCritical("smoke live URL field mismatch");closing=true;app.exit(2);return;}
                    window->setProperty("section",1);
                    ui.command({{"op","liveConnect"},{"url",url},{"prefix","/single_target_live/"},{"points","/innolidar_points"}});
                });
            } else {
                const int smokeFrame=option("--smoke-frame").isEmpty()?105:option("--smoke-frame").toInt();
                QTimer::singleShot(250,&ui,[&]{ui.command({{"op","play"}});});
                if(option("--smoke-playback-ms").isEmpty()) {
                QTimer::singleShot(500,&ui,[&]{ui.command({{"op","pause"}});});
                QTimer::singleShot(750,&ui,[&,smokeFrame]{ui.command({{"op","seek"},{"index",smokeFrame-1}});});
                QTimer::singleShot(900,&ui,[&,smokeFrame]{
                    QElapsedTimer timer;timer.start();
                    for(int i=0;i<500;i++)ui.command({{"op","seek"},{"index",smokeFrame-1}});
                    seekBurstEnqueueMs=double(timer.nsecsElapsed())/1e6;
                });
                QTimer::singleShot(1100,&ui,[&]{ui.command({{"op","step"},{"delta",1}});});
                }
            }
            if(args.contains("--smoke-joint")) {
                QTimer::singleShot(450,&ui,[&]{ui.command({{"op","jointStatus"}});});
                QTimer::singleShot(650,&ui,[&]{ui.command({{"op","jointStart"},{"options",QVariantMap{{"camera_url","http://127.0.0.1:1/stream"},{"radar_board_url","http://127.0.0.1:1"},{"output_root","Z:/mock-only"},{"duration_sec",1}}}});});
                QTimer::singleShot(1150,&ui,[&]{ui.command({{"op","jointStop"}});});
                QTimer::singleShot(1400,&ui,[&]{ui.command({{"op","jointStatus"}});});
            }
            QTimer::singleShot(2600,&ui,[&]{
                const QString path=option("--screenshot");
                if(!path.isEmpty() && !QFileInfo::exists(path) && window)window->grabWindow().save(path);
            });
            const int liveDuration=option("--live-duration-ms").isEmpty()?3500:option("--live-duration-ms").toInt();
            if(liveSmoke && !option("--screenshot").isEmpty()) {
                // 真实渲染探针：同一接流窗口覆盖3D、2D和结束前清理，不另开接流。
                const QString base=QFileInfo(option("--screenshot")).absolutePath();
                auto probe=[&,base](const QString &name,bool depth) {
                    if(!window)return;
                    window->setProperty("showDepth",depth);
                    QTimer::singleShot(150,&ui,[&,base,name,depth] {
                        if(!window)return;
                        const bool saved=window->grabWindow().save(base+"/"+name+".png");
                        QFile file(base+"/"+name+".json");
                        if(file.open(QIODevice::WriteOnly|QIODevice::NewOnly))
                            file.write(QJsonDocument(QJsonObject{{"snapshot",QJsonObject::fromVariantMap(ui.data)},
                                {"showDepth",depth},{"screenshotSaved",saved}}).toJson());
                    });
                };
                QTimer::singleShot(liveDuration/3,&ui,[probe]{probe("LIVE_3D",false);});
                QTimer::singleShot(liveDuration/2,&ui,[probe]{probe("LIVE_2D",true);});
                QTimer::singleShot(liveDuration*2/3,&ui,[&,base] {
                    if(!window)return;
                    window->setProperty("showDepth",false);
                    QTimer::singleShot(150,&ui,[&,base] {
                        if(!window)return;
                        const bool available=window->property("levelAvailable").toBool();
                        const bool automatic=window->property("levelActive").toBool();
                        if(available && !automatic)workspaceClick(window,"levelButton");
                        QFile file(base+"/LIVE_LEVEL.json");
                        if(file.open(QIODevice::WriteOnly|QIODevice::NewOnly))
                            file.write(QJsonDocument(QJsonObject{{"available",available},
                                {"automatic",automatic},
                                {"active",window->property("levelActive").toBool()},
                                {"residualDeg",levelResidualOf(window)},
                                {"snapshot",QJsonObject::fromVariantMap(ui.data)},
                                {"screenshotSaved",window->grabWindow().save(base+"/LIVE_LEVEL.png")}}).toJson());
                    });
                });
                QTimer::singleShot(liveDuration-500,Qt::PreciseTimer,&ui,[probe]{probe("LIVE_END",false);});
            }
            const int playbackDuration=option("--smoke-playback-ms").isEmpty()?2800:option("--smoke-playback-ms").toInt();
            QTimer::singleShot(liveSmoke?liveDuration:playbackDuration,Qt::PreciseTimer,&ui,[&]{ui.command({{"op","quit"}});});
        }
        if(args.contains("--smoke-pick")) {
            // Self-test: calibrate the QML camera probes, box the pane center and
            // require the frustum selection to catch points of the shown frame.
            QTimer::singleShot(1000,&ui,[&] {
                if(!window) {qCritical("smoke pick failed: no window");closing=true;app.exit(2);return;}
                if(!QMetaObject::invokeMethod(window,"applyPick",Q_ARG(QVariant,0.25),Q_ARG(QVariant,0.25),
                    Q_ARG(QVariant,0.85),Q_ARG(QVariant,0.85)))qCritical("smoke pick: applyPick invocation rejected");
            });
            QTimer::singleShot(1500,&ui,[&] {
                const int count=pick.infoMap.value("count").toInt();
                if(count>0)qInfo("smoke pick selected %d points",count);
                else {qCritical("smoke pick failed: count=%d info=%s",count,QJsonDocument(QJsonObject::fromVariantMap(pick.infoMap)).toJson(QJsonDocument::Compact).constData());closing=true;app.exit(2);}
            });
        }
        if(!option("--smoke-delete").isEmpty()) {
            // Delete-flow self-test: probe -> confirm -> quit. "sid,probe|bad|last,boardPort";
            // "bad" sends a drifted manifest sha (must be refused), "last" deletes the only session.
            // Timers outlive this block: everything they touch is captured by value.
            const QStringList parts=option("--smoke-delete").split(',');
            if(parts.size()!=3)throw std::runtime_error("--smoke-delete expects sid,probe|bad|last,boardPort");
            const QString sid=parts[0],token=parts[1];
            const int boardPort=parts[2].toInt();
            QTimer::singleShot(700,&ui,[sid,&ui]{ui.command({{"op","deleteProbe"},{"sessionId",sid}});});
            QTimer::singleShot(1500,&ui,[sid,token,boardPort,&ui]{
                const QString sha=(token=="bad")?QString("deadbeef"):ui.manifest.value("sha256").toString();
                ui.command({{"op","deleteConfirm"},{"sessionId",sid},{"manifestSha",sha},
                            {"board",boardPort>0},{"boardUrl",QString("http://127.0.0.1:%1/").arg(boardPort)}});
            });
            QTimer::singleShot(2400,&ui,[token,&closing,&app,&ui]{
                const bool expectFail=token=="bad"?ui.message.contains("变化")
                    :token=="last"?ui.message.contains("最后一个"):false;
                if(token=="bad"||token=="last") {
                    if(expectFail)ui.command({{"op","quit"}});
                    else {qCritical("delete smoke: unexpected message '%s'",qPrintable(ui.message));closing=true;app.exit(2);}
                } else ui.command({{"op","quit"}});
            });
        }
        if(args.contains("--smoke-reload")) {
            // Self-test: append to the dev QML copy, expect a watcher-driven reload.
            if(qmlFile.isEmpty())throw std::runtime_error("--smoke-reload requires --qml-file");
            QTimer::singleShot(900,&ui,[&]{
                QFile file(qmlFile);
                if(file.open(QIODevice::WriteOnly|QIODevice::Append)) {file.write("\n// hot reload self-test touch\n");file.close();}
            });
            QTimer::singleShot(3000,&ui,[&]{
                if(reloads>=2)ui.command({{"op","quit"}});
                else {qCritical("hot reload smoke failed: reloads=%d",reloads);closing=true;app.exit(2);}
            });
        }
        QObject::connect(&app,&QCoreApplication::aboutToQuit,&ui,[&]{if(!closing){ui.command({{"op","quit"}});socket.flush();}closing=true;});
        result=app.exec();
    } catch(const std::exception &error) {qCritical("%s",error.what());}
    if(view)UnmapViewOfFile(view);
    if(mapping)CloseHandle(mapping);
    return result;
}
