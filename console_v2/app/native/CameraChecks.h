#pragma once
#include <QCoreApplication>
#include <QJsonArray>
#include <QJsonObject>
#include <QMouseEvent>
#include <QQuickItem>
#include <QQuickWindow>
#include <QVector3D>
#include <cmath>
#include <stdexcept>

// App-local Qt event regression. This does not send desktop/OS pointer input.
inline QJsonObject runCameraChecks(QQuickWindow *window) {
    QJsonArray checks;
    try {
        if(!window)throw std::runtime_error("No application window");
        auto *area=window->findChild<QQuickItem*>("cloudMouseArea");
        if(!area)throw std::runtime_error("No cloud MouseArea");
        const auto value=[&](const char *name){return window->property(name).toDouble();};
        const auto focus=[&]{return window->property("focusPoint").value<QVector3D>();};
        const auto require=[&](const QString &name,bool pass,const QJsonObject &extra=QJsonObject{}) {
            QJsonObject row=extra;row["case"]=name;row["passed"]=pass;checks.append(row);
            if(!pass)throw std::runtime_error(name.toStdString());
        };
        const auto event=[&](QEvent::Type type,const QPointF &at,Qt::MouseButton button,Qt::MouseButtons buttons) {
            const QPointF p=area->mapToScene(at);
            QMouseEvent e(type,p,window->mapToGlobal(p.toPoint()),button,buttons,Qt::NoModifier);
            QCoreApplication::sendEvent(window,&e);
        };
        const QPointF a(area->width()*.70,area->height()*.60),b(area->width()*.23,area->height()*.35);
        const auto drag=[&](const QPointF &from,Qt::MouseButton button,double dx,double dy) {
            event(QEvent::MouseButtonPress,from,button,button);
            event(QEvent::MouseMove,from+QPointF(dx,dy),Qt::NoButton,button);
            event(QEvent::MouseButtonRelease,from+QPointF(dx,dy),button,Qt::NoButton);
        };
        for(const auto &p:{a,b}) {
            const double yaw=value("yaw"),pitch=value("pitch");
            drag(p,Qt::LeftButton,1,1);
            const double dyaw=value("yaw")-yaw,dpitch=value("pitch")-pitch;
            require("one_pixel_new_press",std::abs(dyaw-.35)<1e-6 && std::abs(dpitch-.35)<1e-6,
                    {{"yawDelta",dyaw},{"pitchDelta",dpitch}});
        }
        const double yaw=value("yaw"),pitch=value("pitch");
        const QVector3D start=focus();
        drag(a,Qt::RightButton,1,1);
        const float first=(focus()-start).length();
        const QVector3D after=focus();
        drag(b,Qt::RightButton,1,1);
        const float second=(focus()-after).length();
        require("pan_new_press",first>0 && first<.1 && std::abs(first-second)<.001
                && value("yaw")==yaw && value("pitch")==pitch,{{"firstDistance",first},{"secondDistance",second}});
        drag(a,Qt::LeftButton,0,0);
        require("click_no_motion",value("yaw")==yaw && value("pitch")==pitch);
        double previousYaw=value("yaw"),maxDeltaError=0;
        for(int i=0;i<120;i++) {
            drag(i%2?a:b,Qt::LeftButton,1,0);
            maxDeltaError=std::max(maxDeltaError,std::abs(value("yaw")-previousYaw-.35));
            previousYaw=value("yaw");
        }
        require("120_repeated_short_drags",maxDeltaError<1e-6,{{"maxAngularError",maxDeltaError}});
        event(QEvent::MouseButtonPress,b,Qt::RightButton,Qt::RightButton);
        event(QEvent::MouseButtonPress,b,Qt::LeftButton,Qt::LeftButton|Qt::RightButton);
        event(QEvent::MouseButtonRelease,b,Qt::RightButton,Qt::LeftButton);
        const double afterPanYaw=value("yaw");
        const QVector3D afterPanFocus=focus();
        event(QEvent::MouseMove,b+QPointF(10,10),Qt::NoButton,Qt::LeftButton);
        require("primary_release_does_not_switch_to_rotate",value("yaw")==afterPanYaw && focus()==afterPanFocus);
        event(QEvent::MouseButtonRelease,b+QPointF(10,10),Qt::LeftButton,Qt::NoButton);
        window->setProperty("selectMode",true);
        event(QEvent::MouseButtonPress,b,Qt::LeftButton,Qt::LeftButton);
        event(QEvent::MouseMove,b+QPointF(2,2),Qt::NoButton,Qt::LeftButton);
        const QVector3D beforeMixed=focus();
        event(QEvent::MouseButtonPress,b+QPointF(2,2),Qt::RightButton,Qt::LeftButton|Qt::RightButton);
        event(QEvent::MouseMove,b+QPointF(3,3),Qt::NoButton,Qt::LeftButton|Qt::RightButton);
        event(QEvent::MouseButtonRelease,b+QPointF(3,3),Qt::RightButton,Qt::LeftButton);
        require("secondary_release_does_not_end_pick",area->property("picking").toBool() && focus()==beforeMixed);
        event(QEvent::MouseButtonRelease,b+QPointF(3,3),Qt::LeftButton,Qt::NoButton);
        require("primary_release_ends_pick",!area->property("picking").toBool());
        event(QEvent::MouseButtonPress,b,Qt::LeftButton,Qt::LeftButton);
        area->ungrabMouse();
        require("ungrab_cancels_pick",!area->property("picking").toBool());
        event(QEvent::MouseButtonRelease,b,Qt::LeftButton,Qt::NoButton);
        event(QEvent::MouseButtonPress,b,Qt::LeftButton,Qt::LeftButton);
        window->setProperty("showDepth",true);
        require("hide_cancels_pick",!area->property("picking").toBool());
        event(QEvent::MouseButtonRelease,b,Qt::LeftButton,Qt::NoButton);
        window->setProperty("showDepth",false);
        window->setProperty("selectMode",false);
        const double oldYaw=value("yaw");
        drag(b,Qt::LeftButton,1,0);
        require("resume_rotate_after_cancel",std::abs(value("yaw")-oldYaw-.35)<1e-6);
        window->setProperty("selectMode",true);
        event(QEvent::MouseButtonPress,b,Qt::LeftButton,Qt::LeftButton);
        window->setProperty("selectMode",false);
        require("tool_change_cancels_pick",!area->property("picking").toBool());
        event(QEvent::MouseButtonRelease,b,Qt::LeftButton,Qt::NoButton);
        window->setProperty("selectMode",true);
        event(QEvent::MouseButtonPress,b,Qt::LeftButton,Qt::LeftButton);
        const QPointF wheelAt=area->mapToScene(b);
        const double oldDistance=value("distance");
        QWheelEvent wheel(wheelAt,window->mapToGlobal(wheelAt.toPoint()),QPoint(),QPoint(0,120),
                          Qt::LeftButton,Qt::NoModifier,Qt::NoScrollPhase,false);
        QCoreApplication::sendEvent(window,&wheel);
        require("wheel_cancels_pick_before_zoom",!area->property("picking").toBool() && value("distance")<oldDistance);
        event(QEvent::MouseButtonRelease,b,Qt::LeftButton,Qt::NoButton);
        window->setProperty("selectMode",false);
        return {{"status","PASS"},{"checks",checks}};
    } catch(const std::exception &e) {
        return {{"status","FAIL"},{"error",e.what()},{"checks",checks}};
    }
}
