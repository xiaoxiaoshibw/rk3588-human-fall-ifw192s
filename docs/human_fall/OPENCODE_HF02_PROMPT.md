# 可直接递交 OpenCode 的 HF-02 提示词

2026-10-01：本开工提示词保留为历史。HF-02第3轮软件复审已PASS，R1–R5全闭合；当前仅等待设备核验证据，不重新执行本提示词或 [第3轮返工要求](HF-02_REWORK_R3_PROMPT.md)。设备BLOCKED、整单未ACCEPTED、HF-03未放行；详见 [审查记录](REVIEW_LOG.md)。

请使用我配置的 DeepSeek v4.1 Flash，在 `D:\Code\ldiar` 完成 `docs/human_fall/tickets/HF-02_time_imu.md`。HF-00 盘点和 HF-01 工具已由 Codex 验收；HF-01 的 health/manifest、时间与质量共同规则已冻结，state/event 仍是后续草案。

用户已确认最终目标为 RK3588 算法＋现有 WebUI 人工选人、自动跟踪框/位置、站姿基线与跌倒状态，先读 docs/human_fall/WEBUI_SCOPE.md。UI/框选实现由后续 HF-05/07/11 承担，本单仍只做时间/IMU 核验；保留源帧 seq、raw stamp、session/epoch 的可追溯关系，不静默改冻结字段。

开工前记录分支/HEAD、工作树及相关差异，读取 AGENTS.md、CLAUDE.md、docs/human_fall/README.md、DISPATCH.md、CONTRACT.md、hardware_inventory.md、IMU_VERIFICATION.md、REVIEW_LOG.md、本工单及 RETURN_TEMPLATE.md。必须读取 `C:\Users\30680\.codex\skills\ponytail\SKILL.md`，支持技能调用则调用 ponytail；遵守最小实现原则。

只做本工单的时间域、IMU 语义与失效处理：

1. 确认点云/IMU 原始 stamp 约定，记录 raw sec/nsec 与接收 monotonic。设备 stamp 相近、frame_id 相同或接收时间拟合好，都不能证明物理同步。仅有厂商约定或受控共同事件支持的物理偏移才允许校正；没有证据就保留 unknown，不能伪造 UTC 锚定。
2. 以现有最小包扩展 core/timebase.py 和 core/sensor_quality.py，复用 HF-01 检查。在线 freshness 用 monotonic，离线回放由消息时间推进；有限缓存、超时、重复/回退/跳变重建 epoch 并清历史，不无限等待辅助 IMU。
3. IMU 单位/轴向/偏置用厂商协议或受控已知姿态/旋转核验，不能用静止角速度近零或加速度模长接近 g 直接证明尺度。orientation 全零或 covariance[0]=-1 不可用；六轴单位与姿态有效性分别记录。IMU 是设备运动/重力线索，不是人体冲击传感器；未通过相关验收不得启用融合。
4. 如有证据需要修正驱动，只改 publish_manager.cpp 对应转换，保留用户既有拼写修复和 ROS1/ROS2 分支。核验 sec/nsec 进位、有限值、SDK state/四元数真实语义，不仅因头文件注释就改时间单位。构建在板上完成，未具备另一 ROS 环境注明 NOT_RUN。
5. 冻结字段/语义需要变化时，先在本轮文档明确对应 schema_version 和兼容方案，再实现并测试，不静默破坏旧消费者。第一轮 hf01_verify 是冻结前 DRAFT 采样，可能缺少新字段；保留原 bag/manifest/哈希，离线读取要明确兼容，不改原始证据。

设备沿用已授权 SSH 条目 `ldiar-wel` 与 `slam-localization` 容器，操作前核对环境。Windows 只做编辑/纯函数测试；不保存凭据、不升级系统/ROS、不改网口/自启/厂商库、不重启既有雷达服务，不发布车辆控制。传感器运动核验所需的现场动作没有现成授权或执行条件时，报告所需条件，不编造人工动作和结果。

测试覆盖纳秒进位、非法/重复/回退 stamp、单位错配、偏移/漂移、晚到/停流、姿态无效；本地与板上使用 NumPy/unittest，板上 Python 3.8.10/NumPy 1.17.4。记录源文件/配置版本、命令/退出码、厂商证据、参数来源、原始样本路径/哈希与明确未验证项。使用新 session_id，保留已有录制及 reserve 保护；不把合成测试称为真机验证。

按 RETURN_TEMPLATE.md 写 `returns/HF-02.md`。实际单位无法查清时保持本单 BLOCKED、该路融合禁用；已完成的离线部分仍如实回传。完成且有证据时写 SUBMITTED，由用户将回传与差异交给 Codex 审查；不得自行 ACCEPTED，不开始 HF-03，不默认提交或推送。
