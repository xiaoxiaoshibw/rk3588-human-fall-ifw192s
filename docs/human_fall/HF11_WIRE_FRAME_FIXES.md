# HF11预览实际代码复核：先修复线格式/帧/协议门控

继续同session ses_f0c1d2e43ffeMDoXiXAHqpVYqQ，不重做HF07。Codex仅暂停本次CLI6032提供具体源码问题，原Node/packaging/5方法修复保留；原活动页面/驱动不改，仍仅预览。

1. hfSendRequest目前组包5+JSON.length，只包含client opcode1/channel id4/JSON。encoding=ros1、schema=std_msgs/String要求数据体还包含uint32 little-endian UTF8字符串长度，然后才JSON。应为opcode1+channel4+string_len4+JSON。缺4字节使bridge反序列化BufferOverrun，请修复并做实际通过浏览器/同编码客户端→ROS请求→正确request_id回执的链路，不能只serverInfo/advertise。
2. hfFrame仅seq相等，pcPrevSeq=null也判aligned，未用原始secs/nsecs/session/epoch与bounded raw-frame缓存，重复seq/reboot或无点云可叠假框。记录原点云header seq/sec/nsec、当前实际呈现帧和接收时刻；无呈现帧一律无框，精确源帧匹配才叠。旧帧/跨epoch/session清缓存/框/待选择；有限6–8帧缓存或明确等待匹配，过期灰/隐藏。目标框也同样处理，不能用当前seq给旧source矩阵绿框。
3. hfOnMessage/hfRenderState目前无schema/kind/有限数字校验，schema999+upright或非有限向量可直接绿显/报toFixed异常。候选/state/event/ack各独立校验必要结构/版本/有限三轴/bbox/枚举及source；非法/未知只unknown，隐藏当前框/位置，不把既存事件删掉。DOM状态数据同步处理过期/乱序/断连，不能按到达晚就回滚新selection_version/epoch。
4. 预览hfPrefix硬编码/human_fall，而真实验证节点输出/hf07_verify/*、输入/hf07_verify/points。提供仅诊断需要的URL配置prefix和points_topic（默认生产正常），让预览实际匹配验证数据，而不是原点云+另一命名空间状态。公开预览URL、活跃测试节点/输入及截图/测试分界，synthetic明确标记，不替换生产首页。
5. 当前UI把clientPublish直接显示给用户，改请求通道可用/不可用。保留原数字但IMU单位标原始量待核验，255含义未知，不显示已证实异常。使用可见点云中心/雷达坐标/站姿参考高度措辞，不说人体身高/世界标定已通过。状态可中文，原因友好，日志保留必要诊断。

补真实JS有效检查（可提取纯组包/帧键/校验/投影函数用既有Node跑，不能仅grep存在），覆盖ROSString字节长度、DPR/viewport投影、无云/同seq不同stamp/跨epoch、未知版本/NaN、旧回执/重连/过期。合法候选DOM列表可键盘/鼠标选择，与拖框同一服务端路径；源frame和后端回执是权威。普通问题自修；只新增必要代码，不新网站/前端框架。

尽快闭合后完成HF07/11回传SUBMITTED，给Codex可访问已连接实际链路的预览（不靠前端假动画），当前线上confirmed仍false，默认等待未验证地面/基线是正常诚实边界。原冻结helpers、158+前18/本5边界不破坏，失败日志保留。用户不需搬运或批准常规问题。
