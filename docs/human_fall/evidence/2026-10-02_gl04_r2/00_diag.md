# GL-04 R2 集中返工诊断（00_diag）

判据：GL04_ACCEPTANCE v1（结果列只更新）。唯一生产写入者 OpenCode `opencode-go/deepseek-v4.1-flash`，default DB，同 model default-DB 紧凑新会话（R1 `ses_f03dbb94affeLd27gZz6bQalDp` 保留）。范围：仅 `webui/human_fall_preview/{index.html,human_fall.js,human_fall_lib.js,human_fall_lib.test.js}`；正式页（外部新增 Q/E 旋转）保留不写。core/config/driver/其他 webui/原数据/旧证据/旧断言冻结；无 GL05/部署/采集/板端网络/commit/reset。生产消息 R/t/support 缺口 V10 继续 BLOCKED，不改 core/topic。D01 NOT_RUN。

输入：R1 `CODEX_REVIEW.md`、`10_codex_runtime.txt`（12 FAIL / 6 PASS）、`02_operation_matrix.md`、`GL04_ACCEPTANCE.md` v1、R1 独立 harness/checks（字段名来源）。不重读全部历史大文档。

## 0. 三个共享根因（R1 CODEX_REVIEW 第 35–39 行）

1. **权威输入/当前显示帧未统一**：R1 自创顶层 `snapshot.ground_render` 作唯一入口；用户要求 `snapshot.coordinate.ground` 子块 + `snapshot.ground.support_polygon/support_polyline`。且 `hfOnMessage(CAND)` 收到任何 snapshot 立即写 `hf.groundRender` 并重投点云，未来/外来 snapshot 抢改当前帧。
2. **资格/生命周期/提交绑定不足**：`hfStateAligned` 不要求当前实际候选详情与 verifier/schema/ground 资格；列表 click 闭包持可变旧 snapshot；`validateSelection` 只比 candidate_id，不比候选签名/变换内容；drag 用 source 框。
3. **synthetic/性能证据误义**：`syntheticScenario` 在浏览器构造几何/逆变换/AABB；FPS 取 `pcPresHz`（呈现 Hz）非真实 `renderer.render` 帧数；queue_dropped 取 `pcSkip`（未呈现）冒充队列丢弃。

## 1. R1 独立失败 → 函数/赋值顺序 → R2 守门/检查（固定不改判据）

| R1 失败 | 现行函数/赋值 | R2 守门/改动 | 对应 ID |
|---|---|---|---|
| V02 exact requested `ground.support_polygon` entry `unavailable` | `HF.parseGroundRender` 只读 `snapshot.ground_render.support` | 新增权威源 `coordinate.ground` + `snapshot.ground.support_polygon/polyline`（默认 frame=to_frame、schema=1、GDID=block GDID）；旧 `ground_render` 仅兼容；两源共存且变换不一致→`invalid/conflicting_ground_sources` | V02/V10 |
| V06 valid transform + unknown/none ground 仍 ground | `hfSetMode` 只看 `groundRender.status`；无 ground 状态守门 | `_parseGroundBlock` 校验 `calibration.ground_status`（缺则 `snapshot.ground.status`）==`valid`，否则 `unqualified`；`hfSetMode`/`hfSyncCurrentSnapshot` 回退 source | V03/V06/M01 |
| V06 unsupported calibration schema 仍 ground | geometry 绑定相等即通过 | `cal.schema_version !== 1` → `unsupported` | V03/V06/M09 |
| V06 verifier unavailable 仍 upright | `hfStateAligned` 不读 `sensor_quality` | `HF.observationQualified`：`sensor_quality.ground_verifier_available===false` 或 `ground_monitor.status!=='ok'` → 不齐 | V06/V07/M05 |
| V07 无/空 candidate + ready baseline 仍 upright/旧位置 | `hfStateAligned` 无 snap 时用 state source key 匹配 | `hfCurrentCandidateSnapshot()` 必须存在且 `candidates.length>0`（经 `observationQualified`） | V06/V07/M07 |
| V05 list closure 同 ID 改 candidate 内容仍发 | `validateSelection` 只查 candidate_id | `hfSelectCandidate` 比对不可变 render token：`snapshotIdentity`+`candidateSignature`（render 时捕获，submit 时对当前 fresh） | V05/M04/M06 |
| V05 同 ID 改 R/t 仍发 | `snapshotIdentity` 不含变换内容 | `snapshotIdentity` 加 `groundTransformKey`（from/to/cal/GDID/geom/R/t） | V05/M04/M06 |
| V05 caller 原地修改后旧按钮仍发 | 按钮闭包只持可变 snap | `hfRenderCandidates` 渲染时捕获 token 传入 onclick；`hfSelectCandidate(closed,id,token)` 用 token 签名 | V05/M04/M06 |
| V06 未来外来 snapshot 抢改当前 R/t（源 X 2.8→22.8） | `hfOnMessage(CAND)` 立即 `hf.groundRender=...; hfApplyModeToBuffers()` | 拆出 `hfSyncCurrentSnapshot()`：只从 `hfCurrentCandidateSnapshot()`（当前 presented entry）取 metadata/变换/支持；外来/未来只入缓存，待其 raw 被 present 才生效 | V01/V03/M04/M06 |
| V03 ground 模式 hfPos 非 ground、hfCoord 说 innolidar | `hfRenderState` 固定 `position_source_m`/固定源坐标文案 | ground 模式位置取 `position_ground_m`→`center_ground_m`→当前候选 `center_ground_m`；`hfCoord` 分源帧/`ground_local` 两文案 | V03/M08 |
| V08 FPS=pcPresHz、queue=pcSkip | `hfUpdatePerfPanel` 读 `pcPresHz`/`pcSkip` 文本 | 包装 `renderer.render` 计真实 render 次数/1s；queue 取已知字段否则 `unknown`；连接含 synthetic 态 | V08/M08 |
| （R1 browser 几何越界） | `hfStartSynthetic` 调 `HF.syntheticScenario` 在浏览器构几何 | 浏览器入口仅 `fetch` 静态 JSON fixture（`?fixture=` 或 r2 默认路径）；`syntheticScenario` 仅 Node/CommonJS 分支导出 | V08/V09/M08 |

## 2. 操作矩阵 → 函数/赋值顺序/守门/检查（全行）

| 行 | 入口/组合 | 实际函数（改/增） | 赋值顺序 | 守门/失效 | 保留行为 |
|---|---|---|---|---|---|
| M01 | 原始↔配平；valid→unknown→none→valid 两模式 | `HF.parseGroundRender`、`hfSyncCurrentSnapshot`、`hfSetMode`、`hfRenderPanel` | 收 snapshot→`validSnapshot`→存缓存→`hfAdvancePresent`→`hfSyncCurrentSnapshot`（identity 来自当前 presented）→`parseGroundRender`→按 ready 设 `coordMode` | 非 ready/unqualified：按钮 disabled、回退 source；unknown/none ⇒ fall unknown/位置 null、旧选拒 | source 点云/原点数组/candidate ID/事件历史不变 |
| M02 | ground 实际框 / unavailable / 无字段 / 错 derived 版本 | `HF.groundCandidateBox`、`HF.candidateBox`、`hfFrame` 画框 | 每帧 `hfCurrentCandidateSnapshot`→`candidateBox(c,mode)`（ground 要求 `bbox_ground_from=="actual_points"` 且有限）→`hfPlace` | 非 actual/non-finite ⇒ 不画 ground 框（不转两角） | source 框仍可用 |
| M03 | rotate/zoom/resize/仅 DPR，两坐标 | `hfUpdateMvp`、`HF.boxProjectRect`、`hfResizeOverlay`、`hfFrame` | 每帧重建 MVP→8 角投影；DPR 变化同步 renderer `setPixelRatio`+`resize3d`+overlay 宽高 | 任一角 w≤0 或 |z|>1 ⇒ behind 跳过 | 请求 wire/ID 不变 |
| M04 | 同 ID 同 frame 异 coordinate / 外来 frame / 旧列表 click / 拖选 | `HF.snapshotIdentity`、`HF.candidateSignature`、`hfRenderCandidates`、`hfSelectCandidate`、`hfFinishDrag` | click/drag 以 render 时 token（identity+签名）对当前 fresh entry 复核→`hfSendSelect`；drag 用当前 mode 框 8 角 | 闭包旧 snap / 跨 frame / 内容/变换变化 ⇒ 拒；同 seq+stamp 异 frame 不匹配 | ack/lock/capture/release 语义不变；不发裸像素/client id |
| M05 | ws disconnect / silent expiry / reconnect；locked/pending/ready | `hfConnectionState`、`hfRenderState`、`hfRenderCandidates`、`hfFresh`、`observationQualified` | onclose/onopen→`hfResetContext`；500ms 刷新 | 断连/超 2s/verifier unavailable ⇒ unknown、位置 null、旧 select 拒 | events/ack/pending 日志与历史保留；不重放选择 |
| M06 | 同内容 reload / 同 ID 异内容 / 新 ID / schema unsupported / caller 原地修改 | `HF.snapshotIdentity`、`groundTransformKey`、`HF.parseGroundRender`、`hfSelectCandidate` | 解析→identity/签名比对→更新缓存/展示 | schema≠1/坏绑定拒；transform/内容变化清旧选；同内容不误拒 | 旧事件历史保留 |
| M07 | 当前 candidate 详情丢失 + valid baseline + 旧 state 位置 / 恢复 | `hfRenderState`、`hfCurrentCandidateSnapshot`、`HF.observationQualified`、`hfStateAligned` | 刷新重算 aligned→未齐 fall unknown/位置 null；恢复再对齐 | 候选缺失/空但 baseline ready ⇒ 不冒用旧 position；baseline 按钮/history 不清 | 基线按钮、事件历史保留 |
| M08 | normal/tilted/no_extrinsics，source/ground 请求入口，同帧截图 | `hfStartSynthetic`（fetch fixture）、`hfUpdatePerfPanel` | `?synthetic=`→禁连板端→fetch 离线 JSON→定时喂同帧 raw+snapshot | 无外参 fixture 无 ground 块 ⇒ 配平禁用；FPS/queue/conn 同屏 | 复用同一 handleMessage/渲染路径；不建第二网站 |
| M09 | startup 无消息 / ground 缺 R/t / 缺 support / malformed / unsupported | `HF.parseGroundRender`、`HF.parseSupport`、`hfSetMode` | 无消息⇒source 可用；缺字段⇒unavailable；坏⇒invalid/unsupported | 配平入口禁用；支持缺失不造支持区 | 原始点云始终可显示 |
| M10 | 有效支持 0/3/3000/3001/9000 点 × 两坐标 | `HF.supportBudget`、`HF.parseSupport`、`hfDrawSupport` | 解析→frame/GDID 绑定→预算抽样→`LineLoop`(面)/`Line`(线) | 超预算均匀抽样保留原索引/`sampled_from/total`；frame 不匹配⇒未提供 | 网格常显并标注“参考网格≠已核验地面” |
| M11 | near/far/behind 全/部分裁剪 / camera 退化 | `HF.projectPoint`、`HF.boxProjectRect` | 每帧 8 角投影→遇 behind/clip 返回 behind | 部分/全部裁剪⇒不画框，无伪命中、不红屏 | 点云/面板/网格不受影响 |

## 3. 兼容与冻结

- R1 顶层 `ground_render` 作为旧 preview 兼容输入保留；权威输入为 `coordinate.ground`+`ground.support_*`，两源共存冲突即拒，旧路径不覆盖/绕过新守门；实际生产 topic 不变，不以兼容测试冒称后端已提供（V10 BLOCKED）。
- 原 18 + R1 旧断言文本不动，只在 `human_fall_lib.test.js` 末尾追加新检查。
- `syntheticScenario` 仍在 `human_fall_lib.js`，但只在 CommonJS/Node 分支导出并执行；浏览器入口只 `fetch` 本轮 r2 离线 fixture。
- 辅助检查/日志/fixtures/manifest 只写 r2；不覆写 r1 或旧证据；全树基线见 `00_before_manifest.json`。
