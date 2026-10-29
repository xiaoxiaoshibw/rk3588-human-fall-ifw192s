#pragma once
#include <QColor>
#include <QFont>
#include <QMouseEvent>
#include <QPainter>
#include <QQuickPaintedItem>
#include <QVariantList>
#include <QVariantMap>
#include <QWheelEvent>
#include <algorithm>
#include <cmath>
#include <cstring>
#include <limits>
#include <mutex>
#include <vector>

// 原生标注画布（Qt 界面内的标注台，不嵌入网页）：
// 传感器系 XY 俯视、单位米；框与 pc_apps/annotator_v2 的 gt_annotate/2 同义
// （x/y 为中心，w/h 为全宽全高，zMin/zMax 为米制高度范围）。
// 交互：左键空白拖出新框、点框选中、拖框身移动、拖角缩放；右键平移；滚轮缩放。
// paint() 由渲染线程调用，几何与交互状态（点云/视图/框/手势/拖拽矩形）统一由递归互斥量保护：
// 交互写侧、getter、QML 属性写侧与 paint 读侧都持同一把锁，没有“只锁一半”的路径。
class AnnotationView : public QQuickPaintedItem {
    Q_OBJECT
    Q_PROPERTY(QVariantList boxes READ boxes WRITE setBoxes NOTIFY boxesChanged)
    Q_PROPERTY(QString selectedBoxId READ selectedBoxId WRITE setSelectedBoxId NOTIFY selectionChanged)
    Q_PROPERTY(bool drawMode READ drawMode WRITE setDrawMode NOTIFY drawModeChanged)
    Q_PROPERTY(QVariantMap view READ view NOTIFY viewChanged)
public:
    explicit AnnotationView(QQuickItem *parent=nullptr):QQuickPaintedItem(parent) {
        setAcceptedMouseButtons(Qt::LeftButton|Qt::RightButton|Qt::MiddleButton);
        setAntialiasing(true);
        setOpaquePainting(true);
        setPerformanceHint(QQuickPaintedItem::FastFBOResizing);
    }

    QVariantList boxes() const {std::lock_guard<std::recursive_mutex> lock(m_mutex);return m_boxes;}
    void setBoxes(const QVariantList &value) {
        {std::lock_guard<std::recursive_mutex> lock(m_mutex);m_boxes=value;}
        emit boxesChanged();update();
    }
    QString selectedBoxId() const {std::lock_guard<std::recursive_mutex> lock(m_mutex);return m_selected;}
    void setSelectedBoxId(const QString &value) {
        {
            std::lock_guard<std::recursive_mutex> lock(m_mutex);
            if(value==m_selected)return;
            m_selected=value;
        }
        emit selectionChanged();update();
    }
    bool drawMode() const {return m_drawMode;}
    void setDrawMode(bool value) {
        {
            std::lock_guard<std::recursive_mutex> lock(m_mutex);
            if(value==m_drawMode)return;
            m_drawMode=value;m_gesture=Gesture::None;m_drawScreen=QRectF();
        }
        emit drawModeChanged();update();
    }
    QVariantMap view() const {std::lock_guard<std::recursive_mutex> lock(m_mutex);return m_view;}

    // 当前帧点云（float32 XYZ，已由 C# 校验并过滤非有限点）；不写盘、不联网。
    void setFrame(const QByteArray &scene,int frameIndex) {
        const qsizetype count=scene.size()/12;
        {
            std::lock_guard<std::recursive_mutex> lock(m_mutex);
            m_points.resize(size_t(count)*3);
            if(count>0)std::memcpy(m_points.data(),scene.constData(),size_t(count)*12);
            m_frame=frameIndex;
            ComputeZRangeLocked();
            if(m_needFit && width()>0 && height()>0)FitLocked();
            m_view=BuildViewLocked();
        }
        emit viewChanged();update();
    }
    void clearFrame() {
        {
            std::lock_guard<std::recursive_mutex> lock(m_mutex);
            m_points.clear();m_frame=-1;m_zMin=-0.5;m_zMax=2.5;m_needFit=true;m_view=BuildViewLocked();
        }
        emit viewChanged();update();
    }
    Q_INVOKABLE void fitToView() {
        {
            std::lock_guard<std::recursive_mutex> lock(m_mutex);
            m_needFit=true;FitLocked();m_view=BuildViewLocked();
        }
        emit viewChanged();update();
    }
    // 自检/调试用：框在画布上的屏幕中心与像素尺寸（不改任何状态）。
    Q_INVOKABLE QVariantMap boxScreenRect(const QString &boxId) const {
        std::lock_guard<std::recursive_mutex> lock(m_mutex);
        for(const QVariant &entry:m_boxes) {
            const QVariantMap box=entry.toMap();
            if(box.value("boxId").toString()!=boxId)continue;
            const QRectF rect=BoxScreenLocked(box);
            return QVariantMap{{"x",rect.center().x()},{"y",rect.center().y()},
                               {"w",rect.width()},{"h",rect.height()}};
        }
        return {};
    }

    void paint(QPainter *painter) override {
        std::lock_guard<std::recursive_mutex> lock(m_mutex);
        const QRectF area(0,0,width(),height());
        painter->fillRect(area,QColor("#08121f"));
        if(area.isEmpty())return;
        if(m_needFit)FitLocked();
        PaintGrid(painter);
        PaintPoints(painter);
        PaintBoxes(painter);
        PaintHud(painter);
    }

signals:
    void boxesChanged();
    void selectionChanged();
    void drawModeChanged();
    void viewChanged();
    // 世界坐标（米）：中心 + 全宽全高；由 QML 落成 gt_annotate 框。
    void boxDrawn(double x,double y,double w,double h);
    void boxEdited(const QString &boxId,const QVariantMap &patch);
    void boxActivated(const QString &boxId);

protected:
    void mousePressEvent(QMouseEvent *event) override {
        forceActiveFocus();
        std::lock_guard<std::recursive_mutex> lock(m_mutex);
        m_press=event->position();m_last=m_press;m_moved=false;m_resizeCorner=-1;
        if(event->button()==Qt::RightButton || event->button()==Qt::MiddleButton) {
            m_gesture=Gesture::Pan;event->accept();return;
        }
        if(event->button()!=Qt::LeftButton)return;
        const QString hit=HitBox(m_press,m_resizeCorner);
        if(!hit.isEmpty()) {
            m_dragWorld=BoxWorld(BoxById(hit));
            m_gesture=m_resizeCorner>=0?Gesture::Resize:Gesture::Move;
            if(hit!=m_selected) {m_selected=hit;emit selectionChanged();emit boxActivated(hit);}
            event->accept();update();return;
        }
        if(m_drawMode) {m_gesture=Gesture::Draw;m_drawScreen=QRectF(m_press,QSizeF());}
        else m_gesture=Gesture::Pan;
        event->accept();update();
    }

    void mouseMoveEvent(QMouseEvent *event) override {
        std::lock_guard<std::recursive_mutex> lock(m_mutex);
        if(m_gesture==Gesture::None)return;
        const QPointF position=event->position();
        if(m_gesture==Gesture::Draw) {
            m_drawScreen=QRectF(m_press,position).normalized();m_moved=true;update();return;
        }
        if(m_gesture==Gesture::Pan) {
            const QPointF delta=position-m_last;
            m_center-=QPointF(delta.x()/m_scale,-delta.y()/m_scale);
            m_view=BuildViewLocked();
            m_last=position;m_moved=true;emit viewChanged();update();return;
        }
        if(m_gesture==Gesture::Move) {
            QRectF moved=m_dragWorld;moved.translate((position.x()-m_press.x())/m_scale,-(position.y()-m_press.y())/m_scale);
            m_dragWorld=moved;m_moved=true;update();return;
        }
        if(m_gesture==Gesture::Resize) {
            const QPointF world=ToWorld(position);
            const double x0=m_dragWorld.left(),x1=m_dragWorld.right();
            const double yLow=m_dragWorld.top(),yHigh=m_dragWorld.bottom();
            double nx0=x0,nx1=x1,nyLow=yLow,nyHigh=yHigh;
            // 屏幕角 0=左上 1=右上 2=右下 3=左下；屏幕上方对应世界 y 较大。
            switch(m_resizeCorner) {
                case 0:nx0=world.x();nyHigh=world.y();break;
                case 1:nx1=world.x();nyHigh=world.y();break;
                case 2:nx1=world.x();nyLow=world.y();break;
                default:nx0=world.x();nyLow=world.y();break;
            }
            m_dragWorld=QRectF(QPointF(std::min(nx0,nx1),std::min(nyLow,nyHigh)),
                               QPointF(std::max(nx0,nx1),std::max(nyLow,nyHigh)));
            m_moved=true;update();return;
        }
    }

    void mouseReleaseEvent(QMouseEvent *event) override {
        std::lock_guard<std::recursive_mutex> lock(m_mutex);
        const Gesture gesture=m_gesture;
        m_gesture=Gesture::None;
        if(gesture==Gesture::Draw) {
            const QRectF rect=m_drawScreen.normalized();m_drawScreen=QRectF();
            if(rect.width()>=5 && rect.height()>=5) {
                const QPointF a=ToWorld(rect.topLeft()),b=ToWorld(rect.bottomRight());
                emit boxDrawn((a.x()+b.x())/2,(a.y()+b.y())/2,std::abs(b.x()-a.x()),std::abs(b.y()-a.y()));
            }
        } else if((gesture==Gesture::Move || gesture==Gesture::Resize) && m_moved && m_dragWorld.isValid()
                  && m_dragWorld.width()*m_scale>=5.0 && m_dragWorld.height()*m_scale>=5.0) {
            QVariantMap patch{{"x",m_dragWorld.center().x()},{"y",m_dragWorld.center().y()},
                              {"w",m_dragWorld.width()},{"h",m_dragWorld.height()}};
            emit boxEdited(m_selected,patch);
        }
        m_dragWorld=QRectF();m_resizeCorner=-1;m_moved=false;update();
        event->accept();
    }

    void wheelEvent(QWheelEvent *event) override {
        const QPointF position=event->position();
        {
            std::lock_guard<std::recursive_mutex> lock(m_mutex);
            const QPointF world=ToWorldLocked(position);
            m_scale=std::clamp(m_scale*std::exp(event->angleDelta().y()/600.0),3.0,400.0);
            m_center=world-QPointF((position.x()-width()/2)/m_scale,-(position.y()-height()/2)/m_scale);
            m_needFit=false;m_view=BuildViewLocked();
        }
        emit viewChanged();update();event->accept();
    }

private:
    enum class Gesture { None,Draw,Move,Resize,Pan };

    QPointF ToScreenLocked(const QPointF &world) const {
        return QPointF(width()/2+(world.x()-m_center.x())*m_scale,height()/2-(world.y()-m_center.y())*m_scale);
    }
    QPointF ToWorldLocked(const QPointF &screen) const {
        return QPointF(m_center.x()+(screen.x()-width()/2)/m_scale,m_center.y()-(screen.y()-height()/2)/m_scale);
    }
    QPointF ToWorld(const QPointF &screen) const {
        std::lock_guard<std::recursive_mutex> lock(m_mutex);return ToWorldLocked(screen);
    }

    QVariantMap BoxById(const QString &id) const {
        std::lock_guard<std::recursive_mutex> lock(m_mutex);
        for(const QVariant &entry:m_boxes) {
            const QVariantMap box=entry.toMap();
            if(box.value("boxId").toString()==id)return box;
        }
        return {};
    }
    static QRectF BoxWorld(const QVariantMap &box) {
        const double x=box.value("x").toDouble(),y=box.value("y").toDouble();
        const double w=std::max(1e-3,box.value("w").toDouble()),h=std::max(1e-3,box.value("h").toDouble());
        return QRectF(x-w/2,y-h/2,w,h);
    }
    QRectF BoxScreenLocked(const QVariantMap &box) const {
        const QRectF world=BoxWorld(box);
        return QRectF(ToScreenLocked(QPointF(world.left(),world.top())),
                      ToScreenLocked(QPointF(world.right(),world.bottom()))).normalized();
    }
    // 返回命中的框 id；corner 置为屏幕角编号（0 左上 1 右上 2 右下 3 左下），框身命中为 -1。
    QString HitBox(const QPointF &position,int &corner) const {
        std::lock_guard<std::recursive_mutex> lock(m_mutex);
        corner=-1;
        for(auto it=m_boxes.crbegin();it!=m_boxes.crend();++it) {
            const QVariantMap box=it->toMap();
            const QRectF rect=BoxScreenLocked(box);
            if(box.value("boxId").toString()==m_selected) {
                const QPointF corners[4]={rect.topLeft(),rect.topRight(),rect.bottomRight(),rect.bottomLeft()};
                for(int i=0;i<4;i++)
                    if((corners[i]-position).manhattanLength()<=14.0) {corner=i;return box.value("boxId").toString();}
            }
            if(rect.adjusted(-3,-3,3,3).contains(position))return box.value("boxId").toString();
        }
        return {};
    }

    void ComputeZRangeLocked() {
        double lo=std::numeric_limits<double>::max(),hi=std::numeric_limits<double>::lowest();
        for(size_t i=2;i<m_points.size();i+=3) {
            const double z=m_points[i];
            if(!std::isfinite(z))continue;
            lo=std::min(lo,z);hi=std::max(hi,z);
        }
        if(lo>hi) {m_zMin=-0.5;m_zMax=2.5;}
        else if(hi-lo<1e-3) {m_zMin=lo-0.5;m_zMax=lo+0.5;}
        else {m_zMin=lo;m_zMax=hi;}
    }

    void FitLocked() {
        m_needFit=false;
        if(m_points.empty() || width()<=0 || height()<=0) {m_center=QPointF(0,0);m_scale=45.0;return;}
        std::vector<double> xs,ys;
        xs.reserve(m_points.size()/3);ys.reserve(m_points.size()/3);
        for(size_t i=0;i+2<m_points.size();i+=3) {
            if(!std::isfinite(m_points[i]) || !std::isfinite(m_points[i+1]))continue;
            xs.push_back(m_points[i]);ys.push_back(m_points[i+1]);
        }
        if(xs.empty()) {m_center=QPointF(0,0);m_scale=45.0;return;}
        const auto percentile=[](std::vector<double> &values,double q) {
            const size_t index=size_t(q*double(values.size()-1));
            std::nth_element(values.begin(),values.begin()+std::ptrdiff_t(index),values.end());
            return values[index];
        };
        const double x0=percentile(xs,0.01),x1=percentile(xs,0.99);
        const double y0=percentile(ys,0.01),y1=percentile(ys,0.99);
        const double spanX=std::max(0.8,x1-x0),spanY=std::max(0.8,y1-y0);
        const double usable=0.84;
        m_scale=std::clamp(std::min(double(width())*usable/spanX,double(height())*usable/spanY),3.0,400.0);
        m_center=QPointF((x0+x1)/2,(y0+y1)/2);
    }

    QVariantMap BuildViewLocked() const {
        return QVariantMap{{"scale",m_scale},{"centerX",m_center.x()},{"centerY",m_center.y()},
                           {"frame",m_frame},{"points",double(m_points.size()/3)},
                           {"zMin",m_zMin},{"zMax",m_zMax}};
    }

    double GridStepLocked() const {
        for(double step:{0.5,1.0,2.0,5.0,10.0,20.0,50.0})
            if(step*m_scale>=26.0)return step;
        return 100.0;
    }

    void PaintGrid(QPainter *painter) {
        const double step=GridStepLocked();
        const QPointF topLeft=ToWorldLocked(QPointF(0,0)),bottomRight=ToWorldLocked(QPointF(width(),height()));
        painter->setRenderHint(QPainter::Antialiasing,false);
        const auto vertical=[&](double x,bool axis) {
            painter->setPen(QPen(QColor(axis?"#1f4a63":"#12283c"),1));
            const double screenX=ToScreenLocked(QPointF(x,0)).x();
            painter->drawLine(QPointF(screenX,0),QPointF(screenX,height()));
        };
        const auto horizontal=[&](double y,bool axis) {
            painter->setPen(QPen(QColor(axis?"#1f4a63":"#12283c"),1));
            const double screenY=ToScreenLocked(QPointF(0,y)).y();
            painter->drawLine(QPointF(0,screenY),QPointF(width(),screenY));
        };
        const double lowX=std::min(topLeft.x(),bottomRight.x()),highX=std::max(topLeft.x(),bottomRight.x());
        const double lowY=std::min(topLeft.y(),bottomRight.y()),highY=std::max(topLeft.y(),bottomRight.y());
        for(double x=std::ceil(lowX/step)*step;x<=highX+1e-9;x+=step)vertical(x,std::abs(x)<1e-9);
        for(double y=std::ceil(lowY/step)*step;y<=highY+1e-9;y+=step)horizontal(y,std::abs(y)<1e-9);
        painter->setRenderHint(QPainter::Antialiasing,true);
        QFont font=painter->font();font.setPixelSize(11);font.setBold(false);painter->setFont(font);
        painter->setPen(QColor("#7fa6c2"));
        painter->drawText(QRectF(10,height()-26,320,18),Qt::AlignLeft|Qt::AlignVCenter,
                          QString("网格 %1 m · 传感器系 XY · 十字为原点").arg(step,0,'g',3));
    }

    static QColor RampColor(double t) {
        struct Stop {double at;int r,g,b;};
        static const Stop stops[]={{0.0,40,60,160},{0.35,30,150,170},{0.7,120,210,90},{1.0,250,220,90}};
        t=std::clamp(t,0.0,1.0);
        for(size_t i=0;i+1<sizeof(stops)/sizeof(stops[0]);i++) {
            if(t<=stops[i+1].at) {
                const double span=stops[i+1].at-stops[i].at;
                const double k=span>1e-9?(t-stops[i].at)/span:0.0;
                return QColor(int(stops[i].r+(stops[i+1].r-stops[i].r)*k),
                              int(stops[i].g+(stops[i+1].g-stops[i].g)*k),
                              int(stops[i].b+(stops[i+1].b-stops[i].b)*k));
            }
        }
        return QColor(250,220,90);
    }

    void PaintPoints(QPainter *painter) {
        if(m_points.empty())return;
        static constexpr int buckets=16;
        std::vector<QPointF> groups[buckets];
        const double span=std::max(1e-6,m_zMax-m_zMin);
        const double limitX=double(width())+4.0,limitY=double(height())+4.0;
        const size_t count=m_points.size()/3;
        const size_t stride=count>200000?count/200000:1;
        for(size_t i=0;i<count;i+=stride) {
            const double x=m_points[i*3],y=m_points[i*3+1],z=m_points[i*3+2];
            if(!std::isfinite(x) || !std::isfinite(y))continue;
            const QPointF screen=ToScreenLocked(QPointF(x,y));
            if(screen.x()<-4 || screen.y()<-4 || screen.x()>limitX || screen.y()>limitY)continue;
            const int bucket=std::clamp(int((z-m_zMin)/span*buckets),0,buckets-1);
            groups[bucket].push_back(screen);
        }
        painter->setRenderHint(QPainter::Antialiasing,false);
        for(int i=0;i<buckets;i++) {
            if(groups[i].empty())continue;
            painter->setPen(QPen(RampColor(double(i)/(buckets-1)),1.4));
            painter->drawPoints(groups[i].data(),int(groups[i].size()));
        }
        painter->setRenderHint(QPainter::Antialiasing,true);
    }

    void PaintBoxes(QPainter *painter) {
        QFont font=painter->font();font.setPixelSize(12);font.setBold(true);painter->setFont(font);
        for(const QVariant &entry:m_boxes) {
            const QVariantMap box=entry.toMap();
            const bool selected=box.value("boxId").toString()==m_selected;
            QRectF rect=BoxScreenLocked(box);
            if(selected && (m_gesture==Gesture::Move || m_gesture==Gesture::Resize)) {
                rect=QRectF(ToScreenLocked(QPointF(m_dragWorld.left(),m_dragWorld.top())),
                            ToScreenLocked(QPointF(m_dragWorld.right(),m_dragWorld.bottom()))).normalized();
            }
            const QString colorName=box.value("color").toString();
            const QColor color(colorName.isEmpty()?QStringLiteral("#ffcf5c"):colorName);
            if(selected) {
                QColor fill=color;fill.setAlpha(38);
                painter->fillRect(rect,fill);
            }
            painter->setPen(QPen(color,selected?2.6:1.8));
            painter->setBrush(Qt::NoBrush);
            painter->drawRect(rect);
            if(selected) {
                painter->setBrush(color);
                const QPointF corners[4]={rect.topLeft(),rect.topRight(),rect.bottomRight(),rect.bottomLeft()};
                for(const QPointF &corner:corners)painter->drawRect(QRectF(corner-QPointF(4,4),QSizeF(8,8)));
                painter->setBrush(Qt::NoBrush);
            }
            const QString person=box.value("personId").toString();
            const QString label=selected
                ?QString("%1 · z %2–%3 m").arg(person).arg(box.value("zMin").toDouble(),0,'f',2).arg(box.value("zMax").toDouble(),0,'f',2)
                :person;
            painter->setPen(color);
            painter->drawText(QRectF(rect.left(),rect.top()-19,std::max(rect.width(),160.0),18),
                              Qt::AlignLeft|Qt::AlignVCenter,label);
        }
    }

    void PaintHud(QPainter *painter) {
        QFont font=painter->font();font.setPixelSize(12);font.setBold(false);painter->setFont(font);
        if(m_gesture==Gesture::Draw && m_drawScreen.isValid()) {
            painter->setPen(QPen(QColor("#ffb267"),1.4,Qt::DashLine));
            painter->setBrush(QColor(255,178,103,32));
            painter->drawRect(m_drawScreen.normalized());
            painter->setBrush(Qt::NoBrush);
        }
        double bar=1.0;
        for(double candidate:{0.5,1.0,2.0,5.0,10.0}) {bar=candidate;if(candidate*m_scale>=70.0)break;}
        const double barPixels=bar*m_scale;
        const QPointF origin(width()-barPixels-24,height()-34);
        painter->setPen(QPen(QColor("#9ab2c9"),1.4));
        painter->drawLine(origin,QPointF(origin.x()+barPixels,origin.y()));
        painter->drawLine(origin,QPointF(origin.x(),origin.y()-5));
        painter->drawLine(QPointF(origin.x()+barPixels,origin.y()),QPointF(origin.x()+barPixels,origin.y()-5));
        painter->drawText(QRectF(origin.x()-24,origin.y()+3,barPixels+48,16),Qt::AlignCenter,
                          QString("%1 m").arg(bar,0,'g',3));
        if(m_points.empty()) {
            painter->setPen(QColor("#c8d8e6"));
            painter->drawText(QRectF(0,0,width(),height()),Qt::AlignCenter,"当前帧没有可显示的点云");
        }
    }

    mutable std::recursive_mutex m_mutex;
    std::vector<float> m_points;
    int m_frame=-1;
    double m_zMin=-0.5,m_zMax=2.5;
    double m_scale=45.0;
    QPointF m_center{0,0};
    bool m_needFit=true;
    QVariantList m_boxes;
    QString m_selected;
    bool m_drawMode=true;
    QVariantMap m_view;
    Gesture m_gesture=Gesture::None;
    QPointF m_press,m_last;
    QRectF m_drawScreen;
    QRectF m_dragWorld;
    int m_resizeCorner=-1;
    bool m_moved=false;
};