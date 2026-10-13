# 总控制台 USB＋雷达本机联合录制

2026-10-13，HC-JOINT-LOCAL-01，Codex唯一writer，SUBMITTED未ACCEPTED。

## 行为

桌面现有总控制台快捷方式目标保持D:/Code/ldiar/pc_apps/console/dist/Console.exe。重开后新增“USB＋雷达联合录制”。
默认保存D:/Code/ldiar/captures/remote，也可输入本机绝对目录。两路均收到有效数据后才统一开始；停止/定时结束/正常关闭控制台都会收尾文件。任一路失败停止两路，保存错误和部分数据。界面显示帧数、时间、大小、目录和相机画面。

读既有http://192.168.31.58:8081/stream和ws://192.168.31.58:8765，仅GET和Foxglove订阅；没有调用capture_server的板端录制接口，没有ssh、板端部署、服务重启或配置修改。

## 文件与时钟

- camera.mjpeg：依次连接的完整JPEG帧；camera_frames.jsonl记录字节位置、长度、本机monotonic和Unix接收时间。
- radar.ros1：每条记录为uint32 LE长度＋原始Foxglove二进制消息（opcode/subscription/logTime/payload）。保留原始PointCloud2，包括原始字段和float64逐点时间。
- radar_frames.jsonl：原始位置、源帧seq、header stamp、bridge logTime、本机接收时间与转换后点位置。
- meta.json/points.bin：现有回放器使用的28B点格式；逐点时间float32是已有兼容格式，原始精度由radar.ros1保留。仅xyz非有限点从兼容副本剔除，原消息未删点。
- joint.json：开始/停止/完成时间、两路计数、状态、错误、源地址、时钟质量信息。

同时开始不是硬件同步。相机流没有传感器曝光时间戳。设备时钟也尚未锚定到PC时间，雷达传输积压会影响接收时间对齐；本轮不生成逐帧跨模态真值，不将此前CAM-HOT猜测当训练标签。

## 实测

真实Windows PC、既有USB与雷达流，通过Edge/Playwright在总控制台iframe中操作，浏览器pageerror为0。最新自动3秒一段：93相机帧、13雷达帧，兼容点云17,883,992字节，原始雷达16,608,787字节，MJPEG6,544,871字节。手动停止一段：30相机帧、4雷达帧，兼容点云5,503,064字节。完整源seq在已收到区间内无缺号；不代表整个设备时间窗无丢弃或网络无积压。

自动段雷达设备跨度1.243970秒、接收跨度2.594秒，差1.350030秒；手动段差0.877007秒。表明本链路的精确时序对齐仍未解决，不能用接收时间直接证明人体关节对应。会话名和全部机读实测见LIVE_CHECK.json。两段均被现有human_replay_lib._local_sessions识别，文件大小严格等于total_points×28。

第一轮定时结束把收尾耗时计入duration_sec，已改为停止时刻计时，独立保留LIVE_CHECK_first.json。初次Playwright缺默认headless shell，保留LIVE_CHECK_FIRST_BROWSER_UNAVAILABLE.json；改用本机Edge后通过。测试日志汇总脚本首次打印遇Windows GBK编码错误，测试本身均exit0；最终用UTF-8日志保存。

## 验收逐项

| ID | 状态 | 证据 |
|---|---|---|
| JL01 | PASS | console.html实例capture_port；console_html.test.js |
| JL02 | PASS（软件/短录制） | synthetic close/定时、真实自动/手动两段；强制杀进程恢复未验收 |
| JL03 | PASS（实现/短录制） | Recorder仅打开PC文件；GET＋Foxglove subscribe；实际目录见LIVE_CHECK.json |
| JL04 | PASS（格式/列表读取） | 原消息byte-exact合成验证、真实尺寸与现有列表读取；完整视频点云联动回放不在范围 |
| JL05 | PASS（合成） | 启动失败、中途模拟写失败、重复开始、路径/时长/JSON/origin校验 |
| JL06 | PASS | 实际浏览器四张截图、joint.json；精确同步NOT_EVALUATED |
| JL07 | PASS | TESTS.json：联合7项、原控制台7项、JS12项 |
| JL08 | PASS（短录制） | LIVE_CHECK.json；真实动作/长时录制NOT_RUN |
| JL09 | PASS | 两次PyInstaller exit0；最终冻结启动报告与ZIP哈希见RELEASE_CHECK.json |
| JL10 | PASS（范围记录） | README入口、return、SHA与基线；独审NOT_RUN |

## 边界与资源

仅新增本地会话与console功能，不改旧captures、GT、模型、驱动、板端服务。最长3600秒，累计原始＋兼容副本约8GiB上限，剩余空间低于256MiB停止；单消息上限32MiB。正常停止等待网络读超时和文件收尾，UI保持“正在停止并保存”。取消未就绪启动不产生可用回放会话。
异常断电或强制结束进程可能留下未收尾文件，自动恢复未实现；已有原始消息/逐帧索引保留。只验证短时本机写盘与流接收，不宣称长时可靠性、硬件同步、人体识别或跌倒精度通过。

## 实现范围

新增joint_capture.py/html/test.py；在已有console_gui.py增加本机服务和关闭保存，在已有console.html追加入口；Console.spec打包页面，make_release.py加入新源码，README.txt补说明。原控制台文件起始已有用户差异，未重置或覆盖其他功能。
技能实际读取：C:/Users/30680/.codex/skills/ponytail/SKILL.md。无子代理，无commit/push/reset/clean。
