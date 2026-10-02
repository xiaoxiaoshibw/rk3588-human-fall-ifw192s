# 工单审查记录

日期：2026-09-30（Asia/Shanghai）。审查者：当前 Codex。

最新状态：HF-00 第 2 轮盘点交付 **ACCEPTED**（经文档证据边界修正）；用户确认无相机，计划已改为点云几何与辅助 IMU。单位/时间转 HF-02，安装与地面转 HF-03，内部双目形态可后续查资料。HF-01 **READY**，尚未实现或派发。下面保留前序审查过程。

## HF-00 / Luna 静态盘点

回传：[returns/HF-00.md](returns/HF-00.md)。审计：[LUNA_AUDIT.md](LUNA_AUDIT.md)。

### 第一轮：要求修订

- 设备 IMU 的作用须限定为设备运动/静止重力参考，不能把人体冲击写成它直接可提供的证据。
- 用户已明确硬件含双目与 IMU，报告须区分用户说明与源码接入缺口。
- PCAP 回放请求首帧与实际输出时间戳回退不是同一事实，SDK 时间语义仍需实测。
- 简写源码引用补为完整仓库相对路径。

### 第二轮：PASS（仅静态交付）

Luna 已修订以上内容并按统一模板回传。Codex 复核 publish_manager.cpp 的 156～174 行 IMU 转换、source_driver.cpp 的循环请求、SDK SetLocalFrame 声明、现有候选筛选与标定输出，报告主要结论符合当前源码。

源码循环将本地请求索引设为 0 并请求 SDK 首帧，不能据此确定 SDK 输出时钟行为。IMU 转换未赋姿态；SDK 时间注释和发布代码解释相矛盾，单位尚未查证。静止标定包无相机订阅或身份跟踪，人体尺寸筛选不能直接当跌倒候选入口。

整张 HF-00 仍为 **BLOCKED / WAIT_DEVICE**：尚无实际板卡环境、双目运行话题、IMU 原始单位/时钟与多传感器记录。没有现场频率、性能、模型能力或跌倒准确率可验收。hardware_inventory.md 与真机日志尚未生成。HF-00 没有标 ACCEPTED。

回传主动说明未事先记录 HEAD，属于追溯不足；后续执行须先记录基线，不能把工作树现存变更归为本轮。Luna 报告的路径/行号检查属于静态检查，测试/构建/设备采样均 NOT_RUN。

## 计划与工单包检查

- 已生成 HF-00～HF-10 共 11 张工单、总表、共同执行要求、回传模板与开发计划。
- 独立检查编号连续、每张包含 ponytail 要求、本地 Markdown 链接可解析以及新增文档无空白错误；通过。
- 本轮仅新增 docs/human_fall/ 文档。没有实现新检测算法，没有运行 ROS 构建，也没有改变现有用户源代码修改。
- 所有后续工单为待执行或等待依赖；外部 DeepSeek 尚未收到自动派发，需由用户递交。其完成后按同一模板回传再审查。

## 下一步

先把 [HF-00 真机部分](tickets/HF-00_sensor_inventory.md) 与 [共同要求](DISPATCH.md) 交给有授权设备访问的 OpenCode 执行者；回传设备证据后复审，再冻结 HF-01 契约。若无法访问设备，可先写契约草案与纯函数代码，涉及同步/标定/模型性能的验证继续保留未完成状态。

## 用户授权 SSH 后的补充审查

Codex 已连接 wel@192.168.3.125，取得并保存四份运行日志；Luna 整理主机表，Codex 复核后补齐 hardware_inventory.md 的 ROS、网络、设备映射和源码版本差异。没有改远端服务/配置、传感器参数或源码。

PASS（运行环境与接口探测）：RK3588、Ubuntu 20.04.6、约 8 GB、Noetic 容器、Python 3.8.10/NumPy 1.17.4；当前 publisher 声明及在线配置、网络链路与主机 RKNPU 枚举有日志证据。容器无可导入 cv2/推理库，未见视频/DRM 设备映射。

WAIT_STREAM（有效数据和双目）：各 5 秒窗口点云/IMU 未收到消息，ROS 图未出现图像/深度/CameraInfo。eth2 无 carrier，但未现场确认雷达接线。不能据此确认 IMU 有效单位/姿态，不能认定设备可提供双目输入，也不能绝对否定网络或专用相机硬件。

第一轮 ROS 探测末尾配置读取脚本出错，已保留失败日志并由后续独立读取补齐；不把该轮标为整体成功。HF-00 当前 BLOCKED 原因为出流与硬件接口证据不足，已不再是 SSH 不可达。外部工单提示词已更新，下一步仅补未确认项。

## IMU 源码与独立实测复核

用户进一步要求确认 IMU 是否存在。Codex 追踪 RegisterImuCallBack → PutImuMsg → ProcessImuMsg → SendImuMsg → ROS 转换；当前节点没有外部 IMU 订阅，源码不通过 Timer 合成默认 IMU 数据。SDK 解析实现位于预编译 .so，只有头文件/二进制符号可检查，不能声称已读完整解析源码。

独立实时检查确认在线模式、唯一 publisher 为 /inno_lidar_node；4.02 秒接收到 902 条 IMU、39 帧点云，IMU 接收约 226.766 Hz，时间戳递增、测量值有限且变化。PASS：真实六轴输出已确认。现有全零四元数无效，state 未在包装链检查；后续 HF-02 处理有效性，不在本轮改驱动。

同时发现 OpenCode HF-00 新回传及原始采样，独立结果与其出流结果一致。其“静止角速度近零证明 rad/s”“数值时间域相近证明同一设备时钟”证据不足：近零不能判尺度，同域数量级不能替代同步/偏移测量。已在 hardware_inventory.md 补充边界，不把此两项升级为 ACCEPTED。双目/相机的实体含义未因 IMU 出流而得到证明。

## HF-00 第 2 轮正式移交审查

用户已移交 OpenCode 回传，并明确项目没有相机。Luna 只读复核 A–Q，确认 17/17 文件非空、索引可对应；Codex 检查 M/N/P、源码与工作树差异，并与独立实时采样交叉验证。原始日志未改写。

### 已验证交付

RK3588/Ubuntu20.04/Noetic 容器拓扑、源文件与运行配置差异、三路短时出流、26 字节点布局/offset=18、零点/稀疏标志、IMU 全零四元数、一帧 header=首点 timestamp 均有证据。本轮 source_driver/publish_manager 的相关差异没有新增算法；既有一行拼写修复保留，Catkin 顶层软链接在 Windows 无法 diff 的限制已注明。

### 已修正的问题

1. IMU 模长只有数量级证据，近零角速度不能确认 rad/s；单位/轴向/偏置仍未知。
2. 相近 stamp 和 frame_id 不能证明同一硬件时钟或零偏移；一帧首点相等不能扩展为全帧/长期保证。
3. Q 标记时间为 13:46:22，属于采集末尾，不能称开工前快照；缺基线的追溯限制保留。HF-01 必须开工前先记录。
4. 未发现图像接口归为运行快照；项目物理无相机归为用户说明。系统仍有通用摄像头/GStreamer 库，不能称完全无相机软件。
5. renderD129 对应 RKNPU，不能因无 /dev/rknpu* 断言无 NPU 内核驱动或把它归为 GPU；用户态推理未测。
6. 未统一保存命令/外层超时/退出码。E/F/G/H/J/O 中失败项保留为失败；P 后续成功只补时间字段比较，不等于补完 O 原始字节转储。自启脚本文本不等于该轮运行过脚本。
7. 独立采集 manifest 模板未交付，划归 HF-01；不把证据索引当已实现录制工具。

上述内容已由 Codex 原位修正文档；源代码、远端服务与原始日志未修改。执行者原始提交状态 BLOCKED 作为历史保留，审查状态由 Codex 写入。

### 结论与放行范围

**ACCEPTED：HF-00 盘点交付范围。** 无相机路线已确定，不再等待相机/CameraInfo。一个已验证点云接口足以启动 HF-01，内部“双目雷达”形态不作为独立双设备输入要求。

单位/时钟偏移/漂移归 HF-02；IMU 安装旋转/地面归 HF-03。这些未验证项不表示已获融合或跌倒算法验收。HF-01 READY，用户可递交 [新提示词](OPENCODE_HF01_PROMPT.md)；本轮没有开始 HF-01、没有冻结尚未交付的 CONTRACT.md，也没有进行外部消息派发。

## HF-01 第 1 轮正式审查 / 2026-09-30

输入：[执行者 SUBMITTED 回传](returns/HF-01.md)、CONTRACT.md、6 个新增源文件及 evidence/2026-09-30_hf01/00–08。已读取根 AGENTS.md、CLAUDE.md、DISPATCH.md、开发计划、HF-01/HF-10 与旧标定包入口；已按 `C:\Users\30680\.codex\skills\ponytail\SKILL.md` 审查。没有委派其他 agent，没有启动 HF-02。

### PASS（明确范围）

- 当前 Codex 独立复跑本地 Python 3.12.10 / NumPy 1.26.4 的 13 项 unittest：退出码 0。沿用已授权 SSH `ldiar-wel`，核对容器仍运行、镜像为 slam-localization:noetic；在板上重新运行同一 13 项测试，退出码 0。板上复跑日志：[10_codex_device_tests.txt](evidence/2026-09-30_hf01/10_codex_device_tests.txt)。这是合成测试，不是重新采集真机数据。
- 当前板上 6 文件、驱动二进制、原 bag 的 SHA256 均与提交日志匹配：[11_codex_remote_hashes.txt](evidence/2026-09-30_hf01/11_codex_remote_hashes.txt)。驱动仍为 `0286545f64e76f8435d8da20dcc55e3837eac17d1066415148a2a4c5abb6f3c4`；bag 仍为 `3b9552979478a5882897d8a37d3831bdca09970f21c3a58fa0000ac3876afd29`。
- 审阅 02/05/06/07：部署哈希、catkin_make=0、正常健康样本、1936 条消息的短 bag 和再读结果可以对应。当前复核未重跑 ROS 构建、未启动健康节点或录新 bag；正常路径的运行结论来自提交原日志，现存源文件/二进制/bag 完整性由本次独立哈希支持。
- 复用旧 xyz_from_cloud、非对齐 double timestamp、填充行/大小端、必需点云与辅助输入区别、严格 JSON 输出、原始 abnormal_flag 和 unknown 单位/同步边界符合路线。六轴单位、真实同步、安装/地面待 HF-02/03，不是本次返工原因。
- 原驱动差异仍为用户的一行拼写修复；顶层 Catkin 软链接未操作。没有修改生产源文件、部署新包、重启服务、提交或推送。远端只执行容器状态读取、纯函数测试和哈希读取。

### REWORK（阻止本轮冻结）

| 编号 | 优先级 | 缺陷与触发 | 最小修复要求 |
|---|---|---|---|
| R1 | P1 | record_session.main 未拒绝已有 bag/active/manifest，同名录制可重写已有证据 | 录制前独占预留会话；冲突失败且保留旧文件；失败运行不能重标旧 bag |
| R2 | P2 | monitor 回调与 snapshot 无同步，可发布新 stamp + 前帧有效布局，掩盖当前截断帧 | 完整更新/epoch/snapshot 同步；解码可锁外完成 |
| R3 | P2 | 收到非法当前 stamp 后 source_stamp_s 仍为上一帧 10.0 | 当前无效 stamp=null，保留原始字段语义；上一合法比较基线独立保存 |
| R4 | P2 | build_manifest 接受缺 software.version 或嵌套 sync/calibration/config 必填键的对象 | 按精确 schema 检查类型、必填/null/枚举、计数/哈希和 strict JSON；明确会话/时钟域及冻结范围 |
| R5 | P2 | --duration 10 提前 Ctrl-C，退出 130 但 termination=duration | 按实际 interrupted 写 sigint，保留请求时长；增加中断 bag 再读 |
| R6 | P2 | CMake 仅安装脚本，默认配置未进入 install space | 安装 config；明确 devel 包装脚本与真实 install 验证区别 |
| R7 | P2 | on_imu 只用 covariance[0]==0 判全矩阵零，且 -1 不可提供姿态标志未影响 orientation_usable | 检查 9 元素及 -1 标志，保留全零协方差未知语义；测试 callback |

R1–R5 有独立可运行复现：[review_hf01_codex.py](evidence/review_hf01_codex.py)。6 个测试方法均失败，子测试合计 8 个失败断言，退出码 1，见 [09_codex_review_boundaries.txt](evidence/2026-09-30_hf01/09_codex_review_boundaries.txt)。其中会话覆盖用任务临时文件和 mocked recorder，SIGINT 使用 mocked interrupted 返回值；并发快照用线程屏障强制现实中可发生的切换点，未声称在现场已经观察到竞态。R6 为 CMake/路径静态审查，未运行真实 install 环境；R7 为 ROS callback 与 [官方 Imu 定义](https://github.com/ros/common_msgs/blob/noetic-devel/sensor_msgs/msg/Imu.msg) 的静态核对，原 13 项仅检查四元数纯函数与全零样本，未覆盖该 callback 分支。

关于采集时长：已核对 [Noetic rosbag Recorder 源码](https://github.com/ros/ros_comm/blob/noetic-devel/tools/rosbag/src/recorder.cpp)，无消息队列时也会检查时长，未把“普通在线停流必然录制无限挂起”列为缺陷。其时长使用 ROS time；未来暂停仿真时钟/回放的运行语义需在契约说明，不把该情况冒称本轮在线复现。

### 结论与下一步

**HF-01 = REWORK；CONTRACT.md 保持 DRAFT，HF-02 保持 WAIT_DEPENDENCY。** 原 SUBMITTED 回传、00–08 原日志和原 bag 保留。正常构建/采样证明工具基本可用，但不足以冻结当前失效行为和精确 schema。

请把 [HF-01 第 1 轮返工要求](HF-01_REWORK_PROMPT.md) 递交 OpenCode；按原编号追加第 2 轮修复与证据，状态重新 SUBMITTED，由 Codex 复审。审查新增内容仅为文档、复现脚本和 09–11 复核日志；未修补被审代码，保证本次结论与提交哈希可对应。

## HF-01 第 2 轮复审 / 2026-09-30

输入：returns/HF-01.md 的第 2 轮 SUBMITTED、DRAFT 契约（提交哈希 `b31b27c18e2e3e0f6c088274608c843e4da5613639ba3d9c8d9617737af1a99b`）、4 个源文件修复、原样独立边界脚本、12–21 原日志及部署/采样/安装脚本。当前 Codex 复核实际调用链后完成以下检查，生产代码未在审查轮修改。

### 独立检查与证据

| 检查 | 层级 | 结果与日志 |
|---|---|---|
| 本地 Python 3.12.10 / NumPy 1.26.4 回归 | synthetic | 25/25，exit 0：[22_codex_local_tests_r2.txt](evidence/2026-09-30_hf01/22_codex_local_tests_r2.txt) |
| 原独立边界脚本，本地复跑 | synthetic | 6/6，exit 0：[23_codex_boundaries_r2.txt](evidence/2026-09-30_hf01/23_codex_boundaries_r2.txt)；未放宽原断言 |
| 板上 Python 3.8.10 / NumPy 1.17.4 回归 | synthetic on device | 25/25，exit 0：[24_codex_device_tests_r2.txt](evidence/2026-09-30_hf01/24_codex_device_tests_r2.txt) |
| 同一原边界脚本，板上独立复跑 | synthetic on device | 6/6，exit 0：[26_codex_device_boundaries_r2.txt](evidence/2026-09-30_hf01/26_codex_device_boundaries_r2.txt)；脚本经 stdin 执行，使用虚拟仓库内 __file__ 定位，未部署或改变远端代码 |
| 当前本地/板上源文件、驱动、新旧采样哈希 | device / integrity | 6 个源文件与 15/21 提交哈希一致，见 [25_codex_remote_hashes_r2.txt](evidence/2026-09-30_hf01/25_codex_remote_hashes_r2.txt)。驱动仍为 `0286545f…f3c4`，hf01_verify 仍为 `3b955297…afd29`，hf01_sigint_r2b 为 `d7f5779c…fdd9b`，manifest 为 `e51dc13b…f0e5a` |
| 实际 main/on_imu callback，使用合成 ROS 模块与消息 | synthetic | 部分非零协方差、首元素 -1、全零 unknown 三条路径通过，六轴有限性不被姿态标志覆盖；exit 0：[27_codex_imu_callback_r2.txt](evidence/2026-09-30_hf01/27_codex_imu_callback_r2.txt) |
| 提交的 SIGINT、同名会话保护与 bag 再读 | device evidence review | [19_session_sigint_r2b.txt](evidence/2026-09-30_hf01/19_session_sigint_r2b.txt)：实际录制 exit 130、termination=sigint、请求 30 s，bag 6.129 s/1515 条，12 条 health JSON 可解析；重录 exit 1，原 bag/manifest 哈希不变。本轮未再次采集或发送信号 |
| 提交的隔离 install 完整运行路径 | device evidence review | [20_install_check_r2b.txt](evidence/2026-09-30_hf01/20_install_check_r2b.txt)：安装配置存在，rospack 指向 install/share，包含复用的标定解析包，无 --config 运行获得 valid、decode_error=None。脚本确实使用隔离 /tmp 工作区，没有构建活动驱动。本轮未重跑安装构建 |

18 日志中的第一次中断试验录满 30 s，保留为驱动方式失败的历史，不算 SIGINT 成功；19 通过显式恢复子进程信号默认动作后完成了真实中断验收。20 首次 install 只取得 invalid 启动样本，不把它当完整解码成功；20b 增强试验的有效样本才支持完整默认路径。原始失败尝试没有被后续成功抹除。

### R1–R7 闭合

- R1：既有 bag/active/manifest 在录制前拒绝；O_CREAT|O_EXCL reserve 实现同会话独占。冲突的合成和真机检查均保留原文件，reserve 的保留/人工清理边界已写入契约。
- R2：一把普通锁覆盖完整 note_* 与 snapshot；解码在锁外完成，提交和 epoch 在锁内。实际回调提交的新字典随后只整体替换，已发布快照不受后帧替换影响；原屏障测试通过。
- R3：当前非法 stamp=null，当前 raw sec/nsec 保留，last_stamp 独立保存上一合法基线。各 topic 共用修复路径，恢复后的比较测试通过。
- R4：必需软件版本、sync/units 布尔、calibration/file reference、可读 bag 的计数/类型/有限数与哈希检查已落实；默认对象完整。labels 的对象形态、监视与录制会话独立、bag/设备/monotonic 时间域及冻结范围均已明确。
- R5：实际 interrupted 决定 termination，保留 requested duration；合成与真机中断均验证。
- R6：config 的 share 安装规则到位，隔离 install 的完整默认路径有有效数据证据。
- R7：全 9 项协方差零检查和 -1 姿态不可提供标志已接入实际 on_imu；原六轴测量检查保持独立，补充 callback 复现通过。

### 正式结论与冻结

**ACCEPTED：HF-01 接口契约、采集/健康工具的已实现范围。** R1–R7 已闭合，未发现阻止本工单验收的剩余缺陷。CONTRACT.md 基线 `HF01-20260930-R2` 正式冻结，health/manifest 首次正式 schema_version=1；第 6 节 state/event 仍为后续草案。冻结后的字段/语义变更须有版本和消费者兼容策略。首次 DRAFT 采样可能缺新字段，契约补充历史样本兼容说明，不修改原 bag 或 manifest。

本次冻结只更新契约头部/第 10 节和审查元信息；第 3–9 节实现字段及行为正文保持提交版本。已实现数据流/格式健康不等于 IMU 单位、同步、安装/地面或跌倒检测通过；这些仍归 HF-02/03 及后续关卡。未来启用融合前必须取得相应证据。

HF-02 已标 READY，新增 [直接递交提示词](OPENCODE_HF02_PROMPT.md)。本轮没有启动 HF-02、没有外部派发、没有改驱动或远端服务、没有 reset/commit/push。回传的两次 SUBMITTED 与 00–21 原日志全部保留，审查新增 22–27 证据及冻结哈希记录。README、DISPATCH、总表和相关工单已同步。

## 用户目标调整：RK3588 算法与现有 WebUI 联调 / 2026-09-30

用户说明人体已能通过 WebUI 完整成像，希望算法与跌倒检测均运行在 RK3588，最终在网页中实时框选/标定位置并显示是否跌倒。用户回答交互问题，明确选择 **人工选人＋自动跟踪框**。本次授权范围是目标/计划修订；没有开始全部算法/UI 实现。

Codex 用 PyAV 只读解码用户提供的 10.133 s 视频并检查约 4.07 s、9.13 s 抽样帧，可辨人体点云轮廓。原视频未修改，元数据/哈希与本地抽样保存在 evidence/2026-09-30_webui_scope/。人体在页面可见是显示链路证据，不能升级为已有检测/跟踪/跌倒能力。

沿用授权 SSH 只读列出 `/root/catkin_ws/webui`，抓取当前 index.html 到本地证据快照，核对页面使用 Three.js/OrbitControls、Foxglove v1 订阅和原始 XYZ 渲染，当前仅订阅点云/IMU/设备状态。查询 `/foxglove_bridge/capabilities` 返回参数未配置、exit 1，原日志保留；没有把该结果误判为不存在客户端发布能力。后续 HF-11 需核对实际 serverInfo/允许话题并实现选择请求/回执，未更改当前 bridge、页面或远端服务。

新增 [WEBUI_SCOPE.md](WEBUI_SCOPE.md) 确定板端/浏览器职责、选人/站姿基线与安装标定区别、三维框/位置定义、源帧关联与旧快照/断连失效规则、界面和最终验收。新增 [HF-11](tickets/HF-11_webui.md)，并同步 README、DISPATCH、HF-03/04/05/07/08/09、总表与 HF-02 提示词。工单总数现在为 12；顺序为 02 → 03 → 04 → 05 → 06 → 07 → 11 → 08 → 09 → 10，00/01 继续 ACCEPTED，HF-02 继续 READY。

**HF-01 的 CONTRACT.md、生产代码和冻结哈希保持不变。** 新候选/选择/标定回执和位置框结构在独立文档中明确为 DRAFT，不偷加 health v1 字段，不宣称未实现的 state/event 已冻结。本轮没有算法运行、测试性能或 UI 验收；验证仅为视频/源码检查和文档链接/状态一致性。真实联调须回传板端结果、bag/参数版本及对应网页录屏，由后续关卡验收。

## HF-02 第1轮正式审查 / 2026-09-30

输入：执行者 [BLOCKED 回传](returns/HF-02.md)、新增 core 三文件与23项测试、publish_manager.cpp 差异、evidence/2026-09-30_hf02/00–14。已读取根 AGENTS.md、CLAUDE.md、DISPATCH.md、HF-01 冻结契约、HF-02/10工单、硬件/IMU记录和旧标定入口；使用 `C:\Users\30680\.codex\skills\ponytail\SKILL.md`。没有委派其他agent，没有进入HF-03，也没有修补被审生产代码。

### PASS（明确范围）

| 检查 | 层级 | 结果与证据 |
|---|---|---|
| 原48项测试独立本地复跑 | synthetic | 48/48、exit0，[15_codex_local_tests.txt](evidence/2026-09-30_hf02/15_codex_local_tests.txt)。使用本机既有Python3.12，不构建Windows ROS工作区 |
| 同一48项板上复跑 | synthetic on device | 核对slam-localization仍运行、镜像slam-localization:noetic，使用现存 `/tmp/hf02_verify` 隔离副本；48/48、SSH exit0，[20_codex_device_tests.txt](evidence/2026-09-30_hf02/20_codex_device_tests.txt) |
| 当前提交源文件/冻结资产哈希 | integrity | core三文件、测试、驱动源码及HF-01工具/配置与14提交哈希一致；契约仍为 `eca2fa25…f5e1`，[18_codex_local_hashes.txt](evidence/2026-09-30_hf02/18_codex_local_hashes.txt) |
| 板上隔离源码、活动驱动与新旧bag哈希 | device / integrity | 隔离core/测试/驱动源码与本地一致；活动驱动仍 `0286545f…f3c4`，新bag `6d6b236b…c68f`，旧hf01_verify `3b955297…afd29`、hf01_sigint_r2b `d7f5779c…fdd9b`，均吻合；[19_codex_remote_hashes.txt](evidence/2026-09-30_hf02/19_codex_remote_hashes.txt) |
| 提交ROS1构建及采样/再读日志 | device evidence review | 03日志编译publish_manager.cpp并链接成功、内层FULL_BUILD_EXIT=0；08/10记录新bag9.8s/2407条及无效姿态，05/06速率只作传输观测。此次未重跑ROS构建或录制；源码/样本哈希独立核对支持对应关系 |
| 实际C++ helper常见进位与NaN处理 | isolated numeric check | 提取提交helper原样用g++/C++14编译，进位409.9999999996→410/0、NaN→0/0通过；这是ROS无关数值验证，不是ROS1/ROS2全包构建；越界失败见R5 |

未知物理单位/轴向/偏置、物理同步和SDK state均如实保留unknown；没有发现凭静止模长/时间相近开启实际融合的设备证据。orientation_covariance[0]=-1 的源码声明符合 [ROS Imu定义](https://github.com/ros/common_msgs/blob/noetic-devel/sensor_msgs/msg/Imu.msg)。未部署源码，所以在线bag仍全零四元数/cov0=0，不能冒称新驱动运行通过。

原03/04末尾出现CR残留造成shell命令失败，内层构建/测试0不能代表整条SSH链成功；本轮20的独立复跑完整SSH exit0补足测试成功证据。原始失败尾部保留，下一轮同时记录外层/内层退出码。

### REWORK（软件 R1–R5）

| 编号 | 优先级 | 位置、触发及实际结果 | 最小修复要求 |
|---|---|---|---|
| R1 | P2 | timebase.py:313–370；登记imu相对cloud偏移+0.5s后仍按raw stamp匹配，正确100.5样本漏配，存在100样本时错配 | 明确映射方向/流对，证据支持后应用校正；保留raw字段，报告校正残差；禁止把局部证据扩大到所有流 |
| R2 | P2 | timebase.py:164–187、332–372；pair忽略now。snapshot stale或当前cloud invalid后仍返回上一seq paired | 配对入口按正确时间域拒绝过期/非法当前输入，清理不可用观测历史，保留上一合法比较基线和冻结epoch规则；历史分析不得冒充在线有效观测 |
| R3 | P2 | timebase.py:241–252、313–330；受控事件经验同步在stamp100→1、epoch重建后仍verified | 给经验映射绑定适用epoch/流对，时钟重启后撤销或明确重新验证；厂商永久关系与一次经验偏移分开 |
| R4 | P2 | sensor_quality.py:31–51、65–72、102–121；value=None能升级verified并返回static；g/deg_s原值被套SI门限导致静止判moving；缺轴也finite=True | 检查语义值/证据与三轴形状；非SI先证实转换或unknown/明确拒绝，不假定SI；缺失/非法输入不能启用运动/融合判断 |
| R5 | P2 | publish_manager.cpp:48–74及三处赋值；helper接受3000000000秒，赋给ROS2 int32秒字段实测-1294967296 | 按两种ROS实际秒字段检查转换与进位后的范围；保持双分支、三处一致和用户修改；补实际helper边界验证 |

Python独立复现：[review_hf02_codex.py](evidence/review_hf02_codex.py)，7个方法共8个失败断言，本地与板上相同、exit1；日志：[16](evidence/2026-09-30_hf02/16_codex_boundaries.txt)、[21](evidence/2026-09-30_hf02/21_codex_device_boundaries.txt)。板上脚本经stdin执行，导入已核对哈希的隔离core，没有部署新代码或改变活动驱动。原48项没有覆盖这些具体失效条件，不能用其全通过代替边界闭合。

C++独立复现：[review_hf02_driver_codex.py](evidence/review_hf02_driver_codex.py)，提取实际helper而非重写Python同型函数；编译exit0、检查exit1，[17_codex_driver_helper.txt](evidence/2026-09-30_hf02/17_codex_driver_helper.txt)。ROS2秒字段类型已核对 [官方Time.msg](https://github.com/ros2/rcl_interfaces/blob/rolling/builtin_interfaces/msg/Time.msg)。没有ROS2环境，全包构建继续NOT_RUN，不因本地类型级检查宣称ROS2构建完成。

### WAIT_DEVICE 与正式结论

**HF-02 软件部分 REWORK，设备核验继续 BLOCKED；整体未 ACCEPTED，HF-03 未放行。** IMU原始单位/轴向/偏置、安装/同步没有厂商协议或受控实验，融合禁用是正确边界；它们与软件缺陷分开，不要求为通过而猜测。驱动修复未部署，运行时验证仍待设备条件；ROS2构建NOT_RUN。本轮哈希验证不等于重新采集或单位核验。

请递交 [HF-02 第1轮返工要求](HF-02_REWORK_PROMPT.md)，沿原编号追加第2轮软件修复与证据，物理核验不足仍保留BLOCKED。README、DISPATCH、工单总表、HF-02工单与原开工提示词已同步当前状态；returns/HF-02.md只追加审查附记，原回传及00–14证据保留。HF-01冻结契约/工具、被审core/测试/驱动、旧录制和用户资产未改；未重启服务、部署、commit/push或外部消息派发。

## HF-02 第2轮正式复审 / 2026-10-01

**结论：R1/R3/R5 闭合；软件 R2/R4 继续 REWORK，设备核验 BLOCKED，整体未 ACCEPTED；HF-03 未放行。** 输入为 [第2轮回传](returns/HF-02.md)、timebase.py、sensor_quality.py、test_hf02_timebase.py、publish_manager.cpp 与第2轮 00–08 证据及新增 C++ 边界脚本。读取根 AGENTS.md、CLAUDE.md、DISPATCH、冻结契约、HF-02/10 工单和原返工要求，使用 `C:\Users\30680\.codex\skills\ponytail\SKILL.md`。本轮只新增审查证据、返工文档与状态更新，未修改被审生产代码或原回归测试，没有委派其他 agent。

### 独立复核与通过范围

| 检查 | 层级 | 结果与证据 |
|---|---|---|
| 原 Codex Python 边界脚本 | synthetic，本地 Python 3.12.10 | 7/7、exit 0；[09_codex_review_repeat.txt](evidence/2026-09-30_hf02_r2/09_codex_review_repeat.txt) |
| 原回归套件 | synthetic，本地 | 67/67、exit 0；[10_codex_regression.txt](evidence/2026-09-30_hf02_r2/10_codex_regression.txt) |
| 实际 C++ helper 原复现 | isolated numeric check，本地 C++14 | 编译/检查 exit 0；3e9 在默认 ROS2 范围分支为 0/0；[11_codex_driver_repeat.txt](evidence/2026-09-30_hf02_r2/11_codex_driver_repeat.txt) |
| 实际 helper 的 ROS1/ROS2/未定义三变体 | isolated numeric check，本地 | 三变体 BOUNDARY_OK，编译/检查均 0；[12_codex_driver_variants.txt](evidence/2026-09-30_hf02_r2/12_codex_driver_variants.txt)。不是 Windows ROS 全包构建 |
| 本地提交源码、冻结资产与两个原复现脚本 | integrity | 05 清单全部 14 项 MATCH；CONTRACT SHA256 仍 `eca2fa25…f5e1`；[14_codex_hash_integrity.txt](evidence/2026-09-30_hf02_r2/14_codex_hash_integrity.txt) |
| 板上环境、四个被审文件哈希与新增失效复现 | synthetic on device | `welcomtech`，`slam-localization` running / `slam-localization:noetic`；Python 3.8.10 / NumPy 1.17.4。四文件 SHA256 与本地相同，新脚本 2 方法/5 失败断言、SSH exit 1；[15_codex_device_remaining_boundaries.txt](evidence/2026-09-30_hf02_r2/15_codex_device_remaining_boundaries.txt) |
| 板上原回归及原边界脚本独立复跑 | synthetic on device | 67/67、7/7，两个内层 exit 0、外层 SSH exit 0；[16_codex_device_regression.txt](evidence/2026-09-30_hf02_r2/16_codex_device_regression.txt)。使用现有 `/tmp/hf02_r2_verify`，新复现脚本经 stdin 执行，未部署或写入远端源码 |
| 活动驱动完整性 | device / integrity | 本轮板测前后均 `0286545f…f3c4`，见 16；源码修复仍未部署 |
| 提交的 ROS1 构建与全链退出码 | device evidence review | [06_device_checks.txt](evidence/2026-09-30_hf02_r2/06_device_checks.txt) 中先生成消息再构建，实际编译 publish_manager.cpp 并链接，MSG_BUILD_EXIT=0、ROS1_BUILD_EXIT=0、docker 包装与 SSH exit 0；源码哈希对应当前提交。本轮未重跑构建 |

R1：偏移参与校正配对；有序流对、raw stamp、原始 delta 与校正 residual 分开，交换顺序和 raw 近错样本检查通过，局部证据不会赋予另一流对配对资格。

R3：controlled 证据按 epoch 撤销，vendor 永久关系跨 epoch 保留，证据历史可追溯；时钟重启与重新核验测试通过。

R5：helper 按实际 ROS 秒字段选择上限，先查整秒、再查进位，三条转换一致；末秒合法小数与非法输入检查通过。ROS2 全包构建仍 NOT_RUN。补充脚本在通常秒域测进位、在类型上限测整秒越界；double 在秒上限附近的间距大于纳秒，不将上限处不可表示的纳秒进位当作已实测案例。

R2 已通过停流、当前非法源 stamp、配对 now 无效、负 age、过期与跨 epoch 的原测试，但未覆盖当前接收时间非法后的回退。R4 已通过 None/空值、单位枚举、g/deg_s 换算、六轴 3+3 与 bias 六项验证，但轴映射只检查非空字符串，不能闭合全部要求。

### 剩余 REWORK（保留原编号）

| 编号 | 优先级 | 触发、位置与影响 | 最小返工要求 |
|---|---|---|---|
| R2 | P2 | timebase.py:158–163、494–507。seq1 双流 stamp100、receive10；cloud seq2 stamp100.1 的 receive=None/NaN/Inf。last_receive_s 保留10，now10.1 时入口仍 fresh，新条目被筛掉后返回旧 seq1 paired、reason=None。当前接收质量失效没有阻止旧观测冒充有效输入 | 分开保存当前接收质量和上一合法比较基线；当前 receive 非法时 snapshot/pair 明确拒绝并给原因，保留源 epoch 规则；补两路非法时间及恢复合法输入回归 |
| R4 | P2 | sensor_quality.py:63–70。axis_mapping="unknown" 或 "x_forward_x_left_z_up" 均写入 verified，alignment_verified=True；单位有效时静止样本被判 static，未合法的轴映射可解除运动提示门控 | 明确受支持的三轴表示、方向与 from/to 语义，拒绝 unknown/任意文字/缺轴/重复或冲突轴；在状态/evidence 变更前校验，保留合法描述的兼容策略，不猜设备轴向 |

独立新增脚本：[review_hf02_r2_codex.py](evidence/review_hf02_r2_codex.py)。本地日志 [13_codex_remaining_boundaries.txt](evidence/2026-09-30_hf02_r2/13_codex_remaining_boundaries.txt)，板上日志 15：同为 2 个方法、5 个失败断言、exit 1。原7项与67项全部通过不能覆盖这些新增失效路径。R4 静止分类的直接探针见 [17_codex_axis_motion_probe.txt](evidence/2026-09-30_hf02_r2/17_codex_axis_motion_probe.txt)，两种非法轴描述均 alignment_verified=True、motion=static；这证明门控失效，不表示本项目已启用融合。

### 设备与后续边界

IMU 实际单位/轴向/偏置、物理偏移/漂移仍无厂商或受控实验证据，融合继续禁用。ROS1 隔离源码构建成功不能升级为新驱动运行时通过；活动二进制未变。第2轮 [07_device_cold_build_note.txt](evidence/2026-09-30_hf02_r2/07_device_cold_build_note.txt) 已记录冷工作区单遍构建因既有消息生成依赖时序失败，两遍构建通过；本轮没有扩大为构建系统返工，也没有将冷构建失败抹除。

请递交 [HF-02 第3轮软件返工要求](HF-02_REWORK_R3_PROMPT.md)，仅修复剩余 R2/R4，保留已闭合 R1/R3/R5 和两轮回传/证据。README、DISPATCH、总表、HF-02 工单与历史开工提示词入口已同步；回传只追加本轮审查附记。未进入 HF-03、重启服务、部署、修改网口/自启、commit/push 或发送外部消息。HF-01 冻结实现、旧 bag、原证据和用户资产保留。

## 执行流程调整：Codex 直接使用 OpenCode CLI / 2026-10-01

用户授权今后收到其指定的 OpenCode 工单后，由 Codex 直接通过 CLI 派工、跟进执行、读取共享工作区回传、独立复审并续接同单返工，替代用户逐轮手动转交。已建立 [CODEX_OPENCODE_WORKFLOW.md](CODEX_OPENCODE_WORKFLOW.md)，明确单一写入者、指定 session 续接、命令/退出码/源码与证据追溯、独立验收、失败恢复、设备阻塞与下一单授权边界；同步 DISPATCH、README、回传模板、HF-10 和总表。

本机只读核验：CLI 路径 `C:\Users\30680\AppData\Roaming\npm\opencode.ps1`，`opencode --version` 为 1.18.33；`opencode run --help` 支持指定目录/模型/附件、JSON 事件及 session 续接；`opencode models opencode-go` 包含 `opencode-go/deepseek-v4.1-flash`。这些命令没有启动模型执行。尚未调用 `opencode run`、新建或续接实现会话，也没有修改模型、CLI 配置或创建后台自动派工；等待用户提供工单。HF-02 软件 R2/R4 REWORK、设备 BLOCKED 与 HF-03 未放行状态不变，生产代码和 HF-01 冻结契约未改。

收尾完整性核对附注：本轮 Codex 未写入生产代码，但与第2轮提交基线相比，当前 timebase.py、sensor_quality.py、test_hf02_timebase.py 已出现外部更新（本地 mtime 分别为 2026-10-01 00:31:40、00:31:55、00:32:25）；不推断执行者或完成状态，未覆盖或审查这些新改动。当前 SHA256 分别为 `73d505e194d9b9d0b86a6c4ae952503a5bfc70e2cfda2873f6c2c018ef463100`、`06d57e2d7f621802dc40e119b4b123aa43085d5f9cc3d5d5990b50a74c50228a`、`e43b60096b3f415b6826c1aa5bf7c5990e22f17bb7f18640b3fe1621ce7f331c`。其余05清单文件及冻结 CONTRACT 哈希不变。下一次派工前须核对既有执行会话和新回传，避免重复派发；此前第2轮复审结果只适用于当时记录的哈希。

## HF-02 第3轮正式复审 / 2026-10-01

**软件部分 PASS：R1–R5 全部闭合；设备核验继续 BLOCKED，整单未 ACCEPTED，HF-03 未放行。** 输入为第3轮 SUBMITTED 回传、三个 Python 文件、未变 C++ 源码与第3轮00–09证据。本轮按用户授权直接读取共享文件并完成独立复审，不再要求用户手动转回；软件复审未发现剩余返工项，因此没有重复启动 OpenCode CLI 实现任务。使用已读取的 ponytail 技能，遵守单一写入者与既有设备权限；未修改被审生产代码或原回归测试。

### 独立复核与证据

| 检查 | 层级 | 结果与证据 |
|---|---|---|
| 第2轮原失败脚本，不改断言 | 本地 synthetic | 2/2、exit0，[10_codex_remaining_boundaries.txt](evidence/2026-10-01_hf02_r3/10_codex_remaining_boundaries.txt) |
| 原7项边界 | 本地 synthetic | 7/7、exit0，[11_codex_original_boundaries.txt](evidence/2026-10-01_hf02_r3/11_codex_original_boundaries.txt) |
| 原回归套件 | 本地 Python3.12.10 synthetic | 72/72、exit0，[12_codex_local_regression.txt](evidence/2026-10-01_hf02_r3/12_codex_local_regression.txt) |
| 独立三轴定义域与非法更新检查 | 本地 synthetic | 2/2、exit0；216种组合恰好接受24个右手旋转，非法更新不覆盖已有合法映射/证据；[13_codex_axis_domain_audit.txt](evidence/2026-10-01_hf02_r3/13_codex_axis_domain_audit.txt) |
| 当前本地提交及冻结资产哈希 | integrity | 07清单17项全部 MATCH，包括C++、三个原复现脚本和 CONTRACT；[14_codex_local_hashes.txt](evidence/2026-10-01_hf02_r3/14_codex_local_hashes.txt) |
| 板上环境、隔离源树及原断言完整性 | device / integrity | `slam-localization` running、镜像 `slam-localization:noetic`、Python3.8.10/NumPy1.17.4；隔离树16项源码/测试/配置/脚本哈希与本地一致。对第2轮/第3轮测试 AST 比较，原42个HF-02方法未变，仅新增5项；[16_codex_device_review.txt](evidence/2026-10-01_hf02_r3/16_codex_device_review.txt) |
| 板上独立回归、原边界与原失败脚本 | synthetic on device | 同一隔离树 `/tmp/hf02_r3_verify`：72/72、7/7、2/2；REGRESSION_EXIT/ORIGINAL_BOUNDARIES_EXIT/R2_BOUNDARIES_EXIT均0，外层SSH exit0；见16 |
| 板上独立三轴补充检查 | synthetic on device | 新脚本经stdin执行，未写入远端源码；216种组合/24个合法右手旋转及非法更新保护均通过，2/2；见16 |
| 活动驱动完整性 | device / integrity | 本轮检查前后均 `0286545f…f3c4`；见16。未部署、未重启服务 |
| 实际diff和C++检查/构建证据 | evidence review | [09_code_diff_r3.txt](evidence/2026-10-01_hf02_r3/09_code_diff_r3.txt) 对哈希已核对的第2轮树给出实际diff，仅R2/R4及新增测试；diff exit1表示存在差异。C++仍 `1b3d5793…b787`，引用此前独立三变体数值检查与第2轮ROS1两阶段构建；第3轮04/05/06也记录C++数值检查通过，本轮不重复编译或全包构建 |

新增独立脚本为 [review_hf02_r3_codex.py](evidence/review_hf02_r3_codex.py)，以维度排列奇偶性和方向符号验证旋转，独立于实现中的叉积校验。没有把216种夹具组合计入72项回归，也没有将板上合成测试称为实际轴向/运动实验。

15首次板测包装在前置哈希阶段要求隔离包含CONTRACT.md，但该文档未随执行者隔离包上传，因FileNotFoundError/SSH exit1提前结束，未执行测试；[15_codex_device_review.txt](evidence/2026-10-01_hf02_r3/15_codex_device_review.txt) 保留。修正审查包装，将CONTRACT明确限定为本地哈希核验，16才是完整成功的板测；没有降低源码/测试断言或将15误记为通过。

### R2/R4 闭合与兼容边界

R2：当前 `receive_status` 与上一合法接收时间/源stamp基线分开。None/NaN/Inf接收时间使snapshot stale，并带 `<label>_receive_time_invalid`；pair返回 `input_receive_invalid` 和非空具体原因，不能回退旧缓存。两路输入、首次坏帧、合法恢复及源stamp仍独立控制epoch均有检查。新增字段/失败状态已在回传注明，仅影响未冻结timebase模块，HF-01 health/manifest冻结输出未改。

R4：只接受明确的 `x_<direction>_y_<direction>_z_<direction>`，from为IMU传感器轴、to为参考系方向；未知/缺轴/重复/平行或反向冲突/镜像映射均在状态与证据变更前拒绝，既有合法值兼容。24种支持的轴映射只是轴对齐的带符号排列，不能表达任意安装角度，也不是当前设备真实轴向的测量证明。单位换算、六轴3+3及静态背景门控保持此前已审范围，融合不会因描述语法合法而自动启用。

R1/R3/R5此前已闭合，相关原回归与源文件完整性保持。**未发现阻止软件范围验收的剩余缺陷。**

### WAIT_DEVICE 与流程结果

IMU实际单位/轴向/偏置和点云↔IMU物理偏移/漂移仍缺厂商约定或受控证据；实际安装与运行时验证也未完成，融合继续禁用。驱动修复未部署、ROS2全包NOT_RUN，不能用软件PASS升级整单ACCEPTED。

当前只等待这些具体设备条件，不再递交第3轮软件返工提示词。HF-03依然等待前置验收且本轮未获启动授权。README、DISPATCH、工单/总表、历史提示词入口与CLI工作流现状已同步；三轮原回传/证据全部保留，仅追加审查附记。后续同单若出现软件返工，Codex按已授权CLI闭环直接派发并复审，无需用户转发；不为已通过的实现启动重复会话。本轮未commit/push、部署、采集或发送外部消息。

## 用户授权持续开发与HF-03第1轮复核 / 2026-10-01

用户新授权在HF-02软件PASS后继续顺序开发，常规问题自主解决，目标今晚交付，Codex直接使用OpenCode CLI、不需要用户搬运；允许独立点云几何路线继续，IMU和实际物理证据不足仍不启用融合/虚构验收。已建立AUTONOMOUS_RUN.md保存阶段、实际session、进程与恢复信息；session ses_f0cbba8e8ffeUVpsyHE7V6qdck，模型opencode-go/deepseek-v4.1-flash。

HF-03第1轮新增几何/地面/离线标定、独立配置与19项回归。早期独立检查复现薄SVD内存、留出硬门控和产物结构问题（5方法3失败），已直接在同一CLI会话修复，无用户转发；执行者两端91回归及5独立方法通过并SUBMITTED，未部署。实际bag分析的全部场景留出RMS1.439m不能独立推出平面必然不可信，物理地面仍未验证。

Codex继续独立审查发现混合场景误拒：400精确地面点+140非地面场景点、正确法向和1.5m高度，训练支持0.765，仍因全部场景点RMS/过高留出支持阈值被拒。review_hf03_codex.py扩展为6方法、1失败；新增用例没有改原5断言。第1轮软件仍REWORK（此项），已直接通过同session派发HF03_CODEX_R2.md，证据目录2026-10-01_autonomous_hf03_r2。修复完成后独立复核并顺序推进HF04–06；未将物理未知量当作已验证。

CLI本次运行临时使用PowerShell7的shell配置，未改用户全局配置；初次旧PowerShell5引号错误和过短SSH超时日志保留。独立成功SSH实测26.09秒，后续工具给至少120秒。恢复同session，无并行源码写入、无重复派工。

## HF-03第2轮软件正式复审PASS与继续开发 / 2026-10-01

混合场景误拒已修复，全部场景统计与地面支持质量分开；家具/人体点不会直接成为地面拟合误差，另一平面/缺支持仍拒绝。薄SVD有界内存和产物校验修复保留。Codex独立本地92/92回归和6/6边界通过（本轮10/11），板上同样92/92及6/6、11项隔离源码/配置/脚本哈希匹配、活动二进制仍0286545f…，外层SSH0（14_codex_device_review.txt）。本地源码哈希见12_codex_hashes.json，HF-01冻结工具/配置/契约未改。13首次包装错误要求隔离包包含未上传且未改的C++源码，在前置阶段退出；失败保留，14才是完整成功复跑。

软件范围PASS，几何接口语义记录GEOMETRY_CONTRACT.md。真实bag支持0.242、支持地面RMS约0.019m仍低于默认支持率0.5，所以未报有效地面；全场景RMS1.439m保留为统计，不能独立推出伪平面。真实外参/IMU/地面物理仍NOT_VERIFIED，整单未ACCEPTED，融合禁用。按用户最新自主推进授权，允许以已审软件接口继续HF04–06；不因物理未知量而编造参数或开启confirmed。

回传只追加复审附记、保留两轮及早期失败。常规返工已由Codex直接续CLI完成，无需用户转发。后续继续单一写入者与独立复核，用户无需逐单批准软件步骤。

## HF04–06第1轮独立复审与直接返工 / 2026-10-01

OpenCode session ses_f0c87fac6ffeKE1MYpxoZMnwXa完成候选/跟踪/选择/基线/特征/状态机及回放，三张回传SUBMITTED、INTERACTION_CONTRACT.md DRAFT；执行者两端146回归通过。Codex实际追踪组合调用链后独立新增14方法，共15失败断言（NAN/Inf两个子例），日志第1轮09–11：超时后匹配绕过失锁、预测重复积分；未来/非法接收快照可选、未知请求schema/错误epoch可执行；切人旧基线ready及人工确认允许完整低卧ready；静态基线差代替真实下降、预测中断后同事件重复；重置原因粘住导致新目标一直unknown；回放默认自动选最大簇。

软件REWORK，新增接口尚未冻结。已直接续接原CLI session派发HF04_06_CODEX_R2.md，第2轮证据2026-10-01_autonomous_hf04_06_r2。独立断言不修改，前HF01–03的92项冻结回归保留；草案协议收紧可补齐合法夹具字段与明确的模拟初始选择，不降低验证强度。源码无并行写入，无用户转发；普通问题自动处理，修复复审后继续HF07/11。真实物理/标签和confirmed门控边界保持。

## HF04–06第3轮软件独立复审PASS / 2026-10-01

OpenCode已按R1–R6及最后两个基线完整绑定/固定时钟域条件返工。Codex独立本地158回归/16边界通过，源代码进一步核对后在单写者状态下将prediction_age_s改成从最后合法实测计时（原实现从首次丢帧计，可能少报年龄），补两条独立年龄/过期例；最终本地/板上158回归和18独立边界全部通过。最终11+核心源码的哈希逐一匹配，证据第3轮13–16，外层SSH0。新独立隔离树/tmp/hf04_06_codex_final保留原执行者测试树；未部署，原始回传和失败保留。

软件范围PASS，INTERACTION_CONTRACT.md冻结已实现纯模块、候选、请求与回执语义，并约定HF07合并target_state投影；ROS包/运行/页面仍待本阶段实测。真实物理/人工标签/性能模式未验收，confirmed默认禁用，未将合成事件算真实跌倒。继续依用户授权直接派发HF07/11，先隔离节点与实际网页预览，独立复审后可回退推广；无用户转发步骤，无改驱动/网络/厂商库/自启/原bag或commit/push。

## HF07/11独立软件复审及实际浏览器修复 / 2026-10-01

OpenCode第3轮完成，Codex独立177回归/5节点组合/18时序/12网页协议通过。实际浏览器连接10Hz、0丢帧，解除位置清空、候选选择回执、基线pending→ready→upright通过，均为synthetic隔离输入。额外发现并修复断开后旧绿色状态及无目标显示实测；刷新后实际断开变unknown/请求不可用，截图和完整说明在第1轮16/17证据。小UI变化由Codex单写者完成，原活动首页不变。拖框手势未实测，物理/标签未验收，confirmed/融合禁用。软件允许继续HF08/HF09，整单不虚标真人ACCEPTED。

## HF08第2轮独立软件复审PASS / 2026-10-01

Luna session ses_f0b78f0f6ffez18d7PSN69mbE3完成评测。独立4方法确认跨epoch负例/观测分母不合并、跨epoch事件不误计、schema bool拒绝；本地186回归全部通过，评测器哈希7a97ce4f…c936。确定性手算事件表与真实四bag待标注清单分开；无真实精确率/召回率，不虚标100%。软件允许继续HF09；真实物理/标签和冻结性能门槛缺证据，不称全票ACCEPTED。板上Python3.8回归由后续部署复核。

## HF-09实现回传与部署测量 / 2026-10-01

OpenCode在同一工单完成后回传SUBMITTED（详见 returns/HF-09.md 与 evidence/2026-10-01_autonomous_hf09_r1/）。按 `HF09_CODEX_EARLY.md` 与 `HF09_PROFILE_REVIEW.md` 闭合：

- ROS三时钟边界：节点始终monotonic并拒绝`mode.replay`；worker计算后再读monotonic，过期帧只发stale/unknown；请求取core锁后再取时钟。新增纯`frame_age_exceeded`与可注入`now_fn`，本地独立watchdog 5/5（原3失败）通过。
- 嵌套状态一致性：`status_state`/`_state_payload`在`observability=invalid`时经`_mask_unobservable`统一把`fall_status`置unknown、隐藏position/range/bbox/预测、`target_features.observable=False`、`fall_state`一致；已存历史事件保留，输入恢复按合法实测重建。
- 测量口径整改：只读observer改读节点自报`performance`块（node monotonic receive/start/finish、frame_count、queue_dropped、input_valid、ground_valid、fall_status），按`(session,epoch,seq,secs,nsecs)`去重；改用`LatestFrameQueue.dropped`而非输入减输出；duration/window限有限正、延迟样本有界、坏JSON/未知schema/重复输出不计有效；observer差值单列，不冒称处理延迟。
- 部署：正式页`/human_fall/index.html`复用`../three`/`Orbit`、默认`/innolidar_points`，旧首页与preview未动；`deploy_human_fall.sh`版本目录+符号链接回滚、PID文件cmdline校验、无pkill/删目录；合成两进程按配置/PID精确停止，driver`0286545f…f3c4`未变。
- 实测：本地203/203、独立5+5+4+18通过；板上202/202。正式节点无真实地面→`degraded`+`unknown`+position null，不伪造地面。30分钟真实点云有限统计：input 9.647 Hz、processed 8.718 Hz、节点处理p50 75.6/p95 146.1 ms、队列覆盖累计4122、RSS 86.8 MB、温度51℃；代表回放12帧0.509s全unknown。浏览器FPS/端到端与真实标签/门槛NOT_RUN/NOT_VERIFIED，只作测量交付，不标ACCEPTED。

待Codex按CLI闭环独立复审本回传、差异与证据；本工单不自关。

## HF09第1轮最终独立复审：部署与真实WebUI返工 / 2026-10-01

watchdog5/5根端通过，实际1800.35s统计交付可信范围为节点monotonic处理/队列/资源；原记录保留。独立分析180行：CPU时间加权约102.8555%（单核100%基准），RSS82.816–89.461MiB、首末+0.723MiB，SoC温度51–60℃；不能把最后51℃冒称全程峰值。首10s队列2461、末4122，仅两行间增1661，完整窗口初值未存。证据codex_profile_analysis.json。原30min不可直接当新版传输修复的基准。

最终代码发现release未保存core，实际start来自可变外部devel树；rollback只还原参数/页面，软件REWORK。profile严格元数据独立3方法6失败1异常（schema bool、坏header截断/抛错、negative/bool时间），已交HF09_CODEX_R2，后续现已独立3/3PASS但还未整体验收。Windows203/板202需同树复测原始日志。

实际IAB正式真实49k输入7.8Hz/9.4MBs、每3sSend buffer limit reached、drops32→448、源框等待匹配；synthetic80点PASS不能代替真实链路。截图codex_real_before_transport.jpg，已释放订阅。HF09_REAL_WEBUI要求轻量ROS候选投影（不污染缓存）、8帧原始源帧缓存/同源呈现与严格上下文/过期守卫，原完整算法和driver不改；HF11真实链路当前REWORK。仍同OpenCode session直接续接，无用户搬运或commit。

## HF09第2轮实现回传（R2）/ 2026-10-01

OpenCode按HF09_CODEX_R2与HF09_REAL_WEBUI最小改动返工，SUBMITTED（详见returns/HF-09.md第2轮与evidence/.../hf09_board_checks_r2.txt）。

- **不可变bundle**：release存core/scripts/config+冻结解码器并写manifest；start/profile以PYTHONPATH优先bundle并校验`core.__file__`/`sensor_health.__file__`在release内，devel仅提供ROS依赖。实测节点cmdline指向`<release>/bundle/scripts/human_fall_node.py`。
- **精确PID/回滚**：pidfile记`node|config`，kill前同时匹配才停；指向driver的伪pidfile→stop exit1且driver存活。实际`start(C)→rollback(B)→start`通过；legacy无bundle回滚exit6、指针不变；release先校验链接再原子切换、版本保留无删目录。
- **profile输入严格**：strict整数schema/epoch/header，坏header返回None不抛异常，`_ms`拒绝负数/bool/NaN/Inf，queue_dropped记baseline/total/delta；独立review_hf09_profile_codex 3/3。
- **同树回归**：Windows与板同步后均207/207，原始stdout/stderr留档（R1的202vs203即当时板未同步新增用例）；网页纯检查human_fall/preview各16。
- **候选投影/帧对齐**：`project_snapshot_for_ros()`发新dict去`evidence_indices`（真实帧34424B→5296B，-84.6%，原缓存不变）；页面缓存8帧原始点云，只呈现最新已有处理输出的源帧（前向不回退、>800ms回退最新raw显示点云+unknown），session/epoch/断流清缓存，raw接收Hz与呈现Hz/未呈现分开；`hfPred`锁但无有效position显示“无有效观测”。
- **边界**：候选投影只减候选话题，原始点云~9.4MB/s仍是主要带宽，send-buffer是否缓解待Codex正式页复测；抽样流备选未实施。真实地面/标签/门槛NOT_VERIFIED，无算法改动，本工单不自关。

## HF09第3轮实现回传（R3：可视化抽样流/显示键守卫/部署核验）/ 2026-10-01

OpenCode按HF09_CODEX_R3与HF09_DISPLAY_KEY_REVIEW最小改动返工，SUBMITTED（详见returns/HF-09.md第3轮、evidence/.../hf09_board_checks_r3.txt）。

- **只读抽样显示流**：新增`/human_fall/display_points`（stride4/≤12000）；算法仍用全量`/innolidar_points`解码/候选；`sample_point_data`按point_step整点抽样、organized用row_step处理padding、非法布局不发布。字段/单位/端序/坐标不变。
- **真实wire映射**：探针证实rospy重写`header.seq`；节点publish后读回真实wire seq，配`source_topic`/原`source`/`topic`/stride/原·显示点数写入`visualization`块。真实订阅探针60/60帧wire_seq+source stamp匹配，fields/point_step保持，display width=12000。
- **显示键严格守卫**：`objectKeys(obj, selectedTopic)`按所选topic隔离（source_topic仅S、display topic仅D且source必须一致、其他/错配返回[]、无mapping保留S）；前端所有匹配传实际`POINTS_TOPIC`；`?points=/innolidar_points`全流诊断可用。独立review_hf09_display_keys.js PASS。
- **前端**：默认显示流；统计“显示流/呈现/未呈现/抽样/帧龄(接收后)”；`rxMs`=原包接收monotonic、另存`presentedAtMs`；断流/未知schema/旧epoch清缓存；录制提示抽样≠全量bag。
- **部署**：manifest排除自身/__pycache__/pyc（self_listed=0、sha256sum -c OK）、start/profile先校验；profile另记`profile.cmd`并拒绝重复observer；实际rollback→B2→rollback→C通过；driver`0286545f…f3c4`未变。
- **回归**：Windows与板同源211/211；独立hf09 5/5、profile 3/3、hf07 5/5、hf08 4/4、hf04_06 18/18、display_keys PASS；网页纯测试human_fall/preview各18。浏览器带宽长测NOT_RUN，由Codex实际复测；真实标签/地面/门槛NOT_VERIFIED。

## HF09/HF11/HF10最终软件复审PASS / 2026-10-01

最终211本地/板回归、44独立Python边界、18网页纯检查及display-key独立脚本通过。真实ROS完整源/显示wire/状态三方67帧配对0错误（1捕获边界缺一侧不算错）；活动bundle20261001T051310Z/PID26591的12项关键源/资源SHA与本地完全一致，清单0、外层SSH0，driver0286545f…f3c4/旧首页e68dea…未变。源/显示dense均false，原解码器差异与冻结版本固定详HF10。代码版本回滚/错误PID拒绝实际验证。

实际浏览器轻量流持续8.2–8.8Hz、2.5–2.7MiB/s、drop0且无buffer overflow，有源帧候选框；选择几何簇回执接受、解除清位置。最后独立复现并修复candidate_id逐帧复用在失锁时误投影另一簇位置，短预测只来自原轨迹，lost/ambiguous隐藏几何。软件范围PASS，HF10回传记录完整结论；真实性能标签/地面/IMU/可信背景/门槛未验收，confirmed融合关闭，不给整项目ACCEPTED。最终GUI与停止测试订阅状态详最终浏览器记录。没有commit/push或driver部署。

## GL-00启动与用户暂停 / 2026-10-01

用户成组授权GL系列；Codex核对基线、指定DeepSeek v4.1 Flash探针MODEL_PROBE_OK/exit0后派发GL-00，同session ses_f096ebb32ffe6JPAKA1RK6JfQE。完成只读数据分析及用户单独批准5秒/50帧/100MB范围内的47帧采集，bag独立重读/大小/哈希一致。CLI最终exit0但工作区外技能比较被OpenCode自身external_directory规则自动拒绝，最终回传未产生；无独立PASS，不派GL-01。

用户明确“等我先测数据你再动工”，现PAUSED_USER。生产src/webui及冻结契约哈希未变。当前候选d约1.292m与用户粗估2m存在差异，待雷达中心垂直尺量、机器人实测高度及地面ROI确认；不得据此假标定。完整真实失败/内外退出码、session/证据路径、恢复待审项见evidence/2026-10-01_gl00_r1/CODEX_PAUSE.md。此次为启动/暂停记录，不替代GL-00回传或方法验收。

## GL-00 R4 Codex独立复审 / 2026-10-01

用户明确恢复开发，雷达向下看为最新安装事实，机器人总高1.4m/眼球离地约1.1m。R3参数/ceil/证据措辞返工后，R4软件方案、合成参数协议与兼容契约PASS；真实数据/物理BLOCKED，仅放行GL-01合成原型，不允许实际标定启用或部署。Codex独立13协议检查exit0、完整SHA核查src/webui/冻结资产未变；R2布局脚本修订与原版本保留已记录。p=.999/w=.2预算861；逐验证区域门槛、采样up_axis基底、源索引不泄漏等补充见evidence/2026-10-01_gl00_r4/CODEX_REVIEW.md。R2主动中断、R3 CR错误与旧失败保留，未造真实PASS。

## GL-01 R4独立软件复审PASS / 2026-10-01

显式约束RANSAC、数值CLI与加载器经Codex244回归/12独立方法exit0及同SHA板端244验证，软件PASS；真实bag源索引/帧组适配、ROI与物理BLOCKED，未部署。原9/10独立失败已闭合，两次API400在同DeepSeek session压缩后恢复，日志保留。hardware_inventory.md外来人工截图约26度粗估保留，不据此标实测。详evidence/2026-10-01_gl01_r4/CODEX_REVIEW.md。允许串行GL02数学软件/未核验候选预览，不升级真实外参/IMU/confirmed。

## 最新用户派工方式与GL02 R1复审 / 2026-10-01

用户要求“接下来任务让我手动给cluadecode”。后续改为用户手动交Claude Code；Codex只准备具体工单/独立复审，不自动调用OpenCode继续返工或派后续。当前GL02 OpenCode R1已结束exit0，Codex262常规回归通过但独立6方法6失败，软件REWORK/真实物理BLOCKED，GL03未放行。手动下一步为AI_PROMPT_GL02_CLAUDE_REWORK.md，详细证据evidence/2026-10-01_gl02_r1/CODEX_REVIEW.md与40_*。GL00/01已审软件不重做。无活动实现写入者，不部署/采集，旧失败保留。

## GL-02 Claude R2 Codex独立复审 / 2026-10-01

软件REWORK，GL03不放行；继续用户手动派Claude Code。Codex独立262回归/原6方法exit0；新增集成5方法5失败，补类型检查后最终7方法7失败exit1（evidence/2026-10-01_gl02_r2/50～54）。R2闭合原反例，但实际加载仍可保留旧ground、裸块版本错配；monitor失效仍发布位置/继续相关观测、散点误报整体变化、重标定被一帧清除；float版本/mixed bool矩阵仍通过。详同目录CODEX_REVIEW.md；下一步手动AI_PROMPT_GL02_CLAUDE_R3.md。板端兼容NOT_RUN，真实物理BLOCKED，未改生产算法/部署/采集。

## GL-02 Claude R3 Codex独立复审 / 2026-10-01

R2原七方法/267全回归/R2静态六方法独立通过（GL02 R3 evidence50～52），已闭合部分保留；新增其他入口四方法四失败，补单侧遮挡后最终五方法五失败exit1（55_*）。软件REWORK，设备兼容NOT_RUN/真实物理BLOCKED，GL03不放行。剩余为配套局部更新calibration版本错配/caller引用、同GDID新calibration版本未清旧资格、monitor不可用仍accepted基线请求、10%单侧遮挡误锁存整片变化。详evidence/2026-10-01_gl02_r3/CODEX_REVIEW.md；用户手动下一步AI_PROMPT_GL02_CLAUDE_R4.md，不自动派工。生产算法未由Codex修改，未部署/采集。

## GL-02 Claude R4 Codex独立复审 / 2026-10-01

R3原五方法5/5、R2七方法7/7、静态6/6、fall 271/271、follow 2/2、两个webui各18/18均由Codex独立实跑通过。新增reload/已有pending三方法3失败exit1：空或相同配套reload沿用旧版本却丢input.sha256/evidence/note等完整产物字段；已accepted基线请求在随后monitor持续不可用超过10秒时仍pending且无终态回执。软件REWORK，GL-03不放行；设备兼容NOT_RUN、真实物理BLOCKED。详[evidence/2026-10-01_gl02_r4/CODEX_REVIEW.md](evidence/2026-10-01_gl02_r4/CODEX_REVIEW.md)与57_*。手动下一步[AI_PROMPT_GL02_CLAUDE_R5.md](AI_PROMPT_GL02_CLAUDE_R5.md)；只修这两项，不自动派工。生产源码/原测试/driver差异/Windows软链接表示保留，未部署/采集/commit/push/reset。

## 工作流程v2启用 / 2026-10-01

用户要求重构工作流程，以解决GL02逐轮发现入口/状态缺口造成的返工。现行入口为WORKFLOW.md，GL02统一基线GL02_ACCEPTANCE.md v1：固定已有要求ID/来源，集中盘点入口、消费者和状态转换，实现前一次诊断，单生产写入者，提交SHA后对全表独立复审并集中反馈。冻结范围/语义而不忽略真实缺陷；新需求另列，已有契约漏测明确记审查遗漏。

R5提示词/RETURN_TEMPLATE已改为引用统一验收表；AGENTS/CLAUDE/README/DISPATCH/地面PLAN及GL02/03工单入口已同步，旧CLI流程明确历史属性。保留用户手动交Claude派工方式。只读助手参与流程审核，无并行实现写入者。

本轮只修改流程/模板/入口文档，未修复生产代码或运行新的生产验收。GL02软件REWORK、设备NOT_RUN/物理BLOCKED和GL03未放行不变。旧成功/失败/回传保留；不部署/采集/commit/push/reset。下一轮应先补齐验收表中的无帧/watchdog、恢复、ready及请求重放等待验证路径，不把待验证风险预先判成新缺陷。

## GL02 R5复审、自动R6/R7与最终收口 / 2026-10-02

用户重新授权Codex直接派OpenCode CLI deepseek-v4.1-flash，持续处理工单内修复/流程优化，无需用户转交或例行发问。R5原R4两根因通过，但全表独立检查发现父ID/schema/startup、ready退休、缓存门控、ACK运输四根因；R6已独立通过。Codex最终逐行核对补查pending标定切换，发现清绑定无终态，这是已列v1行的审查遗漏；R7最小修复后闭合，原失败保留。

最终A01–A12软件PASS，D01 NOT_RUN，P01 BLOCKED；详evidence/2026-10-02_gl02_r7/CODEX_REVIEW.md。Codex R7独立2+12方法、R4三方法、R3五方法、fall272均exit0；R6独立R2/static/Claude R5/follow2/UI18+18和未变SHA证据继续有效。64项源码/配置/driver/follow/UI提交SHA与结束一致；R5后仅4生产文件和1回归变更，冻结资产及Windows catkin ReparsePoint保留。未部署/采集/commit/push/reset。GL03软件前置满足，本轮未启动。

OpenCode会话ses_f07cd9a4dffeTqh7fUyhmsUyLO，实际opencode-go/deepseek-v4.1-flash。R6 exit0；R7约200k token后HTTP400 exit1，代码/回归已完成但回传未完成。同模型新probe正常，官方V1 summarize同session/model压缩成功，续接exit0并停止写入。只停止自建41902端口helper。CLI_RECOVERY.md记录紧凑上下文/约120k提前压缩/每一矩阵行证据映射/区分代码与服务失败；不擅自换模型或宣称市场最优成本。
