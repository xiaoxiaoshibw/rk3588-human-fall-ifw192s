# GL-03 R3 Codex 独立复审 / 2026-10-02

结论：软件 **REWORK**。R3 闭合原四方法反例和 O01 统计/措辞，但 reference 严格资格及生命周期仍违反 GL03 验收 v1 G03/G04/G05。真实身份 BLOCKED，设备 NOT_RUN；不放行 GL-04。本轮只写新审查证据、现行协调文档和追加审查记录，未改生产源码/原测试/历史证据。

## 基线与证据

master / HEAD `49eb7581faabdda031642e04d3ef4ffe75d48331`。四个提交源码及提交时验收表 SHA 均与 `../22_source_manifest.json` 匹配，结束复核源码仍一致。完整 tracked + untracked 文件摘要在 `00_baseline.json`；Windows `src/CMakeLists.txt` 不可读记录为 UNREADABLE:1920，未触碰软链接。

`20_final_verify.txt`：提交源码一致、R3 开工 79 项基线除声明源码/协调文档/已知外部 replay 外均未变，审查开始至结束全部可读基线文件不变；Python3.8 AST 解析通过，不代表 Python3.8.10/NumPy1.17.4 板端运行通过。`16_end_deltas.json` 为空。`19_final_verify.txt` 保留审查脚本错误：假设外部支线工具仍在原路径；修正为记录缺席后产生独立 `20` 日志，未覆盖失败。

外部 `fall_replay.py` SHA 为 `3f9077737e0074ad7b3d9916131c5b5cd03ef8479886688e0618c26957865cd6`，与提交范围记录一致，保留、不归因。本轮开始时 `scripts/lidata_to_replay.py`、`tests/test_lidata_to_replay.py` 已不在主线，实际文件在 `sidequests/lidata_adapter/tools/`、`sidequests/lidata_adapter/tests/`；未移动/删除/验收这些支线文件。主线本次 discover **306** 通过，而提交时 **312** 包含当时尚在主线的六项外部用例；不能称源码/套件数与提交时完全相同。

使用技能：`C:/Users/30680/.codex/skills/ponytail/SKILL.md`，复用原检查；新证据只覆盖既有 reference 契约遗漏。

## 验收 ID

| ID | 结果 | 证据与边界 |
|---|---|---|
| G01 | PASS | `13_fall.txt` GL03 ReferenceGeometryTest：非零 R/t、实际点 reference AABB、源中心经变换原义；原检查未改 |
| G02 | PASS | `10_geometry.txt` 索引还原 + `13_fall.txt` ground 精确 min/max/median、非对称样本、source 不变 |
| G03 | FAIL | 原 source/from/to/ground 四方法通过；`17_extended_checks.txt` 父产物 schema99/缺 ID、缺 from/to、非法 status/units 仍投影；节点启动丢弃冲突参数 |
| G04 | FAIL | 常规 locked 与新 ID reload、普通 occlusion 通过；同 ID 换 T 后 occluded source 错移 8m，见 F2 |
| G05 | FAIL | stale/monitor/release/新版本正常回归通过；同 ID 实际 T 改变仍 changed=false、旧快照/track 不失效；standalone caller 引用未解绑 |
| G06 | BLOCKED | 默认不开新分离路径、源点和接地/低卧旧行为保留；O01 pool 消融通过。无可信现场桥接身份，不启用分离；条件性 synthetic 分离路径未实现/未运行，不能称分离通过 |
| G07 | PASS | 本范围 semantic unknown、物理/trust flags 未升级，无背景在线学习/深度模型；legacy/无 derived/source-only 正常回归通过。损坏 reference 的例外归 G03 |
| G08 | PASS | 已有回归通过、四源码 SHA 匹配、冻结资产保持、外部差异单列。仅范围/回归/静态兼容子范围，不能抵消 G03–G05 FAIL 或替代设备运行 |
| O01 | PASS / BLOCKED | `18_o01_audit.txt` 独立重算全部六面完整 pool 支持数/比例/RMS 与两臂成员/AABB一致；来源/采样/ROI限制、unknown身份诚实。真实单帧根因/地面身份 BLOCKED |
| D01 | NOT_RUN / BLOCKED | 未连接板端、无完整真实逐帧/人工标签、目标环境未运行 |

## 入口/状态矩阵

| 行 | 结果 | 证据 |
|---|---|---|
| build_snapshot 无标定/legacy/source-only | PASS | `10` legacy；`13` GL03 legacy/source-only |
| full artifact + ground + reference | PASS（正常路径） | `13` reference/ground 精确几何；`11` artifact T |
| derived损坏/版本/parent/frame异常 | PASS（ground）；FAIL（reference parent） | `10` ground拒绝；`17` schema99/缺父ID reference泄漏 |
| 采样/非法点/范围/background/原索引 | PASS | `10` 索引与实际ground还原；`13` HF04/GL03 |
| decoder wrapper / node / replay | FAIL（node/reference共用入口） | lidar_candidates.candidates_from_cloud 透传 build_snapshot；node _process_locked 调 build_snapshot；pipeline/replay 调相同 helper，原无标定回放未新增热更新。`13` decoder/pipeline/replay回归。未声称真ROS运行 |
| 当前locked state/candidate一致 | PASS（正常路径） | `13` test_observed_state_ground_equals_candidate |
| reference优先/occluded预测 | FAIL | `10` 正常预测通过；`17` 同ID换T预测错误 |
| unselected/release/lost/ambiguous/stale/invalid/monitor_bad | PASS（未改变T的上下文） | `10` stale/monitor/release；`13` GL02/HF跟踪状态与 GL03 invalid/lost |
| 同/新版本reload/恢复 | FAIL | `11` 新ID与caller artifact深拷贝通过；`17` 同ID变化和standalone原地修改失败 |
| 无可信支持/disabled | PASS（保守关闭） | 源码未新增开启分离，`18` decision enabled=false |
| 可信synthetic桥接/standing/contact/lying/完全近地 | NOT_RUN（新分离） | 未启用新分离，无可信真实身份；`13` 原HF04低卧保留，不冒称新分离已验收 |
| 真实ROI/pool/无空场 | PASS（诊断）/BLOCKED（物理） | `18` 97411池/6000 ROI两帧、同mask统计/成员；报告无空场/真人机器人身份宣称 |

## 集中缺陷（均为已有要求，非新增里程碑）

### F1：共享 resolver 未做完整记录/父资格验证，节点入口绕过 conflict（G03）

来源：验收 G03 的 unknown/损坏/newer/parent/from-frame 不假成功；R3 工单“记录不合法”“known canonical T不能冲突”“复用严格transform/calibration入口”。

`calibration.py:279` 仅 `_load_transform` 检查 R/t 数值；缺 from/to 跳过名称校验，status='broken'/units='mm' 被当有效，带 schema_version=99 或缺 calibration_id 的完整父记录也能供应 reference。`17` 四种 standalone 异常及两种父异常仍返回非空 reference。预期明确拒绝或 reference unavailable；不能造坐标资格。保留合法 standalone 与旧最小摘要，不要求 legacy 摘要变成完整 artifact。

`node_runtime.py:452` 有 canonical 时把显式参数置 None，因此启动时传不同 T 被静默忽略；纯 build_snapshot 的 conflict 校验没有覆盖节点。区分**启动参数冲突**与**新版本 reload 合法采用新 artifact T**：后者本来应覆盖先前绑定，不应误拒绝新版本。

### F2：同 ID 改变参考内容未拒绝/失效（G04/G05）

来源：验收 G04 坐标不可错标、G05 同/新标定资格；R3 工单显式要求“同版本实际reference内容改变不得混旧资格，可明确拒绝要求新ID”。

`apply_ground_context:546` changed 只比较 calibration_id/GDID，随后无条件换 `_reference_transform`。先选择/锁定 T.translation_x=1 的目标，再以**相同 calibration_id**换 x=9：返回 changed=false，旧 snapshot/track 仍保留。下一帧空候选 occluded，旧reference track 通过新inverse得到 source x=-5.993978，而真实原source x=2.006022，差 **8m**。`17` 在有效时间/正常epoch夹具下复现；不是时钟问题。预期同ID内容不同拒绝且无副作用，或明确版本/资格失效；相同内容reload保持现有行为。覆盖 locked/pending/无新帧/status/request/occluded，避免只修一条预测。

### F3：standalone caller 引用仍是活变换（G05/G04）

来源：R3 “caller解绑”、G03 caller不被修改/不混版本及 G05资格绑定。

`self.transform=transform` 和 resolver 返回原 effective dict。无 known artifact 时，caller 修改 translation_x 1→9 后相同点的 reference x 3.006022→11.006022，无 reload/版本切换。artifact路径深拷贝已通过，但 standalone兄弟入口仍漏。应在合法绑定边界解绑；非法/unknown变换不变成新资格；预测与快照消费同份固定绑定。

## 命令与结果

`run_review.py` 原始 argv/exit 位于各日志头尾：Python3.12 本机，`-B -W error`。

- `10_geometry.txt`：R1原九方法 exit0。
- `11_reference.txt`：R2原四方法 exit0。
- `12_independent.txt`：首轮新增检查 exit1；保留旧日志。
- `13_fall.txt`：当前主线306回归 exit0（含 GL03 34 和 GL02 正常回归）。
- `14_follow.txt`：follow2 exit0。
- `python -B -W error .../codex_review_01/review_checks.py` → `17_extended_checks.txt` exit1；扩展后F1/F2/F3全部复现。
- `python -B -W error .../codex_review_01/o01_audit.py` → `18_o01_audit.txt` exit0；没有执行会覆写旧21 JSON的提交main。
- `python -B -W error .../codex_review_01/final_verify.py` → `20_final_verify.txt` exit0；保存修正前19错误。

不能以回归数量或 O01 通过替代必需软件条目；当前仅需集中修 F1/F2/F3。下一步用户手动派发 `docs/human_fall/AI_PROMPT_GL03_OPENCODE_R4.md`；没有自动启动OpenCode、切换模型或连接设备。
