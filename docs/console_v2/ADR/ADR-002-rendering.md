# ADR-002：批量顶点缓冲、显式帧租约与可核验呈现计数

日期：2026-10-24。状态：设计采用，R2/R3验证；性能UNKNOWN。

## 决定

用Qt Quick3D自定义Geometry批量提交一帧顶点，不为每个点创建QML/托管对象。优先验证QQuick3DGeometry Points；不预先用球体实例替代50万点指标。API用法依据[Qt6.5 Geometry文档](https://doc.qt.io/qt-6.5/qquick3dgeometry.html)和[官方点几何示例](https://doc.qt.io/qt-6.5/qtquick3d-customgeometry-examplegeometry-cpp.html)。Points的点大小受后端限制，视认效果与吞吐分别记录；需要另一种画法时写明变化后重测。

原始stride28=XYZI+ring@16+timestamp@20+padding，并非7个float；stride16是XYZI。后台将源帧投影到明确的XYZ/颜色顶点布局，记录过滤点数和来源行。Geometry的stride不是源文件stride，不能混用。坐标变换只作用显示缓冲，源meta/points不写回。

映射帧返回IFrameLease，RawBytes只在本句柄未释放时有效。Retain返回独立拥有权句柄，缓存、投影worker分别持有不同实例，各自幂等Dispose；同一IDisposable实例不能代表多个拥有者。源进入closing后拒绝新读取/Retain，DisposeAsync等待全部句柄归还才解除映射，不能强行关闭并报告成功。V1文件下载另持流租约，不能通过API关闭会话释放仍在发送的文件句柄。

投影worker产生独立IVertexFrameLease（同样Retain/幂等Dispose语义），随后释放自己的源句柄；VM不拿原始数据端口。桥接受Submit后获得一个显示句柄的唯一拥有权。Qt线程复制顶点到Qt拥有的QByteArray后发CopyCompleted(submissionId,generation)，由桥释放输入句柄；实际呈现由另一个Presented事件计时，不混为复制完成。初版禁止fromRawData包装外部内存或保存未持租约指针，GPU只接触Qt副本，故输入归还不需要猜测GPU消费时刻。若将来省掉该复制，必须实现消费完成fence/回收协议并重测。

提交失败/过时代次/取消/Qt关闭时，桥归还其拥有的句柄恰好一次；重复或迟到回调不再归还。关闭按“停止新提交→处理/取消队列并归还→释放Qt副本→等待源租约”顺序收敛，不能先解除映射再等待回调。跨进程槽亦先复制到Qt副本再确认CopyCompleted后复用，除非另有已验证fence方案。

复制语义依据[Qt6.5 QByteArray文档](https://doc.qt.io/qt-6.5/qbytearray.html)：显式长度的数据构造会复制内容，而fromRawData不接管源内存。实现必须验证用的是前者，并将复制耗时纳入UI阻塞/吞吐预算；不能为满足帧率偷偷换成后者。停止时还须释放缓存自己的独立句柄，再等待源关闭，防止缓存pin导致永远等待。

Qt线程提交缓冲/属性，后台处理读取和投影；geometry update与渲染线程同步遵循实际Qt所选路径，不直接在worker改Qt对象。Qt是否复制QByteArray、GPU上传量、缓存命中与峰值在R2测量，不承诺端到端零拷贝。A的C++插件只绘制，不读源文件或执行用例。

## 调度与测试约束

- 顺序1×：有界预取+背压，每个源帧序号可追踪，读取/提交/呈现/取消四种计数分开。播放落后记录时间漂移，不用跳帧满足速度；实现不达预算就FAIL。相机显示不能影响点云帧计数。
- Seek：递增generation，取消旧读请求，提交前检查代次；旧generation的异步回调不改变当前帧或相机。取消不等于播放丢帧，统计原因明确。
- 缓存用字节预算，租约pin住的内存也计入；达到预算时背压/等待，不无界预取整段1GB文件。
- R2静态50万点固定相机路径10秒和动态真实帧更新分别报告；R4全386帧1×0丢帧、漂移≤1帧/分钟、随机200次seek P95≤300ms；R9在实际包上复测。软件呈现计数不替代GPU实际帧与人眼效果，二者边界写明。

## 未选方案与后果

不做逐点跨语言调用、不做JSON/base64帧传输、不把会话整读进托管堆。B方案通过同用户共享内存只读帧槽传顶点缓冲，控制协议见ADR-004；R2B必须测此跨进程额外开销，不能照搬A帧率。
