# GL-04 R4 集中返工诊断（00_diag）

判据：`GL04_ACCEPTANCE.md` v1（只更新结果列）。唯一生产写入 OpenCode `opencode-go/deepseek-v4.1-flash`，default DB 紧凑新会话；Codex 独立复审。范围仅四 preview：`webui/human_fall_preview/{index.html,human_fall.js,human_fall_lib.js,human_fall_lib.test.js}`。core/config/driver/正式页/其他 webui/旧断言/旧证据冻结；无 GL05/部署/采集/板端网络/commit/reset。

输入（各只读一次）：R4 `PLAN_REVIEW.md`、R3 `02_operation_matrix.md`、R3 `90_codex_runtime.txt` 失败尾、R3 `codex_full_review.js` 四个失败断言体、`human_fall.js`/`human_fall_lib.js`；`node_runtime.py:1152-1335`（state 直接从当前候选拷贝 center/bbox，无 candidate_id，`position_source_m===candidate.center_source_m`、`center_ground_m===candidate.center_ground_m`）。

## 0. 四个 R3 FAIL 与共享根因

| 90_codex_runtime FAIL | 现行位置 | 根因 |
|---|---|---|
| V07 source target absent while unrelated candidate survives | `hfTargetGeometryPresent`（human_fall.js:517-527） | 只查 `state.position_source_m/bbox` 非空；不核当前 snapshot 是否有对应本目标的已发布候选 |
| V07 ground target stale fields cannot replace missing current target | 同上 | 只查 `state.center_ground_m/bbox_ground` 非空；候选已换成 other@12m 仍 upright |
| V09 legacy no calibration no ground raw first selection preserved | `hfSelectCandidate`:646 → `HF.observationQualified` | 把“已有目标物理观测资格”（要求 cal.schema===1/ground valid/verifier）错用于“当前选择 context”，legacy source-only 首选被拒 |
| V06 one-sided missing GDID cannot match known state binding | `observationQualified`:536-538 | `sgd != null && state.ground_derived_id != null` 只比双方非空；snapshot null / state `gd1` 被当匹配 |

根因族：①目标详情资格用 presence 而非“当前对应目标”；②选择 context 与目标物理观测未拆分为不同消费者；③nullable 绑定只比双方非空。

## 1. C01–C15 逐行映射（函数 / 赋值顺序 / 守门 / 保留）

| 行 | 到达顺序/输入 | 实际函数与先后 | R4 守门/变更 | 检查 |
|---|---|---|---|---|
| C01 | startup 无消息、legacy 无 R/t、合法 source-only | `fetch`/`hfStartSynthetic`→`hfOnRawFrame`→`hfAdvancePresent`→`hfPresentFrame`→`hfSyncCurrentSnapshot`；`hfSetMode` | 加 `selectionContextQualified`：schema 明确 2 才拒；null/null legacy 绑定可匹配；source-only 首选可用。ground 仍无显式变换即禁用 | 新增 legacy 首选正例 |
| C02 | raw→CAND→STATE / raw→STATE→CAND / →raw | `hfOnRawFrame`/`hfOnMessage`→`hfSyncCurrentSnapshot`+`hfRenderState`+`hfRenderCandidates` | 不变（R3 已过 21 项） | 保留 |
| C03 | 同内容同 ID reload、任一先到 | `hfSyncCurrentSnapshot`；`snapshotIdentity`/`candidateSignature` | 不变，same-content token 继续 | 保留 |
| C04 | CAND cal2→STATE cal1→cal2；反序 | `observationQualified`（绑定对齐） | 不变 | 保留 |
| C05 | 新 GDID、same-ID 异 R/t；state/cand 交错 | `snapshotIdentity`、`candidateSignature`、`observationQualified` | GDID 改完整 nullable：state 声明了 GDID 时 `sgd !== tgd` 即拒；两边 null 匹配；state 未声明（undefined）沿用 legacy 容忍 | 新增单侧 GDID 反例 |
| C06 | schema=2 各自/双方；坏 frame/epoch | `_parseGroundBlock`、`observationQualified` | schema 显式错值仍不支持；不改 | 保留 |
| C07 | 本目标完整→缺详情/空→只 other→恢复；ready 基线 | `hfRenderState`、`hfTargetGeometryPresent`、`hfStateAligned` | `hfTargetGeometryPresent` 改为：当前 snapshot 中按活动 mode 用 state 已发布 position/center + bbox 与候选已发布字段做一致性匹配，唯一命中才算本目标；0/多匹配 unknown/空。不 first/nearest/跟踪/浏览器算几何 | 新增 other+旧 source/旧 ground 字段两反例 |
| C08 | locked 实测→prediction/occluded/ambiguous/lost/unselected | `hfRenderState`、`hfFrame` | `position_predicted` 显式预测位仍显示预测语义（非当前候选，不伪实测）；lock/告警/history 不动 | 保留 |
| C09 | ws 断连/重连；quiet>TTL | `hfResetContext`/`dirty3d`/`hfInvalidatePresentation` | 不变（R3 GPU 一次失效已过） | 保留 |
| C10 | ground valid→unknown→none→valid；verifier | `parseGroundRender`、`observationQualified` | 不变 | 保留 |
| C11 | caller 原地改 candidate/RT/frame | `hfRenderCandidates` token、`hfSelectCandidate` | token 复核不变；guard 换为选择 context | 保留 |
| C12 | rotate/zoom/resize/DPR | `hfUpdateMvp`/`hfBoxRect`/`hfResizeOverlay` | 不变；真实 DPR NOT_RUN | 保留 |
| C13 | supports 0/3/3000/3001/9000；3D null | `validSupportPoints`、`supportBudget` | 不变 | 保留 |
| C14 | units 缺/mm/其它 | `_parseGroundBlock` units 门 | 不变 | 保留 |
| C15 | state.performance 真实字段 | `hfUpdatePerfPanel` | 不变 | 保留 |

## 2. 本轮补的组合（PLAN_REVIEW 指定）

- 旧 target 字段仍在（state.position_source_m / center_ground_m 等）× snapshot 只剩 unrelated `other`：两 mode 都必须 unknown/position 空（V07 source + ground 反例）。
- source / ground 两 mode 分别按各自已发布字段匹配，ground 不得借 source 字段通过。
- unselected 首次选择（有 cal）与 legacy source-only（cal/GDID 全 null、无 ground）首次选择都要正例；同时 cal.schema 明确 2、cal_id 单侧/异值、session/epoch/source frame 不匹仍拒。
- nullable 绑定：both-null 匹配；单侧 null/known 不匹配；state 未声明字段（partial state）沿用旧容忍，不破坏既有 42 断言。
- caller mutation / same-ID 异内容 / 静默过期 / 断连旧选择仍拒（token + context 双重）。

## 3. 兼容与冻结

- 42 旧 lib 断言与 30 通过 runtime 断言文字/语义不动，仅在 `human_fall_lib.test.js` 末尾 `console.log` 前追加 R4 test()。
- 旧兼容字段 `snapshot.ground_render` 仍作别名；`observationQualified` 对外语义保持（缺 state 侧字段容忍）。
- 仅静态比较已完成绑定字段，不新增几何算法/模型/跟踪；辅助 harness/fixtures 只写 r4，不覆写 r3/Codex 旧 JSON。
- 生产 `coordinate.ground` 无显式 R/t/support 端到端仍 V10 BLOCKED，不改 core；D01 NOT_RUN。
