# GL-04 R6 集中返工诊断（00_diag，实现前）

判据：`GL04_ACCEPTANCE.md` v1（只更新结果列，不改语义/条目）。唯一生产写入 OpenCode `opencode-go/deepseek-v4.1-flash`，default DB 紧凑新会话；Codex 独立复审。范围仅四 preview：`webui/human_fall_preview/{index.html,human_fall.js,human_fall_lib.js,human_fall_lib.test.js}`，另加本轮新 r6 证据、`returns/GL-04.md` 末尾追加。core/config/driver/正式页/其它 webui/原数据/旧证据冻结；无 GL05/部署/采集/板端网络/commit/push/reset/checkout/clean。

ponytail SKILL.md 实际读取路径：`C:\Users\30680\.config\opencode\skills\ponytail\SKILL.md`（skill 工具加载，full）。梯子：先复用已有 `_bindingMismatch`/`observationQualified`/`sourceAlignmentQualified`/`snapshotIdentity`/`groundTransformKey`/`candidateSignature`/`parseSupport`，只加最小共享门，不新增依赖/框架/哈希框架。

输入（各只读一次）：根 `AGENTS.md`/`CLAUDE.md`、`WORKFLOW.md` v2、`GL04_ACCEPTANCE.md` v1、`evidence/2026-10-03_gl04_r6/PLAN_REVIEW.md`（C01–C15 完整矩阵）、`evidence/2026-10-03_gl04_r5/00_diag.md`、r5 `CODEX_REVIEW.md`、r5 `95_codex_source_fall_gate.js`/`97_codex_additional.js` 与其 results、r5 `codex_full_review.js`/`codex_runtime_harness.js`，源码 `webui/human_fall_preview/human_fall_lib.js`/`human_fall.js`、`src/human_fall_detection/core/node_runtime.py:1152-1335,1363-1386`。

## 0. R5 复审残留 FAIL 与共享根因

| R5 FAIL（95/97） | 现行位置 | 根因 |
|---|---|---|
| source ground unknown/none 仍 `upright`/绿框（physical fall 被 raw XYZ 资格背书） | `human_fall.js` `hfRenderState`:455-456,478-486；`hfFrame`:1037-1041 | source 模式 `hfStateAligned` 只用 `sourceAlignmentQualified`（不要求有效 ground），physical fall/颜色与 raw 测量未分门 |
| predicted/lost/ambiguous/unselected 仍 physical upright/旧 source 当前位 | `hfTargetGeometryPresent`:554,555-566 | source 分支只比几何，未要求“当前实际观测”（locked 且非 prediction） |
| token 漏 `snapshot.units.length`、`candidate.center_ground_m`、ground block `kind`/`schema_version` | `snapshotIdentity`:495-499；`candidateSignature`:469-477；`groundTransformKey`:323-325 | token 未列已声明坐标/版本子字段 |
| 显式 `snapshot.units.length="mm"` 仍当 m 显示/ready | `_parseGroundBlock`:333-346；`sourceAlignmentQualified`:604-625 | 未校验顶层 units；source 测量未受单位门 |
| 显式 `ground.support_units="mm"` 仍 support.ready | `parseSupport`:436-452 | 未校验 support.units |
| R5 fixture `state.calibration` 缺 `schema_version`，no_extrinsics 误标 `position_source_from=unavailable` | `make_fixtures_r5.js`:40-47 | 生成器未完整复制 `node_runtime` 已发布绑定/current actual 字段 |

共享根因：①raw 测量资格与 physical 观测资格混用（source 模式）；②“当前实际观测”缺 locked/非预测门；③token 漏已声明坐标/版本子字段；④显式单位未在 source/support 入口校验；⑤fixture 未复制真实发布字段。四处均为同一资格族，一次在共享门（lib binding/units/token + 消费门）修复，不做孤立 if。

## 1. 到达顺序总入口（不变）

`handleMessage`(human_fall.js:326) 截获 → `hfOnMessage`(238)/`hfOnRawFrame`(133)。raw 缓存 `hf.rawFrames`；输出帧 `hf.candidates`（`objectKeys` 键）。`hfAdvancePresent`(127)→`hfPresentFrame`(111)→`renderPoints`→`hfSyncCurrentSnapshot`(571)。state 经 `hfAcceptState`(287) 定序后 `hf.lastState`。

## 2. C01–C15 逐行映射（函数 / 赋值顺序 / 各消费者 / 守门 / 保留 / 失效恢复）

### C01 startup / legacy source-only / locked，cal+GDID 全 null
- 输入：`hfStartSynthetic`(889) 静态 fixture，或 board `POINTS`+`CAND`+`STATE`；legacy `calibration={id:null,schema:null}`、`coordinate.source_frame` 有值、无 ground。
- 顺序：`hfOnRawFrame`→`hfAdvancePresent`→`hfPresentFrame`→`hfSyncCurrentSnapshot`（`lastMeta=snapshotMeta`、`groundRender=parseGroundRender`）→`hfRenderState`(416)。
- 消费者资格：选择 `hfSelectCandidate`(676)→`selectionContextQualified`(585)（不要求已有 target/ground）；source 当前测量 `hfStateAligned`(592)→`sourceAlignmentQualified`(604)→`hfTargetGeometryPresent`(529) source 唯一匹配→`hfRenderState` 取 `position_source_m`；physical fall/颜色 = `observationQualified`(556) 另门；预测 `hfPred` 独立行。
- **R6 守门**：source 测量保留（`sourceAlignmentQualified` + 当前实际 locked），physical fall/目标颜色在 `observationQualified` 不成立时 `unknown`；ground 入口禁用。
- 失效/恢复：`hfResetContext`(213)/`hfInvalidatePresentation`(391) 清缓存/变换并 `dirty3d`；历史事件不清。
- 反例：90 `legacy no calibration no ground raw first selection`（保留）；92 `legacy source-only locked ...`（raw XYZ/track 保留）；97 legacy（physical unknown）。

### C02 raw/state/candidate 任一先到 × source/ground
- 入口 `hfAdvancePresent`/`hfSyncCurrentSnapshot`/`hfRenderState`+`hfRenderCandidates`。R3/R4 已过，不改；R6 门仅加取值，不破坏到达顺序。

### C03 同内容 reload × locked/ready/prediction
- `snapshotIdentity`(481)/`candidateSignature`(467)/`sameSnapshot`(501)。R6 只“增量”已声明子字段（units.length / ground kind/schema / center_ground_m），同内容 identity 不变仍可选；相机变化不入 token（保留 90 `fresh list choice / same-content reload`、`camera rotate/zoom` 正例）。

### C04 同 ID 异 cal / 新 cal ID / 双侧交错
- `_bindingMismatch`(513) 完整 nullable；R6 不改该函数，只在其上游加单位/当前实际门。混配仍 unknown/拒旧，双侧到齐恢复（90 保留）。

### C05 新 GDID / same-ID 不同 R/t / state-cand 交错
- 选择 token `hfRenderCandidates`:647 捕获 `snapshotIdentity`+`candidateSignature`；`hfSelectCandidate`:685-689 再核。
- **R6 守门**：`snapshotIdentity` 增列 `s.units.length`；`groundTransformKey` 增列 `block.kind`/`block.schema_version`；`candidateSignature` 增列 `center_ground_m`。旧按钮/拖选同门拒绝。
- 反例：90 `same IDs changed R/t`、`one-sided missing GDID`（保留）；97 四条 in-place mutation（修复为 token 覆盖）。

### C06 schema2 / frame / epoch 错误 × source/ground
- `_parseGroundBlock`:332/347-357、`observationQualified`:562-566、`sourceAlignmentQualified`:610-615。显式 schema2/frame/epoch 仍全拒，无伪绿色/旧选择；R6 不改这些值，只加 `_sourceUnitsUnsupported` 同族显式错误。（90 保留）

### C07 当前目标→空/other/重复→唯一恢复 × ready 基线
- `hfCurrentCandidateEntry`:491→`hfCurrentCandidateSnapshot`:508→`hfTargetGeometryPresent`:529 唯一匹配。无命中/多命中→`hfStateAligned` false→`hfRenderState` 未对齐分支位置 `--`/fall unknown；基线 `hfBaseline`:432 独立显示不背书。R6 增加“当前实际”门：非 locked / 预测 / lost/ambiguous/unselected 不匹配。（90 保留）

### C08 locked 实际→predicted/occluded/ambiguous/lost × ground 有效/无
- `hfRenderState`:421 读 state→`hfStateAligned`；aligned 分支 `hfFall/hfObs/hfPos/hfPred`；`hfFrame`:1032-1041 目标框。
- **R6 守门**：新增 `hfPhysicalObserved()` = `observationQualified(snap,s).ok && hfCurrentActual(s)`（locked 且非 prediction）。aligned 但 physical 不成立：`hfFall=unknown`、`hfFallHex` 用 unknown 灰；pred 仍灰 `6b7a90`、`hfPred` 预测诊断原义。
- 保留：事件/锁 `track_status` 文本、预测框灰、`hfPred` 独立行；`s.position_predicted` 时 `pos=null`（R5）。
- 反例：97 predicted/lost/ambiguous/unselected（修复）；90 `prediction ... only other`（位置空保留）。

### C09 silent expiry/disconnect→reconnect
- `hfResetContext`(213)/`hfInvalidatePresentation`(391)/`window.hfConnectionState`。R6 不改；GPU/支持/变换一次 `dirty3d` 失效，历史/ack 保留，只当前数据恢复（90/92/browser 保留）。

### C10 ground valid→unknown→none→valid / verifier
- `observationQualified`(556) 为 physical 门；`sourceAlignmentQualified`(604) 为 raw 门。R6 把两者在消费者处分离：source raw XYZ 可留，physical fall/颜色在 ground 不足时 unknown；valid 恢复 upright 原色。（95/97 + 真实 browser 修复）

### C11 caller 改 candidate/R/t/source_frame/units × list/drag
- `hfRenderCandidates`:647 捕获不可变 token；`hfSelectCandidate`:685 重算比对；`hfFinishDrag`:1095 走同一 guard。R6 token 覆盖面见 C05；仅相机变化不改绑定。
- 反例：90 source_frame/transform units（保留）；97 四条新子字段（修复）。

### C12 rotate/zoom/resize/DPR、near/far/behind、退化
- `hfUpdateMvp`/`hfBoxRect`/`hfResizeOverlay`。不改；真实 DPR/完整退化 NOT_RUN（交 Codex），不冒实测。

### C13 0/3/3000/3001/9000 支持 × 两 mode
- `validSupportPoints`(424)/`supportBudget`(410)/`parseSupport`(436)。R6 只加 `support.units` 显式非米拒；预算/原索引/LineLoop/图例/2D 平面保留（90 保留）。

### C14 显式 units missing/mm/other × 同 ID 旧 token
- `_parseGroundBlock`（block.units m 门，R3 已有）；**R6 新增** `_sourceUnitsUnsupported(snapshot)`：顶层 `units.length` 显式非 `"m"` → ground invalid / source 对齐 false；`parseSupport` 显式 `support.units !== "m"` → invalid。缺字段合法 legacy 兼容保留，显式错拒。
- 反例：97 三条 units（修复）；旧 `parseGroundRender refuses unknown/non-metre transform units`（保留）。

### C15 Node 形状 performance/全部 fixture 绑定 × 三场景
- `hfUpdatePerfPanel`(779) 真实 `state.performance` 优先（R3 保留）。**R6 新 fixture** 完整复制 `node_runtime` 已发布绑定（`snapshot_id`/`coordinate`/`ground`/`calibration.schema_version`/`sensor_quality`/`center_ground_m`/`ground_derived_id`），no_extrinsics 的 source 实际位置 `position_source_from=actual_points`；physical flags 全 false；资格正/负例断言在 r6 新脚本。

## 3. R6 最小共享改动清单（映射到函数，不建新跟踪/几何/哈希框架）

1. `human_fall_lib.js` 新增 `_sourceUnitsUnsupported(snapshot)`：`snapshot.units.length != null && !== "m"` → true。
2. `_parseGroundBlock`：在 block 结构检查后加 `if (_sourceUnitsUnsupported(snapshot)) return _badGround("invalid","source_units")`。
3. `observationQualified` / `sourceAlignmentQualified`：加 `if (_sourceUnitsUnsupported(snapshot)) return {ok:false,reason:"source_units"}`（选择 context 不加以免破坏纯源选择）。
4. `parseSupport`：`support.units != null && support.units !== "m"` → `{status:"invalid",reason:"support_units"}`。
5. `groundTransformKey`：追加 `block.kind`、`block.schema_version`。
6. `snapshotIdentity`：追加 `s.units && s.units.length != null ? s.units.length : ""`。
7. `candidateSignature`：追加 `(c.center_ground_m || []).join(",")`（无条件，声明即纳入）。
8. `human_fall.js` 新增 `hfCurrentActual(s)=!!(s&&s.track_id&&s.track_status==="locked"&&!s.position_predicted)` 与 `hfPhysicalObserved()=hfCurrentActual(s)&&HF.observationQualified(snap,s).ok`。
9. `hfTargetGeometryPresent` source 实际分支：在 prediction 短路后，`if (!hfCurrentActual(s)) return false;`（ground 分支保持由 ground 几何决定）。
10. `hfRenderState`：aligned 分支 `var physical=hfPhysicalObserved(); var fs=physical?(s.fall_status||"unknown"):"unknown"; hfSetText("hfFall",fs,FALL_CLASS[fs]||"hf-unk");`；`hfFrame`：`pred?0x6b7a90:(physical?hfFallColor(s.fall_status):hfFallColor("unknown"))`，target label fall 文本同门。
11. `human_fall.js` 默认 synthetic fixture 指向本轮 `2026-10-03_gl04_r6/fixtures`（浏览器只 fetch 字段，不建几何）。
12. 旧 44 lib 断言文字/语义保留，仅在末尾追加 R6 test()（单位门、token 子字段、physical/currentActual）；不改旧断言文本。

## 3b. R6 补充诊断（C08/C14/C15 追加组合，压缩前遗漏）

- **C08-a 合法 occluded 预测 + 空候选（source）**：`s.position_predicted=true` 时预测框是独立诊断，不要求 `snapshot.candidates` 非空背书。消费者路径 `hfStateAligned`(592) 经 `sourceAlignmentQualified`(614) 在空候选返回 `no_candidate` → aligned=false；因此新增独立 `HF.predictionDiagnosticQualified(snap,s)`（要求 fresh + session/epoch/snapshot/binding + schema + 顶层 source units；**不要求候选非空、不要求 ground valid**），`hfFrame` 在 `!stateMatches` 时用 `HF.candidateBox(s,mode)` 画灰 `0x6b7a90` 预测框并在 `hfRenderState` 未对齐分支显示 `预测 age`（440-442 已有）。current position/fall 保持 unknown/`--`（physical 门要求非预测）。
- **C08-b 显式负向实际观测标志不背书 physical**：`s.bbox_observed===false` 或 `s.position_source_from` 显式非 `"actual_points"`（如 `unavailable`/`predicted`）时，physical fall/目标色必须 unknown；缺字段（legacy）继续容忍。实现 `HF.actualObservationQualified(c)`，并入 `hfPhysicalObserved()`；raw source 位置显示不改（仅 physical 背书）。
- **C08-c lost/ambiguous/unselected 两 mode 拒旧 current 几何**：即使 `center_ground_m`/`bbox_ground_*` 仍与某候选逐位匹配，`hfCurrentActual`(locked 且非 prediction) 为假即 `hfTargetGeometryPresent` 两分支均 false → 不显示保留的旧中心/框；预测短路仍在（独立诊断）。
- **C14-a 显式 source units 错误须同查当前列表/拖选消费者**：`_sourceUnitsUnsupported` 门同时加入 `observationQualified`、`sourceAlignmentQualified` 与 `selectionContextQualified`（列表点选 `hfSelectCandidate` 与拖选 `hfFinishDrag` 共用）；缺字段合法 legacy 不受影响。
- **C15-a fixture 源平面 offset 契约**：`snapshot.ground` 的 `normal=R[2]` 时 `offset_m` 必须等于 `t[2]`（源平面方程 n·p=offset）；R5 复制器写负号违反冻结几何契约，r6 生成器改为 `t[2]`，负例断言校验。

## 4. 兼容与冻结

- 只静态比较已声明字段，无新几何/模型/跟踪；生产 `build_snapshot` 无显式 R/t/support 端到端仍 V10 BLOCKED，D01 NOT_RUN，不改 core/config/driver/正式页。
- r6 自验脚本/结果/fixtures 只写 r6 新目录，不覆写 r1–r5；正式页外部 Q/E/帮助变化不覆盖。
