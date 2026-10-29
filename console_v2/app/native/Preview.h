#pragma once
#include <QObject>
#include <QTimer>
#include <QNetworkAccessManager>
#include <QNetworkReply>
#include <QNetworkRequest>
#include <QUrlQuery>
#include <QImageReader>
#include <QBuffer>
#include <QElapsedTimer>
#include <QPointer>
#include <deque>

// One asynchronous local request at a time; no recorder-status or GUI-thread waits.
class CameraPreview final : public QObject {
    Q_OBJECT
    Q_PROPERTY(bool active READ active WRITE setActive NOTIFY changed)
    Q_PROPERTY(QString endpoint READ endpoint WRITE setEndpoint NOTIFY changed)
    Q_PROPERTY(QString imageSource READ imageSource NOTIFY changed)
    Q_PROPERTY(QString status READ status NOTIFY changed)
    Q_PROPERTY(double fps READ fps NOTIFY changed)
public:
    CameraPreview() {
        clock.start();timer.setInterval(50);
        connect(&timer,&QTimer::timeout,this,&CameraPreview::request);
    }
    ~CameraPreview() override {
        timer.stop();if(reply){disconnect(reply,nullptr,this,nullptr);reply->abort();}
    }
    QImage current;
    bool active() const{return enabled;}
    QString endpoint() const{return base.toString();}
    QString imageSource() const{return current.isNull()?QString():"image://camera/"+QString::number(revision);}
    QString status() const{return message;}
    double fps() const{return frames.size()>1 && frames.back()>frames.front()?(frames.size()-1)*1000.0/(frames.back()-frames.front()):0;}
    void setActive(bool value) {
        if(enabled==value)return;
        enabled=value;frames.clear();sequence=-1;lastBytes.clear();current=QImage();
        if(enabled){message="正在连接相机预览";timer.start();request();}
        else {timer.stop();if(reply)reply->abort();message="预览已收起";}
        emit changed();
    }
    void setEndpoint(const QString &value) {
        QUrl next(value);next.setQuery(QString());
        if(next==base)return;
        if(!next.isEmpty() && (next.scheme()!="http" || (next.host()!="127.0.0.1" && next.host()!="localhost" && next.host()!="::1")
            || !next.userInfo().isEmpty() || next.path()!="/api/preview"))return;
        base=next;sequence=-1;lastBytes.clear();current=QImage();frames.clear();
        if(reply)reply->abort();
        if(enabled)request();
        emit changed();
    }
signals:
    void changed();
private:
    QNetworkAccessManager network;
    QPointer<QNetworkReply> reply;
    QTimer timer;
    QElapsedTimer clock;
    QUrl base;
    bool enabled=false;
    qint64 revision=0,sequence=-1,lastFreshMs=0;
    QByteArray lastBytes;
    QString message="预览未开启";
    std::deque<qint64> frames;
    void request() {
        if(!enabled || base.isEmpty())return;
        if(!current.isNull() && clock.elapsed()-lastFreshMs>1500) {current=QImage();frames.clear();message="相机画面已过期";emit changed();}
        if(reply)return;
        QUrl url=base;QUrlQuery query;query.addQueryItem("after",QString::number(sequence));url.setQuery(query);
        QNetworkRequest req(url);req.setTransferTimeout(1500);
        req.setAttribute(QNetworkRequest::RedirectPolicyAttribute,QNetworkRequest::ManualRedirectPolicy);
        auto *response=network.get(req);reply=response;
        response->setReadBufferSize(2*1024*1024+1);
        connect(response,&QNetworkReply::finished,this,[this,response] {
            const QByteArray bytes=response->isOpen()?response->readAll():QByteArray();
            const int code=response->attribute(QNetworkRequest::HttpStatusCodeAttribute).toInt();
            const QByteArray seqHeader=response->rawHeader("X-Preview-Sequence"),ageHeader=response->rawHeader("X-Preview-Age-Ms");
            if(reply==response)reply=nullptr;
            response->deleteLater();
            if(!enabled)return;
            if(!ageHeader.isEmpty() && ageHeader.toDouble()>1500) {current=QImage();frames.clear();message="相机画面已过期";emit changed();return;}
            if(code==204)return;
            if(code!=200 || bytes.isEmpty() || bytes.size()>2*1024*1024) {
                if(current.isNull()){message="等待相机新画面";emit changed();}return;
            }
            bool validSeq=false;const qint64 nextSequence=seqHeader.toLongLong(&validSeq);
            if((validSeq && nextSequence==sequence) || (!validSeq && bytes==lastBytes))return;
            QBuffer buffer;buffer.setData(bytes);buffer.open(QIODevice::ReadOnly);
            QImageReader reader(&buffer,"JPEG");const QSize size=reader.size();
            if(size.isEmpty() || qint64(size.width())*size.height()>16*1024*1024)return;
            QImage image=reader.read();if(image.isNull())return;
            current=image;lastBytes=bytes;sequence=validSeq?nextSequence:-1;revision++;lastFreshMs=clock.elapsed();
            frames.push_back(lastFreshMs);while(frames.size()>1 && frames.front()<lastFreshMs-3000)frames.pop_front();
            message="连续预览";emit changed();
        });
    }
};
