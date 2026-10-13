# HR-RET-V2 回传（静立人保留 · 融合 v2 生产接入）

> 本文件自 increment 2 起登记；increment 1（能力函数 + 单测，自验 PASS）的记录见
> `docs/human_capture/evidence/2026-10-08_hrretv2_r1/`（该轮以证据目录为记录，不回填本文件）。

## 本轮信息

- 工单 / 轮次 / 执行者 / 时间：HR-RET-V2 **increment 2**；OpenCode（`opencode-go/deepseek-v4.1-flash`，本会话）；2026-10-08（Asia/Shanghai）。
- 验收表路径 / 版本 / SHA（提交时记录）：`docs/human_capture/HRRETV2_ACCEPTANCE.md` v1；SHA256 `d5d447a10f0422b0eae4199543a8809c2c724e9046375bded3847a390d1b0f43`（工作树时点；未 commit）。
- 执行方式 / 实际会话与模型：OpenCode CLI 会话，工具直写工作树；共享工作区 `D:\Code\ldiar`；未 commit / 未 push / 未 reset。
- 状态：**SUBMITTED（自验）**；V2-07/11/12/13 自验 PASS，V2-14 独立复审 NOT_RUN。软件层自验；设备/物理/部署/采集 NOT_RUN。
- 起始 branch/HEAD / 工作树 / 范围内用户差异：`master` @ `cfbb80c`（既有脏树，AGENTS.md 已登记）；本轮范围内 = 4 个代码/测试文件 + `evidence/2026-10-08_hrretv2_r2/` + 工单与验收表状态行 + 本文件；未动其它未跟踪/已修改文件。
- ponytail SKILL.md 实际读取路径：`C:\Users\30680\.config\opencode\skills\ponytail\SKILL.md`（full）。

## 集中诊断与根因覆盖

| 缺陷/验收ID | 根因 | 受影响入口、消费者与状态转换 | 修复位置 | 保留行为 |
|---|---|---|---|---|
| V2-11 | 融合能力函数（inc1）没有任何消费侧接缝：无旗标、无状态门，任意调用者都可能误启 v2 | `pipeline_frame` 的全部消费者（浏览器 `human_detect.js`、离线 harness）；artifact 状态机输出（`registration.load()` 的 VALID/DEGRADED/STALE/REJECTED/UNAVAILABLE） | `human_pipe_lib.js`：`ctx.fusion` 可选分支（缺省/`refkeys=null` ⇒ P）；`registration.js`：`fusionKeys(flag, loaded)` 门（`flag!==true` 或 `state!=='VALID'` ⇒ null） | P 路径逐位不变（D1 digest = inc2 前快照）；阈值/聚类/跟踪/Fall 不动；非 VALID fail-closed |
| V2-12 | 「加载路径 + 浏览器/节点行为」无验证：refkeys 应来自 artifact 绑定的 reference session（transform_id 解析），且浏览器默认行为未被实机核过 | artifact 消费路径（`levelingBinding`/`loadFrames`/`build_reference_map`）；`human_detect` 页面 | `registration.test.js` V2-11b（真加载路径 + 门输出直插 `pipeline_frame`）；`digest_regression.js` D1–D5；`browser_replica_check.js`/`browser_check.md` | 既有 loader 状态机、SHA 绑定、REFMAP_DRIFT 复算口径不变；不新增「自动取最新」逻辑 |
| V2-07 | 空场口径只覆盖过 P 路径（历史 0/0），v2 语义未单测 | 集成（`pipeline_frame` + `ctx.fusion`） | `empty_v2_check.js`（233658，identity-reference 口径） | P 口径记录保留，不覆盖 |

实现前同类调用者核查：`pipeline_frame` 全仓调用者仅 `human_detect.js`（页面，无 fusion 字段 ⇒ 行为不变）与测试/harness；`registration.load()` 返回值新增消费点仅 `fusionKeys`（不改变 load 本身输出）。

## 实际变更

| 文件 | 本轮用途与修改 | 与用户原差异的区分 | 提交源码SHA（inc2 前 → 后） |
|---|---|---|---|
| `pc_apps/human_replay/human_pipe_lib.js` | `pipeline_frame` 可选 `ctx.fusion`（v2 分支 + `fusion` 诊断计数；缺省 P 逐位不变） | 本会话新增（inc1 的 `extract_foreground_fused` 为上一会话未提交改动，未混改） | `96d471ad…929d` → `8b50a221…a176` |
| `pc_apps/human_replay/registration.js` | 新增 `fusionKeys` 门 + 导出 | 本会话新增（该文件其余部分未动） | `19c1fced…79f5` → `965c6c49…c5c0` |
| `pc_apps/human_replay/human_pipe_lib.test.js` | 新增旗标语义/退化/逐位一致用例 | 本会话新增 | `b2af6a85…6fe2` → `917c9563…e118` |
| `pc_apps/human_replay/registration.test.js` | 新增 V2-11a/b（真值表、真加载路径、门→管线集成） | 本会话新增 | `637d86c5…c0ad` → `310b4b43…fa12` |
| `docs/human_capture/evidence/2026-10-08_hrretv2_r2/` | 本轮证据（README / baseline_code / inc2_only.diff / 3 harness + 产物 / lib_tests.log / browser_check.md） | 本会话新增目录，不覆盖旧证据 | 见目录内 README §1/§4 |
| `docs/human_capture/tickets/HR-RET-V2.md`、`HRRETV2_ACCEPTANCE.md` | 状态与证据入口更新（不复制判据） | 本会话修改 | `HRRETV2_ACCEPTANCE.md` = `d5d447a1…0f43`（时点） |
| `docs/human_capture/returns/HR-RET-V2.md` | 本文件（自 inc2 起登记） | 本会话新增 | —— |

未写：`webui/`、`src/`、`captures/`（只读）、驱动/网络/板端、`human_detect.*`（浏览器零改动）。

## 逐条验收

| 验收ID / 入口或转换 | synthetic/offline/device | 实际命令或源码审查位置 | PASS/FAIL/NOT_RUN/BLOCKED及退出码 | 日志/样本与对应源SHA |
|---|---|---|---|---|
| V2-11a 旗标真值表（缺省/false/'on'/DEGRADED/STALE/REJECTED/UNAVAILABLE 全 null；VALID 且 occ 过滤） | offline（fixture） | `node registration.test.js`（V2-11a） | **PASS**（exit 0） | `lib_tests.log`；`registration.test.js` SHA `310b4b43…fa12` |
| V2-11b 真加载路径（artifact 绑定 → `loadFrames` → `build_reference_map` → refkeys）+ 门输出直插 `pipeline_frame` | offline（fixture，真实帧数据路径） | `node registration.test.js`（V2-11b） | **PASS**（exit 0） | 同上 |
| V2-11 负例（真实数据）：现网 artifact 全 `STALE` ⇒ `fusionKeys(true) == null` | offline（真实 artifact，只读） | `node digest_regression.js`（D3） | **PASS**（exit 0） | `digest_results.json`（state=STALE, reasons=[REFMAP_DRIFT, METHOD_STALE]） |
| V2-11 旗标关=行为不变（P 逐位） | offline（真实会话 215540 / 223757） | `node digest_regression.js`（D1/D2：基线快照 vs 当前；两遍一致性） | **PASS**（exit 0） | `digest_results.json`；基线快照 `baseline_code/human_pipe_lib.js` |
| V2-12 加载路径 + 节点行为（全链对账 + 融合臂确定性） | offline（真实会话 ×3，诊断 shadow 口径） | `node digest_regression.js`（D4/D5：复现 P2 A/B v2 数字 3/3；两遍 digest 一致） | **PASS**（exit 0） | `digest_results.json`；对账对象 `2026-10-08_fusion_v2_ab_r1/fusion_v2_chain_results.json` |
| V2-12 浏览器实际行为（默认缺省=关；页面/节点复刻一致；运行期旗标三态） | 本机浏览器（只读本地服务） | `human_detect.html?sid=…223757` DOM 读数 + 页面内探针；`node browser_replica_check.js` 复刻 | **PASS**（7/7 复刻；console 空） | `browser_check.md`、`browser_replica_results.json`（含输入 SHA 与 transform） |
| V2-07 空场 v2 0 candidate / 0 confirmed | offline（真实空场 233658，identity-reference） | `node empty_v2_check.js` | **PASS**（exit 0） | `empty_v2_results.json`（v2 joint 0/0/0；0 确认 track 帧） |
| V2-13 回归套件 | offline | `human_pipe_lib.test.js` / `registration.test.js` / `human_replay_lib.test.js` / `panel.test.js` / `human_detect_lib.test.js` | **PASS**：38/0、全 PASS、45/45、PASS、11/11；全部 **exit 0** | `lib_tests.log`（含逐套件 exit code） |
| V2-14 独立复审 | 流程 | —— | **NOT_RUN**（非本 writer，待编排方安排） | —— |
| 设备/物理/部署/采集 | —— | —— | **NOT_RUN / BLOCKED**（采集另单；板端 2026-10-08 不可达） | —— |

回归范围与冻结资产对照：不改阈值（`0.65/0.85`、`0.12m`、`occ≥0.5`、`voxel 0.15/0.12`、`3/5`、`0.75`、`8`、`EMA 0.35`、z 带 `0.10/2.50`）；
`captures/` 只读（未写）；未重签任何 artifact；未 commit。

## 未闭合与限制

- 未满足的验收ID、复现条件和解除条件：**V2-14 独立复审**（解除条件 = 非本 writer 逐条核对并记录）；**「开旗标 + VALID」的真实数据端到端**未演示——现存 artifact 全 `STALE`（代码绑定漂移），解除条件 = 按既有流程重签 artifact（另行授权；本轮未做）。合成 VALID 夹具（V2-11b）与诊断臂（D4）已覆盖语义与对账。
- 契约允许的算法/证据限制：v2 的公开代价（非人泄漏点）沿用 A/B 轮公开数字，本轮未新增代价计算；空场 V2-07 为 identity-reference 保留上界口径。
- 范围外新需求及后续建议：WP4 全链复跑（新 evidence 轮）与 WP7 Track 感知保护设计仍待编排方排期；README 顶层索引未动（由编排方登记）。
- 设备/物理未跑项：全部（未部署、未连板、未采集）。

## 交给Codex独立复审

- 现行验收表与本轮变更记录：`HRRETV2_ACCEPTANCE.md` v1（SHA `d5d447a1…0f43`）+ 本文件 + `tickets/HR-RET-V2.md`（状态行）。
- 根因诊断/完整入口检查证据：`evidence/2026-10-08_hrretv2_r2/README.md` §1/§3（含 `pipeline_frame` 调用者核查与 fail-closed 口径）。
- 源码差异与SHA证据：`evidence/2026-10-08_hrretv2_r2/inc2_only.diff`（基线快照 → 当前）+ `baseline_code/`（4 文件 inc2 前 SHA）；工作树对 HEAD 的累计 diff 为 inc1+inc2（`git diff` 可查）。
- 原始日志索引：`evidence/2026-10-08_hrretv2_r2/{lib_tests.log, digest_results.json, empty_v2_results.json, browser_replica_results.json, browser_check.md}`。
- 当前工单下一步：独立复审（V2-14）→ 复审意见决定是否安排「重签 artifact / 开旗标」的 R3.9 类评审；本轮未 commit，待编排方处理。
