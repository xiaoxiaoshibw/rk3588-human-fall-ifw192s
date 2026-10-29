
## 2026-10-15 R1 — Codex 离线统计融合试验

- 工单：FRESH-MOTS-01；唯一验收：`docs/sidequests/evidence/2026-10-15_fresh_mots_r1/ACCEPTANCE_V1.md` v1，SHA256 b8075c561ac00d1dbd1575b73e9d049e193aa36329472049d418510d6e5ded48
- 执行者/唯一研究代码 writer：Codex；本机 Node v24.14.0，未调 OpenCode 或子代理。状态 SUBMITTED，待独立复审；设备/物理 NOT_RUN。
- 起始 branch/HEAD：master / c9c4ee421cb0c8a3e4590b8f5730828b093c759a；故意脏树与全部 tracked/untracked（不含数据联接）文件SHA：`baseline.json`。未 commit/push/reset/部署/采集。
- ponytail 实际读取路径：`C:/Users/30680/.codex/skills/ponytail/SKILL.md`（full）。

### 集中诊断与根因覆盖

| ID | 根因/转换 | 实施 | 保留行为 |
|---|---|---|---|
| FM02/03 | 位移门/新占用对时序变化表达有限 | 独立 r02 复用原更新并加27邻域占用序列 | 原 r01 原码不动 |
| FM04 | 永久事件记忆不可逆，逐帧相关证据会虚增 | A2限0.5s更新、窗口事件合并、稳定观测可逆、UNKNOWN不更新 | 原始点不改、不把运动解释为人体 |
| FM06 | 稀疏扫描导致A1候选扩张；A2稳定负证据伤害历史留存 | 如实报告负结果，不按真实数据调阈值 | 不推进生产/分类器 |

### 实际变更及源码 SHA

仅新增 `sidequests/fresh_map/r02/{mots_lib.js,mots_lib.test.js,run_ablation.js,README.md}` 和本轮独立 evidence/return；范围外脏文件未由本代理修改。输入配平/denoise/参考和原版默认P0保持相同；无目标锚点/分类器。

| 文件 | SHA256 |
|---|---|
| sidequests/fresh_map/r02/mots_lib.js | ad03cc80bf4ba02381913d348f224ed90fbf6e58fb380e0eae072a3096e72a11 |
| sidequests/fresh_map/r02/mots_lib.test.js | 67977b919f61d593603c185c637faa742f8cafef55d12d0c3b3e2e5b134b00ca |
| sidequests/fresh_map/r02/README.md | b256c1a43e8b1f837ef5798b4c7fbe4ea0bd51a46c639d3486689f0a3e2071b9 |
| sidequests/fresh_map/r02/run_ablation.js | 78e44ba269d7a479fe6bd569e9c83b99d27bae8d66d8746645d951e31827d8c0 |

冻结范围317文件复核中，r01 README.md / collect.csv / collect.err / run_grid.log 与基线不同，属于运行期间观察到的并发更新，本代理没有写这些文件；原算法源码、全部依赖与主线范围哈希保持一致（`frozen_scope_check.json`）。因此不得把全工作树说成未变化。
运行结束复核15段meta/bin（含参考）及8个实现/测试/依赖SHA通过；`runs/manifest.json` 全输出哈希复核通过。

### 逐条验收

| ID | synthetic/offline/device | 检查与结果 | 证据 |
|---|---|---|---|
| FM01 | offline | PASS：本轮写入隔离，原算法/依赖未改、输入未变；并发文档/汇总更新单列 | baseline.json / frozen_scope_check.json / runs/manifest.json |
| FM02 | synthetic | PASS：多帧A0候选逐点对原r01投影一致，exit0 | test_final.log |
| FM03 | synthetic | PASS：静态参考与邻域变化触发；初始阈值错误exit1保留，真实试跑前修正到理论可达值 | test_initial_failure.log / test_final.log |
| FM04 | synthetic | PASS：单次事件门控、可逆、UNKNOWN、时钟/无效输入、50相关帧限幅和短事件合并、滚动窗口一致性，exit0 | test_final.log / interval_checks_replay.log |
| FM05 | offline | PASS：15段×3组固定参数完成，exit0，输入/源码/输出SHA复核通过 | runs/plan.json / runs/summary.json / run.log |
| FM06 | offline | PASS：如实报告候选规模/统一cohort留存/切换/耗时及不利结果 | REPORT.md / aggregate.json / 每帧CSV |
| FM07 | offline | BLOCKED：缺独立审核的人体GT，不能声称检人准确率改善 | REPORT.md |
| FM08 | offline | NOT_RUN：A3缺可靠射线可见性；A4未训练、未替换分类器 | REPORT.md |
| FM09 | device/physics | NOT_RUN：本轮未授权板端部署/采集/物理验证 | REPORT.md |

回归命令（仓库根目录）：
```powershell
node --throw-deprecation sidequests/fresh_map/r01/fresh_lib.test.js
node --throw-deprecation sidequests/fresh_map/r02/mots_lib.test.js
node --throw-deprecation docs/sidequests/evidence/2026-10-15_fresh_mots_r1/interval_checks.js
node --throw-deprecation sidequests/fresh_map/r02/run_ablation.js --outdir <全新目录>
```

原r01 15 passed/0 failed；新机制与补充检查各exit0。Python证据汇总/哈希复核均 `python -B -W error` exit0。测试总数不是工单验收。

### 未闭合与限制

- A1/A2无足够净收益证据：12段未参与本轮调参会话，候选比例A0/A1/A2 = 6.91/38.63/27.42%，统一几何cohort后窗留存=99.20/100.00/74.49%；这是几何诊断，不是人体精度。
- A0为默认P0 ev_confirm=2的体素阶段，并非运行期间另一写入者选出的evconf3完整含锚点链路；不覆盖该结论。
- 概率增益为未校准的工程设定；参考空场身份、跨日外参和人体标签未重审；短会话后窗留存NA；设备与物理NOT_RUN。

### 交给独立复审

- 唯一表/变更说明：ACCEPTANCE_V1.md + r02/README.md；原始日志与逐会话表：本轮evidence/runs。
- 独立复审 NOT_RUN；当前停留在可复现实验提交。后续应先审计占用闪烁来源并拆分事件历史/当前占用支持，不据本轮指标直接换生产算法。


## 2026-10-15 对话结论补记（用户要求“记录一下”）

- 原版 r01（灰度背景 + 新鲜度渐黑 + GHOST/retention 保留）与 r02（MOTS 风格占用统计 + 事件概率门控）是两项独立实验。r02 的负结果不否定 r01，本轮没有替换原版。
- 当前结论：保留 r01；当前固定参数的 r02 A1/A2 暂不采用、不接入生产。r02 保留源码和原始证据用于复查。
- 依据：12 段未参与本轮调参会话，A0/A1/A2 候选点比例为 6.91% / 38.63% / 27.42%；相同 A0 几何 cohort 后窗留存为 99.20% / 100.00%（四舍五入）/ 74.49%。A1 明显扩张候选，A2 又损伤历史候选留存；不能据此宣称人体识别收益。
- 口径：r01 的“候选留存 99%+”不是“人体识别准确率 99%”；97–98% 吞没的极端复现仍需要对应长静立素材，不能写成这批本地会话已复现。r02 的 A0 是默认 P0、无锚点体素阶段，不等同于 r01 选定 evconf3 的完整链路。
- 后续建议：以 r01 为基础制作浏览器回放页，观察“运动变亮 → 静止渐黑 → 候选仍保留”。本次仅记录建议，不构成 M2 实施、部署或采集授权；本代理未启动该页开发。
- 本次仅在回传账本末尾追加，未改历史证据、验收表、源码、配置或数据。没有新增实验或设备结论，原 PASS/BLOCKED/NOT_RUN 状态保持。
