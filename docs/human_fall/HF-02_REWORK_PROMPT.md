# HF-02 第 1 轮返工要求（可直接递交 OpenCode）

请继续原 HF-02，使用已配置的 DeepSeek v4.1 Flash，在 `D:\Code\ldiar` 修复以下 R1–R5。Codex 已审查第一轮回传：**代码 REWORK，设备核验继续 BLOCKED**。不启动 HF-03，不自行 ACCEPTED，不默认 commit/push。硬件未知量不要求猜测或伪造。

先读根 AGENTS.md、CLAUDE.md、docs/human_fall/DISPATCH.md、CONTRACT.md、WEBUI_SCOPE.md、tickets/HF-02_time_imu.md、returns/HF-02.md 与 REVIEW_LOG.md 本轮审查。必须读取 `C:\Users\30680\.codex\skills\ponytail\SKILL.md`，复用最小实现、既有 NumPy/unittest，不引入依赖。开工前记录工作树、HEAD、相关文件哈希和差异，保留用户拼写修复、顶层 catkin 软链接、HF-01 冻结资产与原始 00–14 证据。

## R1 / P2：物理偏移没有参与配对

位置：`core/timebase.py::apply_sync_evidence/pair`，第 313–370 行。

当前 `physical_offset_s` 仅登记，匹配仍比较原始源 stamp。已知 `imu_stamp = cloud_stamp + 0.5 s` 时，cloud=100、imu=100.5、容差 0.01 返回 no_match；若另有 imu=100 的样本，则错误匹配它。

明确偏移方向、适用的两个流、共同时间域与证据来源；只对证实的映射应用校正，保留两路 raw stamp。正确样本应匹配，原始数值近但物理不同步的样本应排除，交换参数顺序也正确。`delta_s` 明确原始差/校正残差的语义。未证实域继续拒绝。不能用全局布尔把针对一个流对的证据扩大到任意注册流；容差/偏移/不确定度必须有限且范围合法，无法支持的漂移转换保持 unknown。

## R2 / P2：停流或当前非法帧仍返回旧配对

位置：`TimebaseSession.pair`、`TimeStream.valid_entries/note`，第 164–187、332–372 行。

`pair(..., now=...)` 完全不使用 now，停流后 snapshot 已 stale，仍返回旧 seq 的 paired；当前 cloud=(0,0) 判 invalid 后仍从缓存返回上一帧观察。有限缓存不等于过期/失效处理。

在线配对使用 monotonic，回放使用调用者消息时间；排除过期、接收时间无效、当前质量无效和跨 epoch 的条目，返回清晰原因。上一合法 stamp 比较基线必须保留，invalid 不擅自递增冻结 epoch；比较基线与可用观测历史分开。显式历史分析若需要，区分其接口/状态，不能默认作为在线有效观测。回放时间回退/重开时不能把负 age 截成 fresh 后复用旧观测。停流、非法帧、辅助晚到不能返回过期配对，更不能无限等待辅助 IMU。

## R3 / P2：时钟重启后仍沿用旧经验同步证据

位置：`TimebaseSession.note/apply_sync_evidence`，第 241–252、313–330 行。

受控共同事件测得的偏移在原时钟 epoch 有效；源 stamp 从100回到1后，虽然缓存清空，sync 仍 verified、旧偏移继续适用。

绑定映射证据的流对、会话/epoch和有效条件。回退/复位等破坏经验映射条件时撤销配对资格并要求重新核验，保留证据历史可追溯。厂商永久时钟关系与一次经验偏移可分开处理；不得不加判断地继承旧偏移，也不要求任意重复帧都重新做物理实验。

## R4 / P2：IMU 已验证标记未保证值和单位可用

位置：`core/sensor_quality.py::ImuSemantics.verify/six_axis_report/device_motion_status`，第 31–51、65–72、102–121 行。

- verify 的 value=None 也会设置 verified，三个空值即可让运动判定返回 static。
- 已证实原始单位为 g/deg_s 后，计算仍直接套用 m/s²/rad/s 门限；真实静止的原始加速度(0,0,1)被判 moving。
- 缺轴数组如 acceleration=[]、angular_velocity=[0,0,0] 被 six_axis_report 标 finite=True，空角速度还会在 max() 抛异常。

验证字段值、单位枚举/转换、轴映射形状与来源；空值、未知/不支持单位和不足三轴不能升级质量。经证实的原始非 SI 单位转换后才比较 SI 门限，或明确返回 unknown/拒绝，不偷偷假定 SI。六轴严格各三项、数值有限，错误输入返回明确无效结果。偏置/安装关系等融合条件单独保留，不能只凭该辅助运动提示启用融合，也不能把设备 IMU 当人体冲击。静态背景同时检查地面/背景，不以单帧静止模长证明无平移。

## R5 / P2：C++ 越界检查没有区分 ROS1/ROS2 秒字段

位置：`publish_manager.cpp::deviceStampToRos` 及三处赋值，第 48–74 行和调用处。

helper 只检查 uint32 上限；ROS2 `builtin_interfaces/Time.sec` 是 int32。输入3000000000经 helper 输出3000000000，赋给 ROS2 秒字段变成负值（本机提取原 helper 编译，实测 -1294967296）。官方定义：[ROS2 Time.msg](https://github.com/ros2/rcl_interfaces/blob/rolling/builtin_interfaces/msg/Time.msg)。

按实际 ROS 秒字段检查范围，纳秒进位后的秒也必须合法；ROS1 可表示的末秒小数不得误判，ROS2 超界返回明确无效 stamp。保持 ROS1/ROS2 条件分支与三条转换一致，不改未经证实的原始时间单位。检查实际 C++ helper 的进位、NaN/Inf、负数、两种秒上限和进位越界；Python 同型函数的测试不能替代 C++ 代码测试。仅有 ROS1 环境时 ROS2 全包构建继续 NOT_RUN，可补类型级边界验证。

## 复现与回传

Codex 原样独立复现脚本：

```text
python -B -W error docs/human_fall/evidence/review_hf02_codex.py
python -B docs/human_fall/evidence/review_hf02_driver_codex.py
python -B -W error -m unittest discover -s src/human_fall_detection/tests -v
```

第一脚本本轮7个方法、8个失败断言，本地与板上同结果。第二脚本提取实际 helper 做数值检查，当前编译0、检查1；它是独立数值验证，不是 Windows 构建 ROS。CXX 可指定真实编译器；跨平台运行时可最小调整编译/执行包装，不修改检查断言。修复函数签名时保留兼容或记录迁移，再增加真实失效用例，不删边界、不降低断言以求通过。

在 returns/HF-02.md 追加第2轮，不覆盖原回传、00–14原日志或Codex15–21复核证据；分别列R1–R5闭合、本地/板上测试、源文件哈希、驱动适用构建、原始证据和未验证项。原03/04日志内层结果0，但末尾有CR shell错误；新证据同时记录外层SSH与内层命令退出码，避免尾部失败被最后echo掩盖。

继续沿用已授权 ldiar-wel/现有容器，操作前核对实际环境；不重启服务/部署活动驱动/修改网口或自启，不覆盖旧bag，不保存凭据。受控姿态/旋转没有现场条件时保持设备 BLOCKED、融合禁用。源代码返工完成可写“软件部分 SUBMITTED / 设备 BLOCKED”，由Codex复审；不要声称实时新驱动已验证，不开始HF-03。
