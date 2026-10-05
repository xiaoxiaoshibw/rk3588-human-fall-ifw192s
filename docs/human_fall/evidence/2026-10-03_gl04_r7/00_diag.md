# GL-04 R7 实现前设计映射 / 2026-10-03

同工作项、`GL04_ACCEPTANCE.md` v1，唯一 OpenCode Go Flash / default DB writer，Codex 独审。
R6 原 95/97 全部闭合；r6 lib 54 独立 exit0；R6 CODEX_REVIEW 只剩 **V07/V09/C08** 的 source 位置
来源消费者 FAIL（`_state_payload` 1156–1186 / 1208–1216、INTERACTION 165/178 为来源契约）。
本轮只写四 preview 最小必要改动 + 新 r7 证据 + returns 末尾；R6/旧证据、正式页、core、config、
driver、其它 webui、数据冻结。

ponytail SKILL.md 实际读取路径：`C:\Users\30680\.config\opencode\skills\ponytail\SKILL.md`
（本机 skill 工具加载，full）。R7 PLAN_REVIEW 明确 R6 回传误称 `.config`/skill；本次二选一按
R7 指令“先实际读、回传准确路径”处理：以 skill 工具注入的 `.config\opencode` 路径为准（见
本节末“ponytail 路径如实说明”）。

## 0. R6 复审残留 FAIL 与共享根因

| R6 FAIL | 现行位置 | 根因 |
|---|---|---|
| `position_source_from=unavailable` 仍显示 3m source XYZ + “实测” | `human_fall.js:hfRenderState` 467–473（position）、485–489（hfPred 实测） | 显式负向来源只并入 physical 门（`actualObservationQualified`→`hfPhysicalObserved`），当前位置/“实测”仍只看三元组 + `position_predicted` |
| `position_source_from=predicted` 且 `position_predicted=false` 仍显示 source XYZ + “实测” | 同上 | 同上；`position_predicted` 布尔与来源字段不一致时未以来源字段为准 |

共享根因：缺一个**位置来源 provenance 门**供所有“当前 source 位置/实测标签”消费者使用。
`bbox_observed=false` 是独立框/physical 标志，不得连带清空 `actual_points` 合法 raw 中心；
缺字段/null legacy 保留。仅约束 source 中心可用性，不新增 tracking/几何/变换/单位/严格组合框架。

## 1. C08 全部位置/来源消费者逐格映射（函数 / 赋值顺序 / 判据）

`human_fall.js` 单闭包，运行时顺序：`handleMessage`(state) → 存 `hf.lastState`；`hfFrame`
（每 raw 帧）→ `hfSyncCurrentSnapshot()` 取 `hfCurrentCandidateSnapshot()`（`hfCurrentCandidateEntry`
以 `sameContext` + frame 匹配）→ `hfRenderState()`；`hfRenderCandidates()`（列表/拖选）；面板。

| 消费者（行号，R6 基线） | 取值来源 | 现判据 | R7 是否改 |
|---|---|---|---|
| `hfRenderState` 位置 `hfPos` 463–473 | `position_ground_m`/`center_ground_m`（ground）或 `position_source_m`（source）；`position_predicted` 时置 null | source 分支只查 `HF.isTriple(s.position_source_m)` | **改**：source 分支加共享 provenance 门 |
| `hfRenderState` `hfPred`/“实测” 485–489 | `hasMeasuredPos = track_id && isTriple(position_source_m)` | 只看三元组 | **改**：`hasMeasuredPos` 复用同一 provenance 门 |
| `hfRenderState` 坐标/标定 `hfCoord` 475–484 | `s.source.frame_id` / `cal`（非 source 位置值） | 描述系/标定，无位置值 | 不改（`source_m` 引用仅为 srcFrame 文本来源，非位置读数；避免误伤） |
| `hfCurrentActual` 524–527 | `track_id && !position_predicted && track_status∈{null,locked}` | 状态/lock 门 | 不改（R6，历史回归） |
| `hfPhysicalObserved` 532–538 | `hfStateAligned && hfCurrentActual && observationQualified.ok && actualObservationQualified.ok` | physical 门 | 不改（R6）；**不得**把 `actualObservationQualified`（含 bbox 负旗）整体套到 raw 位置 |
| `hfTargetGeometryPresent` source 分支 577–594 | `position_source_m`/`bbox_source_*` 与唯一 candidate 逐位匹配；预测短路 | 三元组唯一匹配 + `hfCurrentActual` | 不改（R6，C07/C08 历史回归）；来源否定在 provenance 门，不在此清 raw |
| `hfStateAligned` 620–641 | 源模式 `sourceAlignmentQualified` | 现不含位置来源 | **可不改**：provenance 只在**读数消费者**（位置/实测）加门；保持 aligned 判定语义不扩散 |
| `hfRenderCandidates` 642–... / `hfSelectCandidate` / `hfFinishDrag` | `selectionContextQualified` | 选择资格（不要求已有目标实测） | 不改（R6/C11/C14）；选择本身不因来源负旗被禁 |
| `hfFrame` target box 1060–1090 | `stateMatches && candidateBox(s,mode)`；`physical`/`pred` 决定颜色 | 目标框/标签 | 不改（R6 灰诊断保留；bbox 只经 target 框视觉） |
| `hfRenderPanel` 779+ | `state.performance` 优先 | 面板 | 不改（R3/V08） |

`human_fall_lib.js` 既有门（不改语义，仅复用）：`actualObservationQualified`(654–660) 已含
`bbox_observed===false` 与 `position_source_from!=null && !==actual_points` 负向。**该函数整体
含 bbox 否定，R7 不能直接用于 raw 位置门**，否则 `bbox_observed=false` 会错误清掉合法 raw 中心
（R6 98 的 PASS 例）。因此 R7 新增一个**只查位置来源**的共享门。

### 抽出的共享判据（最小）

`position_source_from` 语义（Node `_state_payload`）：`actual_points`=实际点；`unavailable`=无
source 位置；`predicted`=预测位置；缺失/`null`=legacy（保留 raw，兼容）。判据：

- `position_source_from == null` → 保留（legacy）。
- `position_source_from === "actual_points"` → 保留。
- 其他显式值（`unavailable`/`predicted`/其他字符串）→ 当前位置不可显示、不得标“实测”。

**与 `position_predicted` 的关系**：R6 98 两 FAIL 为 `position_source_from` 显式负向但
`position_predicted=false`（矛盾组合）；冻结契约以**来源字段**为准，故门只看来源字段，不额外要求
`position_predicted`。`position_predicted=true` 的合法预测仍走既有 `pos=null` + 预测灰诊断（保留）。
不把 `bbox_observed=false` 并入该门。

place: `human_fall_lib.js` 新增 `sourcePositionQualified(state)`（只查来源字段），导出；`human_fall.js`
新增 `hfSourcePositionQualified()` 包装（取 `hf.lastState`），在 source 位置分支与 `hasMeasuredPos`
共用。零几何/零 tracking/零新依赖。

## 2. C01–C15 矩阵（本轮逐行处置）

| C行 | 组合/消费者 | ID | R7 处置 |
|---|---|---|---|
| C01 | legacy cal/GDID/`source_from` 缺失/null × locked source 读数 | V09 | 不改；门对缺失/null 放行，原 first select/XYZ/track 保留（原 54/92） |
| C02 | raw/state/candidate 任一先到 × raw 来源变化 | V07 | 不改；位置/实测用当前版本字段（门读 `lastState` 当前值） |
| C03 | 同内容 reload / 仅相机变动 | V05 | 不改；token/ID 不变，来源资格不受 camera 影响（原 90） |
| C04 | cal 版本交错→双侧恢复 | V06 | 不改；混配 unknown/拒旧、恢复仅当前（原 90） |
| C05 | known/null/undefined cal/schema/GDID、同 ID 异内容 | V05/06 | 不改；R6 绑定/token 全保留（原 90/97/54） |
| C06 | schema2/frame/epoch/verifier 非法 | V06 | 不改；已有 source/physical 失效不放宽（原 90/97） |
| C07 | 当前目标→空/other/重复→唯一恢复 | V07 | 不改；0/多匹配未知、历史不背书（原 90/97） |
| C08 | locked × `source_from{missing,null,actual_points,unavailable,predicted,other}` × `bbox_observed{missing,true,false}` × `position_predicted` | V07/09 | **本轮修**：显式非 actual 来源 → 当前位置 `--`、不标“实测”；actual_points/legacy 保留 raw；`bbox_observed=false` 仅 physical（不连带清 raw 中心）；合法预测灰诊断/年龄/当前空原义保留 |
| C09 | pending/ready silent/disconnect→reconnect | V06/09 | 不改；R6 真实 browser 16–21 与 90 复用 |
| C10 | ground valid/unknown/none/verifier 与 source 合法实际读数 | V06 | 不改；R6 raw/physical 分门保留 |
| C11 | caller 变 candidate/RT/units/coordinate token × list/drag | V05 | 不改；旧拒/当前原 ID 保留（原 90/97/54） |
| C12 | rotate/zoom/resize/DPR/clip 退化 × 两 mode | V04 | 不改；隔离 DPR-only/完整 clip 仍 NOT_RUN |
| C13 | support0/3/3000/3001/9000/显式坏 units | V02 | 不改；预算/索引/单位门保持 |
| C14 | source/support units 正确/缺失/mm/其它 × 当前/旧选择 | V03/05 | 不改；R6 units 门保留，不因来源修改降低 units 资格 |
| C15 | normal/tilted/no_extrinsics 固定 frame、完整绑定、offset=t[2] | V08 | 不改；R6 生成器/六图已过，source_from 只如实消费 |

## 3. 最小共享改动清单（提交前对照）

1. `human_fall_lib.js`：新增并导出 `sourcePositionQualified(state)`（只查 `position_source_from`，
   缺失/null/actual_points 放行，其它显式值拒）。
2. `human_fall.js`：新增 `hfSourcePositionQualified()`（包 `lastState`）；source 位置分支
   `else if (HF.isTriple(s.position_source_m))` 加"且 provenance ok"；`hasMeasuredPos` 加 provenance ok。
3. 不改 `actualObservationQualified`、`hfPhysicalObserved`、`hfTargetGeometryPresent`、
   `hfStateAligned`、`predictionDiagnosticQualified`、`hfFrame` 灰诊断路径。
4. r7 证据脚本：原 90/92/95/97 + lib 54 复制到 r7 运行（新输出）；新增来源正/负例
   （missing/null/actual_points/unavailable/predicted/other × bbox × position_predicted 的负/恢复正例），
   只断言“非测量/非 physical”。

## 4. ponytail 路径如实说明

R7 PLAN_REVIEW 记载 R6 CLI 实际 read 为 `.claude` 路径，回传误称 `.config`/skill 加载。
本会话由 skill 工具在 `C:\Users\30680\.config\opencode\skills\ponytail\SKILL.md` 注入（内容
即 ponytail SKILL.md，full）。以工具实际注入路径为准；若 Codex 以 R6 CLI read 记录为准则为
`.claude` 路径。两者均指向同一 ponytail 技能内容，未用别的技能冒充。
