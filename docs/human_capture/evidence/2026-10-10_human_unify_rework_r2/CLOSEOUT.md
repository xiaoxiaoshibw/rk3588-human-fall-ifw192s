# HUMAN-UNIFY-R1 R2 返工当前收口

2026-10-10（Asia/Shanghai）。Codex唯一writer。状态：**SUBMITTED，功能缺陷R01–R08已修复并独审PASS；整体未ACCEPTED**。性能检查FAIL，原全树冻结S02 BLOCKED；算法/生产资格BLOCKED，设备/物理/部署/采集NOT_RUN。

唯一验收表：[v1](../../HUMAN_UNIFY_R1_ACCEPTANCE.md)。使用技能：`C:/Users/30680/.codex/skills/ponytail/SKILL.md`。起始master/777296d；未commit/push、reset/checkout/clean；未启动其他writer。原human_replay生产文件没有本轮写入，RF并发改写另记EXTERNAL_DEPENDENCY_CHANGE.md，不回退他人工作。

## 最终软件验证

| ID/检查 | 当前结果 | 最终证据 |
|---|---|---|
| R01–R08 | PASS（作者自验+指定独审） | tests_03.txt、OPENCODE_REVIEW_01/02.md |
| 功能回归 | PASS，96项/7suite，exit0 | schema13+loader16+smoke9+replay11+edge14+model12+rework21 |
| A/B逐帧生产对拍 | PASS，9会话1196帧，exit0 | parity_04.json/txt；同一明确配平输入，不冒称浏览器/物理验证 |
| S01 当前来源与矩阵 | PASS | runs_03：45JSON+45CSV、5980帧次；matrix_summary_03.json核对当前实现/实际输入/JSON/CSV完整SHA，A=U1计数一致 |
| 相关生产JS回归 | PASS | production_js_01.txt六suite；独审01又实际复跑overlay/pipe/RF，各exit0 |
| S02 原始全树冻结 | BLOCKED | preservation_01/02.json：范围外RF版本变化；提交core本身SHA一致，不虚报全树无改动 |
| Q01 指定独立复审 | PASS | Go Flash/plan/default DB，两次probe真实exit0，两次audit真实exit0；四处追加来源链加固PASS |
| D01 | NOT_RUN | 没有设备/物理/部署/采集执行 |

补充独审02生成时聚合/性能尚未完整，其S01待核定与perf NOT_RUN作为历史保留；本轮之后实际生成matrix_summary_03和perf_02/03，当前结果以本表为准，不改审计原文。

## 性能实际失败，不放宽门限

当前依赖`rf_person.js` SHA=`99b02c725f303f07e574b310fdd459ad3e28dd2469ba1e882661c30f370529d6`。Node v24.14.0，AMD Ryzen AI 9 H 365。实际运行的3会话×3模式门为P95<50ms且heapUsed<1500MB：

- perf_02：**FAIL / exit1**，8/9；dynamic U3 P95=71.49ms。
- 独审和其他本轮测试结束后单独perf_03：**FAIL / exit1**，8/9；dynamic BASE_B P95=53.33ms，U3=42.62ms。
- 两批来源SHA守卫均PASS。失败日志/JSON均保留；没有调整阈值、删除失败或继续重跑刷通过。CPU/系统负载未完全控制，不能确定失败全由RF实现或引擎引起，也不能声称性能稳定达标。
- 记录RSS/external和heapUsed分开；不是总内存1500MB门，未涵盖加载/背景构建全生命周期峰值。旧依赖perf_01的9/9 PASS不代表当前版本。

## 实际代码变化

- BASE_B直接使用原生产暴露的find_clusters/associate，保留中心/门限/寿命/一对一/年龄确认，不再错用A跟踪器；取消额外A去噪，强度与raw点索引绑定。
- A各过滤层保序映射raw索引；候选包围盒/来源真实可追溯。背景与帧共用坐标契约，支持raw/已配平/显式R/T，冲突拒绝，CLI identity/ref实际生效。
- 全会话重置报告及状态，强制session_generation拒绝旧回调；重复/回退/跳帧有明确策略和行为断言。实例PIPE、RF树、B状态及globalThis隔离，U6配置实际生效；未知/未实现配置拒绝。
- eager/lazy共享尺寸/元数据/连续帧边界检查；short read拒绝，partial read累积，异常关闭句柄；输入SHA来自实际读到的字节。
- 保留点按raw索引去重，来源fg/retained/merged；仅独立FG确认建立/刷新bank，保留确认不自续命，过期退出。真实人体保留收益未证明。
- 输出v2使用accepted/rejected候选，不称家具GT；末帧current与历史ever分开。不从候选数推断真人人数/家具免疫/recall。
- runner、对拍和性能加入来源漂移守卫，拒绝运行期输入/实现变化；输出必须新路径，不覆盖证据。

## 历史与当前证据分界

runs_01与parity_02/perf_01对应原RF实现，保留历史；parity_03跨依赖变化窗口，不作来源闭合证据；runs_02仅三个会话后外部RF SHA守卫触发，中止，partial results不能当完整验收。本轮之外的RF改写保留，不冒称已由本工单审查其数学/特征正确性。

当前只采信守卫通过、完整复算的runs_03、parity_04，以及记录失败的perf_02/03。RF特征变化会改变U3数值，因此不沿用旧报告的25/23等计数。详表见[AB_RESULTS_CURRENT.md](AB_RESULTS_CURRENT.md)。任何阶段的confirmed track都不是无GT的人数。

## 下一步边界

功能修复已交付，写入已停止。正式总体软件/算法/生产不放行：仍需RF变更归属及稳定版本、性能定位、独立人工GT与新场景留出。用户计划的九类重录尚未作为数据或GT入库，修正时长/原sid/及时下载/独立空场测试建议见NEW_CAPTURE_NOTES.md。本轮不自动采集、部署、接浏览器/EXE、切模型或激活ML。
