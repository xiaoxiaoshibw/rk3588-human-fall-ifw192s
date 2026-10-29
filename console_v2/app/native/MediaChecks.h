#pragma once
#include <QTimer>
#include <QElapsedTimer>
#include <QQuickWindow>
#include <QFile>
#include <QFileInfo>
#include <QJsonDocument>
#include <QJsonArray>
#include "Viewer.h"
#include "Preview.h"

inline void startVideoChecks(QQuickWindow *window,Viewer &ui,const QString &path,const QImage &image) {
    struct State {int stage=0;QElapsedTimer clock;qint64 at=0;double forward=0;QJsonArray checks;};
    auto state=std::make_shared<State>();state->clock.start();
    auto *timer=new QTimer(&ui);timer->setInterval(50);
    QObject::connect(timer,&QTimer::timeout,&ui,[window,&ui,path,&image,state,timer] {
        const auto finish=[&](bool pass) {
            timer->stop();
            QFile file(path);
            if(!file.open(QIODevice::WriteOnly|QIODevice::NewOnly))pass=false;
            else file.write(QJsonDocument(QJsonObject{{"status",pass?"PASS":"FAIL"},{"checks",state->checks}}).toJson());
            if(pass)ui.command({{"op","quit"}});else QCoreApplication::exit(2);
        };
        const auto note=[&](const QString &name,bool pass) {
            const QColor color=image.isNull()?QColor():image.pixelColor(image.width()/2,image.height()/2);
            state->checks.append(QJsonObject{{"case",name},{"passed",pass},{"frameIndex",ui.data.value("frameIndex").toInt()},
                {"video",QJsonObject::fromVariantMap(ui.videoData)},{"rgb",QJsonArray{color.red(),color.green(),color.blue()}}});
        };
        if(!window || state->clock.elapsed()>15000) {note("video_timeout",false);finish(false);return;}
        auto *videoWindow=window->findChild<QQuickWindow*>("replayVideoWindow");
        const bool ready=ui.videoData.value("state").toString()=="ready" && !image.isNull()
            && ui.videoData.value("sourceFrameIndex").toInt()==ui.data.value("frameIndex").toInt();
        const auto send=[&](const char *op,const char *key,int value){ui.command({{"op",op},{key,value}});};
        if(state->stage==0 && ready) {
            const bool pass=videoWindow && videoWindow->isVisible();note("video_auto_window_and_first_frame",pass);
            if(!pass){finish(false);return;}
            ui.command({{"op","play"}});state->stage=1;
        } else if(state->stage==1 && ui.data.value("frameIndex").toInt()>=3 && ui.isPlaying) {
            ui.command({{"op","pause"}});state->stage=2;state->at=state->clock.elapsed();
        } else if(state->stage==2 && !ui.isPlaying && ready && state->clock.elapsed()-state->at>200) {
            note("video_follows_play_pause",true);send("seek","index",55);state->stage=3;
        } else if(state->stage==3 && ready && ui.data.value("frameIndex").toInt()==55) {
            note("video_follows_seek",true);state->forward=ui.videoData.value("videoTimeSec").toDouble();
            send("videoOffset","offsetMs",200);state->stage=4;
        } else if(state->stage==4 && ready && ui.videoData.value("offsetMs").toInt()==200
                  && ui.videoData.value("videoTimeSec").toDouble()>state->forward+.1) {
            note("video_offset_applies",true);send("videoOffset","offsetMs",0);send("seek","index",2);state->stage=5;
        } else if(state->stage==5 && ready && ui.data.value("frameIndex").toInt()==2 && ui.videoData.value("offsetMs").toInt()==0) {
            note("video_reverse_seek_discards_old_frames",ui.videoData.value("videoTimeSec").toDouble()<state->forward);
            if(ui.videoData.value("options").toStringList().contains("clip.mp4")) {
                ui.command({{"op","videoSelect"},{"name","clip.mp4"}});state->stage=6;
            } else state->stage=7;
        } else if(state->stage==6 && ready && ui.videoData.value("name").toString()=="clip.mp4"
                  && ui.videoData.value("alignment").toString()=="relative_start") {
            note("ordinary_mp4_follows_replay",true);state->stage=7;
        } else if(state->stage==7) {
            ui.command({{"op","speed"},{"speed",2}});ui.command({{"op","play"}});state->stage=8;
        } else if(state->stage==8 && ui.data.value("frameIndex").toInt()>=8 && ui.data.value("speed").toDouble()==2 && ready) {
            note("video_follows_double_speed",true);ui.command({{"op","pause"}});
            videoWindow->close();state->at=state->clock.elapsed();state->stage=9;
        } else if(state->stage==9 && state->clock.elapsed()-state->at>250) {
            note("video_window_can_close",videoWindow && !videoWindow->isVisible());
            window->setProperty("videoWindowOpen",true);state->stage=10;
        } else if(state->stage==10 && ready && videoWindow && videoWindow->isVisible()) {
            note("video_window_reopens_in_sync",true);
            bool hasEmpty=false;
            for(const auto &item:ui.sessionData)hasEmpty|=item.toMap().value("id").toString()=="no_video_session";
            if(hasEmpty) {
                ui.command({{"op","open"},{"sessionId","no_video_session"}});state->stage=11;return;
            }
            state->stage=13;
        } else if(state->stage==11 && ui.data.value("sessionId").toString()=="no_video_session"
                  && !ui.videoData.value("available").toBool() && image.isNull()) {
            note("no_video_session_clears_old_image",videoWindow && !videoWindow->isVisible());
            ui.command({{"op","open"},{"sessionId","video_session"}});state->stage=12;
        } else if(state->stage==12 && ready && ui.data.value("sessionId").toString()=="video_session" && videoWindow && videoWindow->isVisible()) {
            note("return_to_video_session_rebinds_source",true);state->stage=13;
        } else if(state->stage==13 && ready) {
            videoWindow->grabWindow().save(QFileInfo(path).absolutePath()+"/video_window.png");
            window->grabWindow().save(QFileInfo(path).absolutePath()+"/replay_with_video.png");
            bool pass=true;for(const auto &row:state->checks)pass&=row.toObject()["passed"].toBool();finish(pass);
        }
    });
    timer->start();
}

inline void startPreviewChecks(QQuickWindow *window,Viewer &ui,CameraPreview &preview,const QString &path,
                              const qint64 &frameCopies,bool stale) {
    struct State {QElapsedTimer clock;qint64 copies=0;double fps=0;int stage=0;QJsonArray checks;};
    auto state=std::make_shared<State>();state->clock.start();
    auto *timer=new QTimer(&ui);timer->setInterval(100);
    QObject::connect(timer,&QTimer::timeout,&ui,[window,&ui,&preview,path,&frameCopies,stale,state,timer] {
        if(state->stage==0 && state->clock.elapsed()>=500) {
            QMetaObject::invokeMethod(window,"chooseSection",Q_ARG(QVariant,2));
            ui.command({{"op","jointStatus"},{"poll",true}});
            ui.command({{"op","play"}});state->copies=frameCopies;state->stage=1;
        } else if(state->stage==1 && state->clock.elapsed()>=1200 && !ui.joint().value("camera_url").toString().isEmpty()) {
            auto *field=window->findChild<QObject*>("cameraUrl");
            if(field)field->setProperty("text",ui.joint().value("camera_url"));
            workspaceClick(window,"cameraPreviewButton");state->stage=2;
        } else if(state->stage==2 && state->clock.elapsed()>=6000) {
            state->fps=preview.fps();
            const bool pass=stale?preview.current.isNull() && preview.status().contains("过期")
                :!preview.current.isNull() && preview.fps()>=7;
            state->checks.append(QJsonObject{{"case",stale?"stale_camera_hidden":"continuous_camera_preview"},{"passed",pass},
                {"previewFps",state->fps},{"status",preview.status()},{"pointFrames",frameCopies-state->copies}});
            state->checks.append(QJsonObject{{"case","preview_does_not_stall_cloud"},{"passed",frameCopies-state->copies>=25}});
            window->grabWindow().save(QFileInfo(path).absolutePath()+"/preview.png");
            window->setProperty("sidebarOpen",false);state->stage=3;
        } else if(state->stage==3 && state->clock.elapsed()>=6500) {
            state->checks.append(QJsonObject{{"case","collapsed_preview_stops_requests"},{"passed",!preview.active() && preview.current.isNull()}});
            bool pass=true;for(const auto &row:state->checks)pass&=row.toObject()["passed"].toBool();
            timer->stop();QFile file(path);
            if(!file.open(QIODevice::WriteOnly|QIODevice::NewOnly))pass=false;
            else file.write(QJsonDocument(QJsonObject{{"status",pass?"PASS":"FAIL"},{"checks",state->checks}}).toJson());
            if(pass)ui.command({{"op","quit"}});else QCoreApplication::exit(2);
        }
    });timer->start();
}
