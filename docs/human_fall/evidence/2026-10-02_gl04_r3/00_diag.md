# GL-04 R3 集中返工诊断（00_diag）

判据：`GL04_ACCEPTANCE.md` v1（结果列只更新）。唯一生产写入者 OpenCode `opencode-go/deepseek-v4.1-flash`，default DB，同 model/default DB 紧凑新会话；R2 exit0 已停止写入，不续塞长历史。范围仅四 preview：`webui/human_fall_preview/{index.html,human_fall.js,human_fall_lib.js,human_fall_lib.test.js}`；正式页（外部 Q/E/帮助）保留不写不回滚。core/config/driver/其他 webui/原数据/旧证据/原断言冻结；无 GL05/部署/采集/板端网络/commit/reset。生产 R/t/support 缺口 V10 继续 BLOCKED，D01 NOT_RUN。

输入（各只读一次）：R3 `PLAN_REVIEW.md`、`02_operation_matrix.md`、R2 `CODEX_REVIEW.md`、R2 `20_codex_runtime.txt` 失败尾段与 `20_codex_results.json`、`GL04_ACCEPTANCE.md` v1、`codex_full_review.js`（失败断言体）、`human_fall.js`、`human_fall_lib.js`、`human_fall_lib.test.js`、`human_fall_node.py:31-52/273-291/387`（真实 performance 字段）。

## 0. 三个共享根因（R2 CODEX_REVIEW 22–47 行）

1. **当前绑定/对应目标资格未统一**：`observationQualified` 只查 snapshot 自身 ground/非空 list/verifier，从不与 state 的 session/epoch/source/snapshot_id/calibration(schema/id/GDID) 对齐；ground 版本混配与双方同值坏 schema 仍 upright。ground 模式还用 `hfAnyGroundCandidate` 任取第一个有 `center_ground_m` 的候选代当前目标。
2. **失效未真正重绘**：quiet>TTL 后 DOM 转 unknown，但 `hfSupportGroup`、cached 框与 `dirty3d` 未动，ground 旧变换仍 ready；无一次性 GPU 失效。
3. **字段/维度/单位旁路**：`_parseGroundBlock` 不校验 `units`（mm 当 m）；`validSupportPoints` 只要 x/y 有限即通过，显式 3D 的 null/NaN Z 被 `hfMakeSupportLine` 置 0 冒充；`hfUpdatePerfPanel` 不读真实 `state.performance.queue_dropped`。

## 1. C01–C15 逐行映射（实际函数 / 到达顺序 / 资格 / UI-GPU 失效 / 检查）

| 行 | 到达顺序/输入 | 实际函数与更新先后 | 共享资格结果 | DOM/overlay/GPU 失效 | 检查 |
|---|---|---|---|---|---|
| C01 | startup 无消息；legacy source-only 无 R/t | `hfStartSynthetic`/`fetch`→`hfOnRawFrame`→`hfAdvancePresent`→`hfPresentFrame`→`hfSyncCurrentSnapshot`；`hfSetMode` | `parseGroundRender` 无块=`unavailable`，不造 identity；`observationQualified` 不变 | 无 ground：`hfRenderPanel` 禁用 ground 按钮、`hfLevelTag` 说明；source 点云/原选择/ack 不动 | lib：missing R/t 非 ready（保留）；R3 新增 units 缺失/错拒 |
| C02 | raw→CAND→STATE / raw→STATE→CAND / →raw | 新帧 `hfOnRawFrame`；CAND `hfOnMessage`→`hfSyncCurrentSnapshot`+**新增 `hfRenderState()`**+`hfRenderCandidates`；STATE→`hfRenderState`+`hfAdvancePresent` | 首轮消息到齐即用同一 `hfCurrentCandidateEntry` 出读数/RT/框，不等下一帧 | 任一侧未到齐：`hfStateAligned`=false→unknown/位置空 | 21 项保留；新增顺序断言 |
| C03 | 同内容同 ID reload；state/cand 任一先到 | `hfSyncCurrentSnapshot`；`snapshotIdentity`/`candidateSignature` | `sameContext`+绑定一致⇒保留资格与正常色；同内容 token 继续 | 不刷新即不重置；无失效 | lib `snapshotIdentity`/`sameSnapshot`（保留） |
| C04 | CAND cal2→STATE cal1→STATE cal2；反序 | `observationQualified` **新增** session/epoch/source/snapshot_id/calibration_id/schema/GDID 对齐 | 混配⇒`reason` 非 ok⇒unknown/position null/拒旧选择；两侧新绑定到齐才恢复 | `hfRefreshObservation` 资格转换失效 | 20 FAIL 3 项修复；新增 cal 反序 |
| C05 | 新 GDID、same-ID 异 R/t；state/cand 交错 | `snapshotIdentity`（含 `groundTransformKey`）、`candidateSignature` | GDID/坐标内容变化⇒旧 token 失效；不借旧 state/RT | `hfSelectCandidate` 复核 fresh entry | 21 项 V05 保留 |
| C06 | schema=2 各自/双方；snapshot schema2/坏 frame/epoch 不匹 | `_parseGroundBlock`（schema/units/cal/GDID/ground_status）；`observationQualified`（scal.schema_version===1） | 错值相等不支持；unknown/不可选；不跨源 | `hfStateAligned`=false→unknown；`hfRefreshObservation` 清 GPU | FAIL 3 项修复（schema2、snapshot cal2/state cal1、反向） |
| C07 | 本目标完整→缺详情/空→只有 other→恢复；ready 基线 | `hfRenderState`（**删 `hfAnyGroundCandidate`**）、`hfTargetGeometryPresent`、`hfStateAligned` | 只消费 state 自身当前模式几何；不 first/nearest/跟踪；无本目标详情⇒fall unknown/position null；ready 不代替观测 | 本目标框隐藏；`hfInvalidatePresentation` 清支持层 | FAIL V07 修复；新增 target 缺失断言 |
| C08 | locked 实测→prediction/occluded/… | `hfRenderState`（`position_predicted` 保留）、`hfFrame` target 框 | prediction 仍只作预测色；不伪当前 actual_points；history/baseline 不清 | prediction 框灰；无观测不补 ground 位置 | lib/21 项保留 |
| C09 | ws 断连/重连；socket open 但 quiet>TTL | `hfConnectionState`/`hfResetContext`+**`dirty3d`**；`hfRefreshObservation`→`hfInvalidatePresentation` | stale⇒`hfCurrentCandidateSnapshot`=null⇒未齐 | DOM+overlay+GPU（框/支持/变换）一次 dirty；raw 留、帧龄诚实、events 留 | FAIL quiet GPU 修复；disconnect dirty 加强 |
| C10 | ground valid→unknown→none→valid；verifier ok→unavailable→ok | `parseGroundRender`（ground_status）、`observationQualified`（verifier/monitor） | 不以 ready 基线/上次状态恢复；恢复同当前 binding | 失效转换清 ground 色/框；恢复后一次同步 | 21 项 verifier/ground 保留 |
| C11 | caller 原地改 candidate/RT/frame/metadata | `hfRenderCandidates` token、`hfSelectCandidate`、`hfFinishDrag` | 提交时对 fresh entry 核不可变 token；发原 candidate_id | 拒绝旧选择不改显示 | 21 项 V05 保留 |
| C12 | camera rotate/zoom/resize/DPR-only | `hfUpdateMvp`/`hfBoxRect`/`hfResizeOverlay`/`hfFrame` | 当前视锥/矩阵；两画布同步 | 每帧重投；无缓存框 | 21 V04 保留；真实 DPR 仍 NOT_RUN |
| C13 | supports 0/3/3000/3001/9000；2D 合法/3D 有限/3D null 非法 | `parseSupport`+**`validSupportPoints`（3D 三分量有限）**、`supportBudget`、`hfMakeSupportLine` | 未知 3D 分量⇒invalid 不置 0；预算/索引/LineLoop 保留 | 支持层独立≤3000；grid≠地面 | FAIL null Z 修复；预算保留 |
| C14 | source/transform units 缺/mm/其它；已知 m | `_parseGroundBlock` **新增 `block.units==="m"` 门**；`snapshotMeta.units` | 非米/未知⇒不 ready，不显示 m 掩盖；合法 source 原义保留 | ground 入口禁用/回退 source | FAIL mm 修复；新增缺失拒 |
| C15 | state.performance kind/schema/enabled/queue_dropped；disabled/未知 | `hfUpdatePerfPanel` **真实 `state.performance` 优先**；`renderer.render` 计数保留；`pcSkip`/Hz 原义 | 缺/disabled/非法⇒unknown，不造 0；真实字段不被兼容字段覆盖 | 三场景同屏同帧由 Codex 实跑 | FAIL performance 修复；render-fps 保留 |

## 2. 固定 8 FAIL → 函数/守门/检查

| 20_codex_runtime FAIL | 现行函数 | R3 守门 | ID |
|---|---|---|---|
| snapshot cal2 而 state cal1 仍 upright | `observationQualified` | 加 `calibration_id` 对齐 | V06/C04 |
| state cal2 而 snapshot cal1 仍 upright | 同上 | 同上 | V06/C04 |
| 双方 schema2 相等仍 upright | `observationQualified` | snapshot/state `calibration.schema_version===1`（坏 schema 同值不支持） | V06/C06 |
| 本目标缺 ground 详情、other 仍在⇒upright/位置 12 | `hfRenderState`+`hfAnyGroundCandidate` | 删任取候选；`hfTargetGeometryPresent` 按模式要求 state 自身几何 | V07/C07 |
| `state.performance.queue_dropped` 未显示 | `hfUpdatePerfPanel` | 真实 `state.performance{kind,schema_version,enabled}` 优先，缺/禁用 unknown | V08/C15 |
| 显式 3D support null Z 仍 ready | `validSupportPoints` | length≥3 时第 3 分量必须有限 | V02/C13 |
| 显式非米 ground transform 仍 ready | `_parseGroundBlock` | `units==="m"` 才 ready | V03/C14 |
| quiet>TTL cached GPU 仍有效、dirty3d false | `hfRenderState`/`hfFrame`/`hfResetContext` | 资格 true→false 转换 `hfInvalidatePresentation`，清框/支持/变换并 dirty3d | V06/C09 |

## 3. 兼容与冻结

- 原 18 + GL-04 R1/R2 断言文本一字不改，仅在 `human_fall_lib.test.js` 末尾 `console.log` 前追加 R3 test()；辅助 harness/fixtures/结果只写 r3，命名不与 Codex 的 `20_codex_*` 冲突，不覆写 r2。
- 旧兼容字段：`snapshot.ground_render` 仍作别名，但 `units`/`schema`/`GDID`/ground_status 门同等适用；`hfUpdatePerfPanel` 兼容字段只在无真实 `state.performance` 时使用，绝不被用来覆盖真实字段。
- `syntheticScenario` 仍仅 CommonJS 分支导出；浏览器只 `fetch` r3 静态 fixture。source 模式始终可用，ground 模式无有效显式变换即禁用。
