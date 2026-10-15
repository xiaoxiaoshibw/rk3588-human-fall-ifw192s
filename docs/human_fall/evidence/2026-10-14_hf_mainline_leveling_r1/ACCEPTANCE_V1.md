# HF-MAINLINE-LEVELING-01 · M3′ · 验收 v1

2026-10-14，Windows 离线；用户在本聊天明确授权开始下一阶段。
唯一 writer 为当前 Codex 会话。R3 点集实验由另一会话负责，本轮不写其源码、页面、配置或结果。
使用 ponytail 与 scientific-toolkit-skill；不提交推送、采集、部署、训练、写原 GT 或开启 confirmed。

## 固定实验

源 cap_20261013_094333，参考 cap_20261013_131958。冻结 nominal pitch=26°、roll=0°、参考高度=1.14m。
三臂：原各自四区重新计算；原 094333 四区用于双方；原 131958 四区用于双方。
区域在任何新配准结果产生前固定，不以 fit/holdout 结果挑区域或修改门。
共享 nominal XY 只表示统一选区协议，不证明两次录制看到了同一物理地面。
既有 leveling 的三个 holdout 帧不参加估计。既有 registration 全录制静态诊断保持原口径；不是因果人体运行测试。
新 UUID 派生数据仅落到本证据目录的隔离 workspace；原 captures/leveled/latest 不受影响。
完整复用 leveling.run_job、registration.writeJob/load、reg_gate_v1；不重签伪造 artifact。

| ID | 检查 | 判定 |
|---|---|---|
| ML01 | 原录制、旧 leveling/registration 证据、生产源与冻结门首尾 SHA 相同 | 任何变化即 FAIL；并发变化单列，不静默接收 |
| ML02 | 三臂配置预冻结、两段源 SHA 绑定、无 holdout 调参 | 完整配置/源码/命令/运行时记录 |
| ML03 | 新 UUID leveling，全点源行/非 XYZ 字节保留，XYZ 与变换一致，holdout 源行互斥 | 全量校验；几何不合格显式 FAIL，禁止强行 export/推荐 |
| ML04 | 同一 registration 算法与原门重跑；全项 gate 与实际 loader 状态均报告 | 不因 fit_p90 单项 PASS 宣称 VALID；不推荐 TLS 则 BLOCKED |
| ML05 | SYNTHETIC 契约与相关现有回归；输出拒绝覆盖，非 VALID 融合关闭 | 检查真实拒绝路径、字节验证、原门与 fit_holdout_guard |
| ML06 | 前后比较、失败原因、下一步与可复跑交付 | 工程完成与假设验证分开；不得以实验运行替代人体效果 |
| ML07 | 独立物理地面身份/真实位移/门的科学合理性 | 本轮无独立测量，BLOCKED；一对会话不能定论 |
| ML08 | 人体保留/家具污染/骨架/成品晋级 | 本轮尚无对应完整实验，NOT_RUN；交给后续端到端修复 |

软件各 ID 为自验，不自行 ACCEPTED。M3′ 的结果无论提升或失败都保留；冻结门不得放宽。
