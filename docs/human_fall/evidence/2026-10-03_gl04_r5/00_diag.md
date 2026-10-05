# GL-04 R5 集中返工诊断（00_diag，实现前）

判据：`GL04_ACCEPTANCE.md` v1（只更新结果列）。唯一生产写入 OpenCode `opencode-go/deepseek-v4.1-flash`，default DB 紧凑新会话；Codex 独立复审。范围仅四 preview：`webui/human_fall_preview/{index.html,human_fall.js,human_fall_lib.js,human_fall_lib.test.js}`。core/config/driver/正式页/其他 webui/旧断言/旧证据冻结；无 GL05/部署/采集/板端网络/commit/reset。

输入（各只读一次）：R5 `PLAN_REVIEW.md`、R4 `CODEX_REVIEW.md`、R4 `90_codex_runtime.txt` 5 FAIL 尾、R4 `92_codex_consumers.txt` 2 FAIL 尾、R3 `02_operation_matrix.md`、`human_fall.js`、`human_fall_lib.js`、`core/node_runtime.py:1152-1335`（state 输出字段与预测语义）。

## 0. R4 残留 7 FAIL 与共享根因

| 90/92 FAIL | 现行位置 | 根因 |
|---|---|---|
| 90 `known snapshot GDID with absent state GDID` | `human_fall_lib.js` `_bindingMismatch`:523 | 只在 `state.ground_derived_id !== undefined` 时比较；state 缺失字段被当“免比较”，known 快照 + undefined state 误判匹配 |
| 90 `known snapshot calibration schema with unknown state schema` | `_bindingMismatch`:517-519 + `observationQualified`:537-539 | state 声明`calibration`但 schema 为 null 时 `tcal.schema_version != null` 跳过；未做完整 nullable 比较 |
| 90/92 predicted old position becomes current source position | `human_fall.js` `hfTargetGeometryPresent`:549 + `hfRenderState`:457-465 | 预测短路 + position 行直接取 `position_source_m`，把预测位当“当前位置” |
| 90 old choice rejects in-place `coordinate.source_frame` change | `human_fall_lib.js` `snapshotIdentity`:487-490 | render token 只列 `source.frame_id`，未列 `coordinate.source_frame` |
| 90 old leveled choice rejects changed transform units | `groundTransformKey`:321-325 | token 变换键未含 `units` |
| 92 legacy source-only locked current target empty | `human_fall.js` `hfStateAligned`:593 | source 模式也复用 `observationQualified`（要求 cal.schema===1、ground valid、verifier），legacy 无标定 source-only 被误判“未对齐”，退化为位置 `--` |

共享根因：①nullable 绑定把“字段缺失”当“免比较”；②source 当前实际测量与 ground 物理观测资格未分门；③render token 漏已声明坐标子字段；④预测诊断复用“当前位置”渲染位。

## 1. C01–C15 逐行映射（函数 / 赋值顺序 / 各消费者 / 失效恢复 / 反例）

到达顺序总入口：`handleMessage`(human_fall.js:326) 截获 → `hfOnMessage`(238) / `hfOnRawFrame`(133)。raw 缓存 `hf.rawFrames`，输出帧 `hf.candidates`（按 `objectKeys` 键）。`hfAdvancePresent`(127)→`hfPresentFrame`(111)→`renderPoints`→`hfSyncCurrentSnapshot`(566)。state 经 `hfAcceptState`(287) 定序后 `hf.lastState`。

### C01 startup 无消息 / legacy 无 R/t / 合法 source-only
- 输入来源：`fetch`/`hfStartSynthetic`（无消息）或 board `POINTS`+`CAND`+`STATE`；legacy 消息 `calibration={calibration_id:null,schema_version:null,...}`、`coordinate.source_frame` 有值、无 `coordinate.ground`/`ground_render`。
- 函数与赋值顺序：`hfOnRawFrame`→`hfAdvancePresent`→`hfPresentFrame`→`hfSyncCurrentSnapshot`（`lastMeta=snapshotMeta`、`groundRender=parseGroundRender`）→`hfRenderState`(416)→`hfStateAligned`(587)。
- 消费者资格：
  - 选择：`hfSelectCandidate`(666)→`selectionContextQualified`(560)：只需 fresh 当前候选 + binding 一致（schema 明确非 1 才拒），**不要求**已有目标/有效 ground/verifier → legacy source-only 首选可发原 snapshot/candidate id。
  - 当前 source 测量：`hfStateAligned`(587)→ `hfTargetGeometryPresent`(524) source 分支唯一候选匹配 → `hfRenderState`:462 取 `position_source_m`。
  - GT 跌倒观测：`hfRenderState`:453 `fall_status` + `FALL_CLASS`；`hfFrame`:1028 目标框颜色。
  - 预测诊断：`hfRenderState`:478-481 `hfPred`。
- 失效/恢复：`hfResetContext`(213) 清缓存、`groundRender=parseGroundRender(null)`、ground 模式回退 source；`hfInvalidatePresentation`(391) 一次 `dirty3d` 重绘 GPU。
- 反例：90 `legacy no calibration no ground raw first selection preserved`（已过，保留）；R5 新增 92 `legacy source-only locked ...`（修复后必须 PASS）。

### C05 新 GDID / same-ID 不同 R/t/coordinate / state-cand 交错
- 输入来源：两模式；`snapshot.coordinate.ground_derived_id`、`calibration.ground_derived_id`、`snapshot.calibration.{calibration_id,schema_version}`；state 根 `ground_derived_id`、`state.calibration.*`。
- 函数与赋值顺序：`hfOnMessage`(238) 校验 `validSnapshot`/`validState` → 存/覆盖 `hf.candidates` → `hfSyncCurrentSnapshot` → `hfRenderState`；选择 `hfRenderCandidates`(604) 先存 token=`{identity:snapshotIdentity(snap),signature:candidateSignature(c)}`，`hfSelectCandidate`:675-680 再核。
- 消费者资格：**绑定**`_bindingMismatch`(503) 统一服务 `observationQualified`(ground)、`selectionContextQualified`(选择)、`sourceAlignmentQualified`(R5 新增源测量)；**token**`snapshotIdentity`(476) + `candidateSignature`(462) 服务选择防旧。
- 失效/恢复：旧 token 失配即拒；绑定一致（both null / 双方 known 且相等）恢复当前实际目标读数。
- 反例：90 `one-sided missing GDID cannot match known state binding`（保留）；R5 反例 90 两条 `known snapshot ... absent state ...`（修复为 full nullable）；`same-ID changed R/t rejected` 已过保留。

### C07 本目标完整→缺详情/空→只有 other→恢复；ready 基线保留
- 输入来源：`snapshot.candidates[]` 各 `center_source_m/bbox_source_*`、`center_ground_m/bbox_ground_*`；`state.position_source_m/bbox_source_*`、`state.center_ground_m/bbox_ground_*`。
- 函数与赋值顺序：`hfCurrentCandidateEntry`(486)→`hfCurrentCandidateSnapshot`(503)→`hfTargetGeometryPresent`(524) 按 `hf.coordMode` 选分支，`hfTripleEq`(519) 逐字段比，命中数必须 `===1`。
- 消费者资格：当前 source 测量 / GT 观测共用该唯一匹配门；无命中（0）或多命中（>1）→ `hfStateAligned` false → `hfRenderState`:435 未对齐分支 `position '--'`、`fall unknown`；基线 `hfBaseline`(432) 独立显示，不背书。
- 失效/恢复：候选从 `hf.candidates` 过期（`hfFresh` 2000ms）或内容变化 → `hfCurrentCandidateSnapshot` null → unknown；本目标新绑定唯一命中即恢复。禁止 first/nearest/重跟踪/浏览器算几何。
- 反例：90 `source target absent while unrelated candidate survives`、`ground target stale fields cannot replace missing current target`、`duplicate geometry has no unique current target`（保留）。

### C08 locked 实测→prediction/occluded/ambiguous/lost/unselected；有/无 other
- 输入来源：`state.track_status`、`state.position_predicted`、`state.prediction_age_s`、`state.fall_status`、`state.center_ground_m*`；`node_runtime._state_payload:1195-1241`（predicted 时 ground 全 null、`position_source_from='predicted'`）、`:1325-1334`（lost/ambiguous 清 ground）。
- 函数与赋值顺序：`hfRenderState`:421 读 state → `hfStateAligned` → aligned 分支 `hfFall/hfObs/hfPos/hfPred`；`hfFrame`:1022-1032 目标框（`pred ? 0x6b7a90 : hfFallColor`）。
- 消费者资格：
  - 预测诊断：`hfPred` 独立行（`预测 age=…s`，灰色 `hf-susp`）。
  - 当前测量/当前位置行：**`position_predicted` 为真时不得写“当前位置”**；R5 在 `hfRenderState` 计算 `pos` 后 `if (s.position_predicted) pos=null`。
  - GT 跌倒观测：`fall_status` 原义 + 告警色。
  - 事件/锁：`hf.events`/`hfAddEvent`(351)、`track_status` 文本不动。
- 失效/恢复：`hfInvalidatePresentation` 仅在一次资格跃迁调用，灰框/预测色保留；恢复走当前绑定。
- 反例：90/92 `prediction ... with only other candidate`（修复后 position `--`）；`one matching target plus unrelated candidate remains observed` 保留。

### C11 caller 原地改 candidate/RT/源frame/metadata；render token 后变化
- 输入来源：同一 snapshot 对象被调用方原地修改 `candidate`/`coordinate.ground.R|t|units`/`coordinate.source_frame`。
- 函数与赋值顺序：`hfRenderCandidates`:637 捕获 `snapshotIdentity`（含 session/epoch/snapshot/source key/frame_id/schema/cal/ground_status/GDID/transform_status + `groundTransformKey`）；`hfSelectCandidate`:672-680 重算并比对；`hfFinishDrag`(1066) 走同一 `hfSelectCandidate`。
- 消费者资格：旧按钮/旧 drag 提交都再核不可变 token；拒绝后不发请求；当前按钮仍发 `entry.snap` 原 `candidate_id`（`hfSendSelect`:192 用原 snapshot_id/candidate_id）。
- 失效/恢复：token 任一已声明字段变化 → 拒；同内容重载 identity 不变仍可选。
- 反例：90 `caller mutation after rendered button rejected`、`same IDs changed R/t rejected`（保留）；R5 新增 `in-place coordinate source-frame change` 与 `changed transform units`（修复 token 覆盖）。

### 其余 C 行（引用 R3/R4 已过入口，R5 核保留）
| 行 | 入口函数 | R5 处置 |
|---|---|---|
| C02 | `hfAdvancePresent`/`hfSyncCurrentSnapshot`/`hfRenderState`+`hfRenderCandidates` | 不改；R4 已过 |
| C03 | `snapshotIdentity`/`candidateSignature`/`sameSnapshot` | 只增量字段，不破坏同内容 |
| C04 | `_bindingMismatch` | 仅修正“缺失/已知”判定，混配阶段仍 unknown/拒旧 |
| C06 | `_parseGroundBlock`:343/`observationQualified`:537 | 显式 schema2 仍拒；不改 |
| C09 | `hfResetContext`/`hfInvalidatePresentation`/`dirty3d` | 不改；GPU 一次失效已过 |
| C10 | `parseGroundRender`/`observationQualified` | 不改；ground 状态门保留 |
| C12 | `hfUpdateMvp`/`hfBoxRect`/`hfResizeOverlay` | 不改；真实 DPR NOT_RUN |
| C13 | `validSupportPoints`/`supportBudget` | 不改 |
| C14 | `_parseGroundBlock` units 门 | 不改；仅 render token 增列 units（防旧选择） |
| C15 | `hfUpdatePerfPanel` | 不改 |

## 2. R5 最小共享改动（不建新跟踪/拟合/几何）

1. **`human_fall_lib.js` `_bindingMismatch`**：新增 `_normBind(v)=v==null?null:v`。当 `state.calibration != null || state.ground_derived_id !== undefined`（真实完整 state 恒真）时，对 `calibration_id`、`schema_version`、`ground_derived_id` 做完整 nullable 比较（both null/缺失匹配；任一侧 known 对侧 null/undefined 拒绝）。state 完全缺 `calibration`/`ground_derived_id` 的合法 partial 输入沿用旧容忍（保留原 44 断言中 `obsState` 之外的部分 state 纯函数用例）。
2. **`human_fall_lib.js` 新增 `sourceAlignmentQualified(snapshot,state)`**：显式 schema≠1 拒、`_bindingMismatch` 拒、`sensor_quality` verifier 明确 false / ground_monitor≠ok 拒；**不要求** ground_status valid。供 source 模式当前测量门；ground 模式仍用 `observationQualified`（不把首选 context 与已选目标观测混成一门）。
3. **`human_fall.js` `hfStateAligned`**：按 `hf.coordMode` 二选一调用 `observationQualified`(ground) / `sourceAlignmentQualified`(source)。
4. **`human_fall.js` `hfRenderState`**：`if (s.position_predicted) pos=null`；未对齐分支的 `hfPred` 在 predicted 时显示预测诊断（灰 `hf-susp`），保留预测语义。
5. **`human_fall_lib.js` token**：`snapshotIdentity` 增列 `coord.source_frame`；`groundTransformKey` 增列 `block.units`。`_parseGroundBlock` 增 `coordinate.source_frame` 与 `source.frame_id` 矛盾即 `invalid`。
6. 旧 44 lib 断言文字/语义保留，仅在 `human_fall_lib.test.js` 末尾 `console.log` 前追加 R5 test()；R4 后的 44 断言不降级。

## 3. 兼容与冻结
- 只静态比较已声明绑定字段，无新几何/模型/跟踪；生产 `build_snapshot` 无 R/t/support 端到端仍 V10 BLOCKED，D01 NOT_RUN，不改 core。
- r5 自验脚本仅复制 R4 Codex harness 到新名，stdout/JSON 落 r5 新名，不冒称独立复审；不覆写 r1–r4 证据。
- 正式页外部 Q/E/帮助变化不覆盖。
