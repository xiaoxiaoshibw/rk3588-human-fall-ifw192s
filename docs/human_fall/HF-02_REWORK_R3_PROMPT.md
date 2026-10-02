# HF-02 第 3 轮软件返工要求

历史提示词：2026-10-01 Codex第3轮复审已确认本轮要求闭合，软件PASS、R1–R5全闭合；当前设备BLOCKED、整单未ACCEPTED，不重复派发本提示词。最新状态见 [REVIEW_LOG.md](REVIEW_LOG.md)。以下原返工要求保留以供追溯。

2026-10-01，当前 Codex 第 2 轮复审结论：**R1/R3/R5 闭合；R2/R4 仍 REWORK，设备核验 BLOCKED，整体未 ACCEPTED。** 继续原 HF-02，不启动 HF-03。第 1 轮返工提示词与两轮回传、证据保留。

请使用已配置的 DeepSeek v4.1 Flash，在 `D:\Code\ldiar` 仅修复下列剩余问题。先读 AGENTS.md、CLAUDE.md、DISPATCH.md、CONTRACT.md、HF-02 工单、回传与 REVIEW_LOG.md 最新审查；读取 `C:\Users\30680\.codex\skills\ponytail\SKILL.md`。记录工作树、HEAD、范围内文件哈希；保留用户资产、HF-01 冻结实现、驱动既有修复与历史日志。没有默认 commit/push 或部署授权。

## R2 / P2：当前接收时间非法仍回退旧配对

位置：`core/timebase.py::TimeStream.note/freshness`（158–163 行）与 `TimebaseSession.pair`（494–507 行）。

复现：cloud/imu 的 seq1、stamp=100、receive=10.0，登记 vendor offset=0；再输入 cloud seq2、stamp=100.1、receive=None/NaN/Inf，`pair(..., now=10.1)` 仍返回 seq1 的 paired、reason=None。`note` 只在 receive 有限时更新 `last_receive_s`，入口 freshness 沿用旧时间；条目筛选虽然排除了新帧，却允许从旧缓存回退。

最小修复：将当前接收时间质量与上一合法源 stamp 比较基线分开。当前帧接收时间无效时，snapshot 与在线 pair 均不能冒充 fresh/paired；返回非空具体原因，不靠条目筛选绕过当前质量。非法接收时间本身不要擅自递增冻结源 epoch；保留源 stamp 的比较规则。对两路输入分别测试非法接收时间、恢复合法输入、缺失/非有限配对 now、负 age、停流、过期和跨 epoch，保留原已有断言。

## R4 / P2：轴向描述未校验却升级 verified

位置：`core/sensor_quality.py::ImuSemantics.verify`（63–70 行）。

复现：单位证据有效后，`verify("axis_mapping", "unknown", "controlled_attitude")` 或重复轴 `"x_forward_x_left_z_up"` 均成功，`alignment_verified=True`。后续静止六轴输入可进入 static 分支；这未满足原 R4 对有效轴映射的校验要求。非空字符串只证明有文字，不能证明三轴映射合法。

最小修复：明确当前支持的三轴表示与 from/to 语义，可使用有限的受支持描述枚举或最小的三轴映射校验，不需要通用变换框架。unknown/任意文字/缺轴/重复轴/方向冲突/不支持格式应拒绝或保留 unknown，拒绝发生在修改状态与 evidence 前。保留现有合法描述的兼容策略，测试合法值仍可登记、非法值不能启用 alignment/motion。不要猜设备实际轴向，不因此启用融合。

## 原样复现与回传

```text
python -B -W error docs/human_fall/evidence/review_hf02_r2_codex.py
python -B -W error docs/human_fall/evidence/review_hf02_codex.py
python -B -W error -m unittest discover -s src/human_fall_detection/tests -v
python -B docs/human_fall/evidence/review_hf02_driver_codex.py
python -B docs/human_fall/evidence/hf02_r2_driver_boundary_check.py
```

新增独立脚本当前本地与板上都是 2 个方法、5 个失败断言、exit 1；原 7 项/67 项及 C++ 三变体通过，不能放宽原断言。Windows 只运行纯函数/独立 helper 检查；板上沿用已授权 `ldiar-wel` / `slam-localization`，先核对环境、使用隔离副本，记录源码哈希及内外层退出码。不重启或部署驱动、不改网口/自启、不覆盖录制、不保存凭据。

在 `returns/HF-02.md` 追加第 3 轮，使用新证据目录，列明 R2/R4 修复、兼容影响、两端结果与未验证项。无需重复修复已闭合 R1/R3/R5；如未改 C++ 可引用已审查构建证据并明确未重建。ROS2 全包仍 NOT_RUN；实际 IMU 单位/轴向/偏置与物理偏移无厂商/受控证据时继续 BLOCKED，融合禁用。回传写 SUBMITTED，交由 Codex 复审，不自行 ACCEPTED、不启动 HF-03。
