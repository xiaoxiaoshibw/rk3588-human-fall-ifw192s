# 可直接递交 OpenCode 的 HF-01 提示词

历史提示词：HF-01 已于 2026-09-30 经第 2 轮复审 ACCEPTED，当前无需重做。下一单使用 [HF-02 提示词](OPENCODE_HF02_PROMPT.md)。下文保留作派发追溯。

```text
请使用我配置的 DeepSeek v4.1 Flash，在 D:\Code\ldiar 完成 HF-01：接口契约与最小采集/健康工具。

HF-00 已由 Codex 按盘点交付范围验收。用户确认没有相机，首版只用 /innolidar_points、辅助 /inno_imu 与 /device_status；不要安装 OpenCV/MediaPipe/RKNN，不创建 CameraInfo、图像或第二台雷达输入。具体 IMU 单位/轴向、点云-IMU 时间偏移、安装旋转仍待 HF-02/03，不能填成已验证。

开工前先记录 Git 分支、HEAD、相关差异与工作树状态，再读取：
AGENTS.md、CLAUDE.md、docs/human_fall/README.md、DISPATCH.md、hardware_inventory.md、IMU_VERIFICATION.md、REVIEW_LOG.md、tickets/HF-01_contract_capture.md、RETURN_TEMPLATE.md。
上面省略根目录的文档都位于 D:\Code\ldiar\docs\human_fall。

必须读取 C:\Users\30680\.codex\skills\ponytail\SKILL.md 并使用马尾辫 skill。支持技能调用则调用 ponytail，否则直接读取遵守；找不到如实报告。优先复用旧 xyz_from_cloud、ROS 标准工具、NumPy 和 unittest，不加不必要的框架。

只实现当前工单：
1. CONTRACT.md：无相机的 lidar_geometry 基线、人工确认的人体样目标、状态/健康 JSON、错误码、时间域、必需点云与辅助 IMU 的区别；未知单位/同步/标定明确 unknown。
2. 最小 ROS1 包 src/human_fall_detection/，只创建工具确实需要的文件。
3. sensor_health.py：检查点云布局/截断/非法值、消息新鲜度、重复/回退 stamp 与 epoch；报告 IMU 原始测量和姿态无效，不伪造单位转换或有效四元数。
4. 有限时长录制工具：复用 rosbag，录上述三路与 /human_fall/health，生成 manifest；没有 TF 时写待标定，不等待不存在的话题。
5. 有效回归测试：非对齐 timestamp@18、point_step=26、填充行/大小端/截断、零/NaN 点、全零四元数、时间回退、点云停流/辅助 IMU 停流、严格 JSON 与 manifest。

保留已有用户修改，尤其 publish_manager.cpp 拼写修复和 src/CMakeLists.txt 软链接；不重置、不提交、不推送。远端驱动源码和本地不同，不覆盖远端驱动、厂商库、网口、自启脚本或已运行雷达服务。

ROS 验证用已授权 SSH wel@192.168.3.125（或既有别名 ldiar-wel），容器 slam-localization，Python 3.8.10/NumPy 1.17.4。先确认 live 状态，只部署本单新增包与必要构建产物；进行 ROS 构建及 5～10 秒短 bag 再读验证，不自动升级环境。每个采样命令都要显式超时并保存实际命令/退出码，缺数据标阻塞。

不实现人体检测、跟踪或跌倒算法；不发布车辆控制，不启动 HF-02。不把近零角速度当 rad/s 证据，不把相近时间戳当已同步，不把 abnormal_flag=255 解释成已确认的故障含义。

按 RETURN_TEMPLATE.md 写 returns/HF-01.md，状态 SUBMITTED 或 BLOCKED，附本次差异、测试/构建命令与退出码、短 bag 内容和再读结果、日志路径、未验证项。原始 bag 留在授权设备/指定本地输出目录，不提交源码仓库。
最后返回交付文件与证据路径，等待我转交 Codex 审查和冻结契约；不得自行标 ACCEPTED 或继续下一单。
```
