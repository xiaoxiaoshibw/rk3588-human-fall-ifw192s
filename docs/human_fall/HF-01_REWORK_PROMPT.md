# HF-01 第 1 轮返工要求

日期：2026-09-30（Asia/Shanghai）。审查者：当前 Codex。结论：**REWORK；CONTRACT.md 仍为 DRAFT，HF-02 未放行**。

以上为第 1 轮历史结论。**第 2 轮已由 Codex 复审 ACCEPTED，R1–R7 闭合；本文件已完成，不再派发。** 当前结论见 REVIEW_LOG.md，下一单为 OPENCODE_HF02_PROMPT.md。

请在 `D:\Code\ldiar` 按原 HF-01 返工，不启动 HF-02。先读 AGENTS.md、DISPATCH.md、CONTRACT.md、returns/HF-01.md、REVIEW_LOG.md，并读取 `C:\Users\30680\.codex\skills\ponytail\SKILL.md`。记录开工前工作树；保留驱动拼写修复、顶层软链接和已有采样。不要重置、提交、推送或覆盖旧 bag。

## 已通过的部分

Codex 独立复跑本地 13 项测试通过；提交的板上测试、构建和 8 秒 bag 日志可对应，6 个源文件哈希与提交部署记录一致。非对齐 timestamp@18、26 字节点步长、填充行和大小端解析、点云必需/IMU 辅助、禁止 NaN/Inf、未知单位/同步和原始 abnormal_flag 的基本方向通过。单位、物理同步和安装关系仍按原计划归 HF-02/03，返工不要求提前解决。

独立复现命令：

```powershell
python -B -W error docs/human_fall/evidence/review_hf01_codex.py
```

当前 6 个测试方法均失败（含子测试共 8 个断言失败），退出码 1；这是对现存缺陷的复现，不是原 13 项测试失败。日志：`evidence/2026-09-30_hf01/09_codex_review_boundaries.txt`。脚本只用合成数据、线程屏障和任务自己的临时目录，不操作真实 ROS 进程或 bag。修复后保留同等行为断言，不能删除或放宽断言来通过。

## R1 / P1：同名 session 可覆盖既有证据

位置：`src/human_fall_detection/scripts/record_session.py`，`main` 建立 bag/manifest 路径后直接调用 `run_record`。

触发：输出目录已有 `<session>.bag`、`<session>.bag.active` 或 `<session>.manifest.json`，再次指定同一个 session_id。当前仍启动 `rosbag record -O`，且 `save_json` 替换原 manifest。独立测试用临时哨兵文件复现：录制函数仍被调用，原文件被替换。真实 rosbag 用 Write 模式写 active 文件，结束后改名到目标文件；没有会话保护。

要求：启动录制前拒绝已有会话产物，采用最小的独占会话预留方式防止两个录制者同时通过检查；默认失败退出并保留旧数据，不添加默认覆盖行为。失败运行也不得把旧 bag 当成本次产物重写 manifest。回归检查旧 bag、active、manifest 冲突及并发会话预留；只用临时目录，不对已有 hf01_verify 数据做覆盖实验。

## R2 / P2：并发快照混合新时间和旧布局

位置：`sensor_health.py` 的 `HealthMonitor.note_cloud/note_imu/note_device/snapshot`。

触发：ROS 回调在更新 `TopicTracker` 后、更新该帧 payload/epoch 前被发布线程切换。独立线程屏障复现：新帧 stamp=11.0、实际布局 truncated，但 snapshot 给出旧帧 `layout.valid=true` 和 `observability=valid`。Python 的 GIL 不使多次属性赋值成为一个原子操作。

要求：用一把普通锁保护完整 monitor 更新与 snapshot，或原子替换完整帧记录；解码可在锁外完成，提交结果和 epoch 必须一致。snapshot 的可变结构也须避免发布期间再被修改。不要增加线程框架。保留屏障测试，使快照仅包含完整旧帧或完整新帧。

## R3 / P2：非法当前 stamp 被替换为上一帧时间

位置：`sensor_health.py` 的 `TopicTracker.note`，`if status != "invalid"` 分支。

触发：先输入 (10,0)，再输入 (0,0) 或非法 nsec。当前 `stamp_status=invalid`，但 `source_stamp_s=10.0`，接收计数、frame_id 和点云内容已经属于新帧。这违背“当前源时间保留原样、无效数值 null”的契约，也会污染后续时钟分析。

要求：当前帧的 `source_stamp_s` 在非法时为 null；用于判后续单调性的上一合法 stamp 独立保留。为原始 sec/nsec 明确表示与验证规则，不能用上一帧替代坏输入。检查每个 topic 的相同路径，恢复后的比较仍用上一合法 stamp。字段若调整须同步 DRAFT 契约。

## R4 / P2：manifest 必填校验与精确 schema 不一致

位置：`record_session.py` 的 `build_manifest`；CONTRACT.md 第 9 节。

触发：`software={package:...}` 缺 version，或传入仅含一个键的 sync/calibration/config，当前均被接受，生成缺少契约必填字段的 JSON。`bag.readable=true` 时空 summary 也未验证内容。现有用例只检查顶层几处，不覆盖嵌套 schema。

要求：逐项明确并校验实际需要的字段/类型/null/枚举，尤其软件版本、两个 sync 布尔值、units、calibration、labels/config 路径与哈希、可读 bag 的 summary 和 topic 名称/类型/非负计数。省略可选对象可以生成完整 unknown/pending 默认对象；提供不完整或非法对象应拒绝。用少量标准库检查即可，不引入 schema 框架。拒绝非有限数值与非法哈希，测试序列化和写入路径。

本轮健康消息 session_id 是 `health_20260930_144334`，录制 manifest 是 `hf01_verify`；labels 实际为 `{path:null,sha256:null}` 而非整个 null。契约须明确监视会话与录制会话的关系、标签对象实际形态及 bag summary 的接收时钟域，避免把设备 stamp、节点 monotonic 和 bag 记录时间混用。第 6 节 state/event 尚为后续草案，不能把未定义字段类型/名字的部分一起宣称冻结；本次冻结范围应明确到已实现的 health/manifest 与共同规则。

## R5 / P2：提前 Ctrl-C 的终止原因被写成 duration

位置：`record_session.py` 的 `main` 调用 `build_manifest`。

触发：`--duration 10` 运行中提前 Ctrl-C，`run_record` 返回 interrupted=true，退出码为 130，但 manifest 的 termination 仍为 duration。独立 mock 复现了完整 main 写盘路径。

要求：termination 根据实际停止原因填写，保留 requested duration；中断后仍正常关闭并再读 bag。增加短时 SIGINT 真机验收，记录退出码 130、实际消息数和 manifest 的 sigint；不要对雷达服务发信号。

## R6 / P2：install space 缺少默认配置

位置：`src/human_fall_detection/CMakeLists.txt`；`sensor_health.py main` 的默认配置解析。

当前只安装两个脚本；默认节点通过 rospack 读取包内 `config/default.yaml`，配置未安装。在只使用 install space、没有源码目录的环境，节点默认启动会找不到配置。提交构建日志的 `devel/lib` 是 Catkin 包装脚本，`--help` 在读取配置前退出，不能证明安装启动已验证。

要求：用最小 CMake install 规则安装 config 目录。以隔离 staging/install 环境或静态安装清单检查验证默认路径，不替换活动驱动、厂商库或远端服务；若没有实际运行 install 环境，注明验证层级。

## R7 / P2：协方差全零与姿态可用性判定不完整

位置：`sensor_health.py on_imu` 与四元数判定调用。

`orientation_covariance_zero` 当前只测试 covariance[0]==0，矩阵 [0,0,0,0,1,0,0,0,1] 会被误报全零；单位四元数且 covariance[0]==-1 仍被当可用姿态。ROS Imu 定义要求首元素 -1 时忽略对应估计；全零是整个矩阵的性质。[官方消息定义](https://github.com/ros/common_msgs/blob/noetic-devel/sensor_msgs/msg/Imu.msg)

要求：检查全部 9 项是否为零；明确处理姿态不可提供标志 -1，保留全零 covariance=unknown 的原规则。不要用 covariance 全零否定六轴测量，也不要借此启用未经 HF-02 验收的融合。测试实际 callback 到 payload 的路径，并同步 reason/schema 文档。

## 回传要求

继续使用 HF-01，在 `returns/HF-01.md` 追加第 2 轮修复清单与测试/部署哈希，不删第一轮 SUBMITTED 及原日志。新增日志编号或独立日期目录，保留 00–11。回传：原 13 项与独立边界检查、本地/板上结果、健康输出、短 bag 与提前 SIGINT bag 再读、配置安装验证和命令/退出码。无须重新证明 HF-02/03 的未知物理量；源代码/契约修复后状态写 SUBMITTED，仍由 Codex 判断冻结和 ACCEPTED。
