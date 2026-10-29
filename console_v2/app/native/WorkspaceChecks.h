#pragma once
#include <QCoreApplication>
#include <QMouseEvent>
#include <QQuickItem>
#include <QQuickWindow>
#include <stdexcept>

inline void workspaceClick(QQuickWindow *window,const char *name) {
    auto *item=window?window->findChild<QQuickItem*>(name):nullptr;
    if(!item || !item->isVisible() || !item->isEnabled())throw std::runtime_error(std::string("Unavailable control: ")+name);
    const QPointF at=item->mapToScene(QPointF(item->width()/2,item->height()/2));
    for(auto type:{QEvent::MouseButtonPress,QEvent::MouseButtonRelease}) {
        QMouseEvent event(type,at,window->mapToGlobal(at.toPoint()),Qt::LeftButton,
            type==QEvent::MouseButtonPress?Qt::LeftButton:Qt::NoButton,Qt::NoModifier);
        QCoreApplication::sendEvent(window,&event);
    }
}
