# HR-RET-V2 increment 2：消费侧旗标 + 加载路径 + 浏览器/节点行为验证 + 行为 digest 回归（自验）

- **授权/工单**：[tickets/HR-RET-V2.md](../../tickets/HR-RET-V2.md)（现行授权含 increment 2）；唯一验收表 v1：
  [HRRETV2_ACCEPTANCE.md](../../HRRETV2_ACCEPTANCE.md)；计划对位：`W03_CLOSEOUT_AND_PROTECTION_PLAN.md` WP3
  （用户 2026-10-08「接着往前开发」；writer：OpenCode 本会话）。
- **基线**：branch `master`，HEAD `cfbb80c`（工作树为既有脏树）；inc2 前快照见 `baseline_code/`（4 文件 SHA 见下表）。
- **本轮 ponytail**：实读 `C:\Users\30680\.config\opencode\skills\ponytail\SKILL.md`（full）；实现路径 = 阶梯 rung 2/3
  （复用既有 `extract_foreground_fused` / `_bg_match` / `build_reference_map` / `occ≥bg_ref_occ_min` 过滤器 /
  `load()` 的 REFMAP_DRIFT 复算路径与 `loadFrames(denoised)`；浏览器零改动；零新依赖、零新参数）。
- **未 commit / 未 push**；未写 `captures/`、未重签任何 artifact；未部署、未连板。

## 1. 范围与变更（inc2 专属 diff：`inc2_only.diff`）

| 文件 | inc2 前 SHA | inc2 后 SHA | 变更 |
|---|---|---|---|
| `pc_apps/human_replay/human_pipe_lib.js` | `96d471ad…929d` | `8b50a221…a176` | `pipeline_frame` 支持可选 `ctx.fusion`（缺省/`refkeys=null` ⇒ P 逐位不变；显式 refkeys ⇒ v2 融合删除，返回附 `fusion` 诊断计数） |
| `pc_apps/human_replay/registration.js` | `19c1fced…79f5` | `965c6c49…c5c0` | 新增消费侧门 `fusionKeys(flag, loaded, options)`：默认关；仅 `VALID` 启用；其余 fail-closed → null；VALID 时按 artifact 绑定的 reference session/leveling（transform_id 解析）重建参考静态键 |
| `pc_apps/human_replay/human_pipe_lib.test.js` | `b2af6a85…6fe2` | `917c9563…e118` | 新增：旗标缺省/`refkeys=null` 与 P 逐位一致；给 refkeys 才走 v2 + 诊断计数 |
| `pc_apps/human_replay/registration.test.js` | `637d86c5…c0ad` | `310b4b43…fa12` | 新增 V2-11a（真值表：缺省/false/'on'/DEGRADED/STALE/REJECTED/UNAVAILABLE/occ 过滤）+ V2-11b（真实加载路径重建 refkeys + 门输出直插 `pipeline_frame` 集成） |

语义契约：`删除 p ⇔ ref_match(p) ∨ (online_match(p) ∧ ref_supported(online_hit(p)))`（不改 `0.65/0.85`、`0.12m`、`occ≥0.5`、聚类/跟踪/Fall）。

## 2. 验证结果（本目录产物）

| 验收项 | 证据 | 结果 |
|---|---|---|
| **V2-11a/b** 旗标默认关=行为不变；开=仅 VALID 走 v2，其余保持 P | `lib_tests.log`（`registration.test.js` 全 PASS）；`digest_results.json` D1/D2/D3 | **PASS（自验）** |
| **V2-11-D3** 真实 artifact 负例（现网四个 artifact 均因代码绑定漂移 `STALE`）→ `fusionKeys(true, …) == null` | `digest_results.json` D3 | **PASS（自验）** |
| **V2-12 节点** 加载路径（artifact 绑定 → refkeys）+ 行为 digest 回归 | `digest_results.json`：D1 基线快照 vs 当前 P digest 逐位一致（215540 / 223757）；D2 两遍一致；D4 诊断 v2 对账 P2 A/B 数字（3/3 会话：raw/fg/cleanup p50 + labels + confirmed 全等）；D5 两遍一致 | **PASS（自验）** |
| **V2-12 浏览器** 实际行为 + 回退 | `browser_check.md` + `browser_replica_results.json`（node 复刻 7/7 PASS：静态体素 1720 + 帧 1/30 三组计数逐字符一致；页面运行期旗标三态探针；console 空；页面无 artifact ⇒ 恒 P） | **PASS（自验）** |
| **V2-07** v2 语义下空场 0 candidate / 0 confirmed | `empty_v2_results.json`：空场 233658 identity-reference（自身全帧参考；删除不窄于任何模板=保留上界），v2 臂 joint `{CONFIRMED_HUMAN:0, HUMAN_CANDIDATE:0, NON_HUMAN:0}`、0 确认 track 帧 | **PASS（自验）** |
| **V2-13** 相关回归全过 | `lib_tests.log`：`human_pipe_lib` **38/38**、`registration`（T37-01…21 + V2-11a/b）全 PASS、`human_replay_lib` **45/45**、`panel` PASS、`human_detect_lib` **11/11**；全部 exit=0 | **PASS（自验）** |
| **V2-14** 独立复审 | —— | **NOT_RUN（待非本 writer 安排）** |

## 3. 关键口径与负例说明

1. **P 逐位不变的基线** = inc2 前工作树快照（`baseline_code/human_pipe_lib.js`），不是 HEAD（HEAD 早于 R39 最小统计修复）。
2. **无 VALID artifact（事实）**：现存四个 registration artifact 的 `code_id/refmap` 绑定随 inc1/inc2 代码变更漂移 → `STALE(REFMAP_DRIFT, METHOD_STALE)`。
   因此「开旗标 + VALID」在真实数据端到端未演示；以合成 VALID 夹具（V2-11b：真数据帧 + 按新 refmap 重签的 artifact，load 走完整校验得 VALID）
   与「诊断臂」（D4：直读 transform 的离线复现，**非生产消费**）覆盖。若需真实启用：按既有流程重签 artifact（另行授权，本轮未做）。
3. **D4 诊断臂**：三段新会话（215540/215623/215643）shadow 注册 + v2，与 `2026-10-08_fusion_v2_ab_r1/fusion_v2_chain_results.json` 的 v2 数字逐一相等
   （这也同时复核 inc1+inc2 未改语义）。代价计数 `n_online_only_kept` 已随产物公开。
4. 空场 V2-07 用 identity-reference：若真实模板更窄，v2 保留只会更少 → 0/0 结论对本口径最严。

## 4. 产物清单

- `baseline_code/`（inc2 前 4 文件快照）、`inc2_only.diff`（基线→当前）、`lib_tests.log`（5 套件 + exit codes）。
- `digest_regression.js` / `digest_results.json`（D1–D5）。
- `empty_v2_check.js` / `empty_v2_results.json`（V2-07）。
- `browser_replica_check.js` / `browser_replica_results.json` / `browser_check.md`（V2-12 浏览器）。
- 未采集：浏览器截图（工具要求桌面窗口可见；以 DOM 读数 + 节点复刻替代，见 `browser_check.md` §5）。
- → 同源可视化（新证据轮）：[2026-10-08_hrretv2_visual_r1](../2026-10-08_hrretv2_visual_r1/README.md)——P vs v2 逐点命运视图（诊断口径直读 STALE artifact 的 transform）。

## 5. 边界

- 不改变 W03 现行唯一验收表（R3.7 `06_test_matrix.md` v1）与 W03 状态；不上 ML；W04–W09 不启动。
- 设备/物理/部署/采集：NOT_RUN 不变；`captures/` 只读、无写入。
- 独立复审（V2-14）待编排方派非本 writer；本轮自验不等于 ACCEPTED。
