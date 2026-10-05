# GL-04 R1 实现前诊断（00_diag）

执行：OpenCode `opencode-go/deepseek-v4.1-flash`（default DB；本轮session `ses_f03dbb94affeLd27gZz6bQalDp`；服务probe session `ses_f03dfd1e5ffeNIRpRvcw2NCaSI`，PROBE_OK exit0）。
范围：仅 `webui/human_fall_preview/{index.html,human_fall.js,human_fall_lib.js,human_fall_lib.test.js}`；`webui/human_fall/` 同名四文件本轮不写（preview 通过后可选同步）。core/driver/config/webui 其他/旧数据/历史证据冻结，不 commit/push/reset/部署/采集/板端联网。

基线：HEAD `8633eacf79619e96d3150d54f3fd8739be53910d`。`human_fall_lib.js` 与 `human_fall_lib.test.js` 在 preview 与正式页当前逐字节相同；`index.html`/`human_fall.js` 已有历史差异（正式页含既有功能），本轮只改 preview。全树 SHA 见本轮 `00_before_manifest.json`；`03_opencode.jsonl` 为本会话日志。旧 18 项断言原样保留（实跑 exit0）。

## 0. 单一文档化坐标入口（避免“猜一堆位置”）

生产 `core/lidar_candidates.build_snapshot` 顶层只有 `coordinate.ground_derived_id`、`calibration.ground_derived_id`、候选 `bbox_ground_min_m/max_m/center_ground_m/bbox_ground_from=actual_points`，以及 `ground.{status,frame,normal,offset_m,sensor_height_m}`；**没有 ground R/t 或 support_polygon/polyline**（GL04_ACCEPTANCE 第41–43行缺口；core 只读复核 `lidar_candidates.py:443-467,612-662`）。因此：

- 新增**唯一**可选顶层字段 `snapshot.ground_render`（synthetic 渲染扩展，显式版本化），浏览器只从此处消费变换与支持区；不从 `normal`/`offset_m` 反推变换，不从两个对角造 ground AABB，不从网格造支持区。
- 字段缺失 → `status="unavailable"`：配平入口禁用/明确 source 回退，绝不身份矩阵。
- 字段存在但版本未知/损坏/错 frame/未绑定 GDID → 禁用，不显示有效。
- 支持区只从 `snapshot.ground_render.support` 消费（`frame` 必须等于当前显示系）。

`ground_render` schema（synthetic fixture 显式提供）：
`schema_version=1, kind="ground_render", from_frame, to_frame="ground_local", units="m", calibration_id, geometry_schema_version, ground_derived_id, R[3][3]（行主序，正交 det+1）, t[3], support{schema_version,kind="support_region",frame,ground_derived_id,polygon[[x,y]...],polyline[[x,y]...]}`。
绑定：`from_frame==snapshot.source.frame_id`、`calibration_id==snapshot.calibration.calibration_id`、`ground_derived_id==snapshot.coordinate.ground_derived_id`（且与 `calibration.ground_derived_id` 一致）、`geometry_schema_version==snapshot.calibration.schema_version`。任一不等 → 不 ready。

## 1. 操作组合矩阵 → 实际函数/赋值顺序/守门（WF-CODEX-R1 R1 前置）

| 行 | 入口/组合 | 实际函数（新增/改动） | 赋值顺序 | 守门/失效 | 保留行为 |
|---|---|---|---|---|---|
| M01 | 原始↔配平；valid→unknown→none→valid 两模式 | `HF.parseGroundRender`、`hfApplyGroundRender`、`hfSetMode`、`hfRenderPanel` | 收 snapshot→`validSnapshot`→`parseGroundRender`→存 `hf.groundRender`→`hfApplyGroundRender`→`hfSetMode` 重绘 | 非 ready：配平按钮禁用、回退 source；unknown⇒unknown 色、位置 null、旧选拒绝 | source 点云/原点数组/候选 ID/事件历史不变 |
| M02 | ground 实际框 / unavailable / 无字段 / 错 derived 版本 | `HF.groundCandidateBox`、`hfFrame` 画框、`HF.candidateSignature` | 每帧 `hfCurrentCandidateSnapshot`→`groundCandidateBox`（要求 `bbox_ground_from=="actual_points"` 且有限）→`hfPlace` | `bbox_ground_from!="actual_points"` 或非有限 ⇒ 不画 ground 框（不转两角） | source 框仍可用 |
| M03 | rotate/zoom/resize/DPR-only 两坐标 | `HF.boxProjectRect`、`HF.projectPoint`、`hfResizeOverlay`、`hfFrame` | 每帧重建 MVP→`boxProjectRect(8角)`→overlay `setTransform(dpr)` | 任一角 w≤0 或 |z|>1 ⇒ behind，跳过绘制 | 请求 wire 与 candidate_id 不变 |
| M04 | 同 ID 同 frame 异 coordinate / 外来 frame / 旧列表 click / 拖选 | `HF.snapshotIdentity`、`HF.candidateSignature`、`hfSendSelect`、`hfFinishDrag`、`hfCurrentCandidateSnapshot` | click/drag 结束**重新**取当前 presented snap→比对 identity+candidate 签名→`hfSendSelect` | 闭包旧 snap / 跨 frame / 内容变化 ⇒ 拒绝；同 seq+stamp 异 frame 不匹配 | 板端 ack 语义不变；不发裸像素 |
| M05 | ws disconnect / silent expiry / reconnect，locked/pending/ready | `hfConnectionState`、`hfRenderState`、`hfRenderCandidates`、`hfFresh` | `onclose/onopen`→`hfResetContext`；每 500ms `hfRenderState`/`hfRenderCandidates` | 断连/超 2s ⇒ unknown、位置 null、旧 select 拒绝 | events/ack/pending 日志与历史保留；不重放选择 |
| M06 | 同内容 reload / 同 ID 异内容 / 新 ID / schema unsupported / caller 原地修改 | `HF.snapshotIdentity`、`HF.parseGroundRender`、`hfOnMessage` 候选分支 | 解析→`validSnapshot`→identity/内容签名比对→更新缓存与展示 | schema≠1 拒；transform/版本变化清旧显示/选择；同内容不误清 | 旧事件历史保留 |
| M07 | 当前 candidate 详情丢失 + valid baseline + 旧 state 位置 / 恢复 | `hfRenderState`、`hfCurrentCandidateSnapshot`、`hf.stateAligned` | 每 500ms 重算 aligned→未对齐则 fall unknown/position null；恢复后重新对齐 | 候选缺失但 baseline ready ⇒ 不冒用旧 position；baseline 按钮/history 不清 | 基线按钮、事件历史保留 |
| M08 | normal/tilted/no_extrinsics，source/ground 请求入口，同帧截图 | `hfSyntheticScenario`、`hfSyntheticFeed`、`hfRenderPanel`（FPS/queue/conn） | `?synthetic=` → 不连接板端 → 定时喂同帧 raw+snapshot | 无外参场景不注入 ground_render ⇒ 配平禁用；FPS/queue/connection 同屏 | 不建第二网站；复用同一 handleMessage/渲染路径 |
| M09 | startup 无消息 / ground 缺 R/t / 缺 support / malformed / unsupported | `HF.parseGroundRender`、`HF.parseSupport`、`hfSetMode` | 无消息⇒source 可用；缺字段⇒unavailable；坏⇒invalid/unsupported | 配平入口禁用；支持缺失不造支持区 | 原始点云始终可显示 |
| M10 | 有效支持 0/3/3000/3001/9000 点 × 两坐标 | `HF.supportBudget`、`HF.parseSupport`、`hfDrawSupport` | 解析→frame 匹配→预算抽样→建 Line/LineLoop | 超预算均匀抽样并保留原索引/元数据；frame 不匹配⇒未提供 | 网格常显且标注“参考网格≠已核验地面” |
| M11 | near/far/behind 全/部分裁剪 / camera 退化 | `HF.projectPoint`、`HF.boxProjectRect` | 每帧 8 角投影→遇 behind/clip 返回 behind | 部分或全部裁剪 ⇒ 不画框，无伪命中、不红屏 | 点云/面板/网格不受影响 |

## 2. 验收条目映射与检查计划

| ID | 实现/检查入口 | 检查层 | 本轮预期 |
|---|---|---|---|
| V01 | `parseGroundRender`+`applyRigid`+`hfApplyGroundRender`（source/ground 双模式、ground_local +Z 俯瞰） | lib 单测 + synthetic fixture + 源码 | 软件 PASS（synthetic）；真实 snapshot 无 R/t ⇒ fallback NOT_RUN/BLOCKED |
| V02 | `parseSupport`+`supportBudget`+`hfDrawSupport`+GridHelper 标注 | lib 单测 + 源码 | 软件 PASS（synthetic）；生产 support 缺字段 BLOCKED |
| V03 | `snapshotMeta`+`hfRenderPanel`+绑定守门+“配平预览（未地面核验）”标签 | lib 单测 + 源码 | 软件 PASS |
| V04 | `boxProjectRect`+`projectPoint`+source/ground AABB 消费 | lib 单测 + 源码 | 软件 PASS；真实 browser 旋转/zoom/resize/DPR NOT_RUN（交 Codex） |
| V05 | `snapshotIdentity`+`candidateSignature`+click/drag 重核 | lib 单测 + 源码 | 软件 PASS |
| V06 | lifecycle 守门（schema/frame/断连/unknown/verifier/旧快照） | lib 单测 + 源码 | 软件 PASS；browser 失效/恢复 NOT_RUN |
| V07 | `hfRenderState` aligned 门控 | lib 单测 + 源码 | 软件 PASS |
| V08 | synthetic 三场景入口 + 面板指标 | 源码；真实 browser 六图 | 入口软件就绪；六图 NOT_RUN（无浏览器，交 Codex） |
| V09 | 旧 18 断言原样 + 新增断言；正式页未改 | node 实跑 + diff/SHA | 软件 PASS |
| V10 | 只读 build_snapshot 复核；生产消息无 R/t/support | 源码审查 | **BLOCKED**（不改 core） |
| D01 | 真实板端/人体/性能 | device | NOT_RUN |

## 3. 根因/最小修复位置

- 缺口根因：preview 只画 source 坐标，无模式/变换/支持/视锥裁剪/提交前重核；且列表 click 使用渲染期闭包 `snap`（旧快照可提交）。
- 最小修复：pure lib 增加“单一入口解析 + 变换 + 预算 + 视锥投影 + identity/签名”；`human_fall.js` 增加坐标模式/点云变换/支持层/面板/提交重核；`index.html` 增加模式、俯视、地面面板与网格说明。所有辅助样本与日志只落本轮 evidence。

## 4. 未闭合/边界（实现前明示）

- 生产 `build_snapshot` 不提供 `ground_render`：V01/V02/V10 的**生产端到端**只能 BLOCKED，渲染能力仅由 synthetic/offline fixture 证明，不冒充端到端 PASS。
- 本轮无法运行真实浏览器：V04/V05/V06/V08 的 browser 交互证据 NOT_RUN，交 Codex 独立复现。
- 设备/物理 D01 NOT_RUN。
