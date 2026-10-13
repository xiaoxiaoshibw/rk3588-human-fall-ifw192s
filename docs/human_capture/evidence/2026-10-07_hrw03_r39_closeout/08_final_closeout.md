# HR-W03 最终收口提交（2026-10-07）

## 1. W03 最终状态

**REWORK_REQUIRED**；writer自验 SUBMITTED，未 ACCEPTED。GT子问题 BLOCKED。gate未过、31点语义UNKNOWN、非WD01真人连续性UNKNOWN与严格共同门FAIL，不能仅把整单叫“缺GT”；即使补GT也不能绕过gate。W03保留，W04–W09/registration R3.9 production未启动。

## 2. 31 个点是什么

30 workspace crop + 1 reference match；语义UNKNOWN31，无人工已验 ground/脚/腿标签。29点在P输出候选track1，2点原已被P cleanup移除。7帧 f63/65/85/90/99/123/146、7个frame-cluster、1个candidate track；z<0.3=31，0.3–0.6=0，>0.6=0。逐点31行见02/01，截图/点云外观不代替GT。

## 3. Confirmation 为什么变化

new green61：gain39/history20/topology2；new purple70：gain58/history1/topology11；disappeared126：WD01静态期望102/reference8/history6/candidate-loss6/topology4。净green -65（132→67），净purple -67（152→85），event-loss0。不能称FP/FN。

既清掉静态家具，也改变非WD01候选的点成员、几何门、拓扑和时序；非静态155行的真实人/物/混合与真人track连续性仍UNKNOWN。P/S overlap split10/merge2，不等同真人fragmentation GT。cleanup自身split/merge0；计数delta减少并非分裂，严格delta==0仍FAIL。

现行归因文件为 `03_confirmation_attribution_r2.json`，首次03保留为superseded；r2修正过度归因cleanup和时序票解释。所有257行带frame/track/形心/点数/高宽深半径/upcos/证据/标签/删除机制/历史与原因。

## 4. Registration gate

冻结 ratio=5938/11959=49.652981%<50%；9897raw×60%trim→5938keep，差42keep/70raw。1684缺球门对应、378normal不足，reference覆盖与空间分布不均匀可测；动态/遮挡/FOV/量化具体因果仍UNKNOWN。接近门不证明无害边界，未放宽/调参/换解。

历史绑定sandbox loader DEGRADED；统计修复后当前loader STALE（METHOD_STALE/REFMAP_DRIFT），全帧SAFE=P已验证。未修改旧artifact；原R/t和输入不变。身份和源码SHA见09_input_source_sha/06.registration。

## 5. 修复内容

生产唯一修改 `pc_apps/human_replay/human_pipe_lib.js` 三个表达式：delta 用数组length相减，before/after显示字段返回length。BUG-R39-M01先复现/登记，随后修改；diff=`05_metric_fix.diff`。PIPE/cleanup/聚类/分类/Tracker/Fall/registration/leveling算法不改。新工具全部在本轮evidence目录：逐点/归因/shadow/gate/统计回归、复用Three.js/OrbitControls的viewer、GT校验、记录/SHA工具。

所有165帧P/S **非诊断字段逐位相同**（对R38）；cleanup点云及人形/track/events没有因统计修复改变。诊断数值有限，fg与candidate分区守恒通过。P/S behavior digest分别 `959a9ecd872da37aaa49844ee90df5528ff5ecf979229d48d84040031abb619f` / `cf5e1b618ccda55fceb32fc47d6aaac20c66cd9d7b0cfd10e67e6cbb4d75e8fb`。完整JSON digest随诊断schema正常变化，不把变化隐藏。

旧R3.6原代码sandbox完整digest复现 `23830edefcb28f04774e328af64abce014dfeff35df75462f8a6f68d68eb3357`；当前源码执行原script的19项/全部algorithm-result projection、CSV SHA均相等。其完整digest变成 `5da7a60d3e23b1b718194d21049246a7820ded62468018604e5171ca1000cb8c`，因为包括PL SHA；这不是逐点算法漂移，且没改写旧结果。

## 6. 回归及验收

| 检查 | 状态 | 实际exit | 真实记录 |
|---|---|---:|---|
| 新 metric/attribution 单测 | PASS | 0 | `05_metrics.stdout.log` / `.stderr.log` / `.run.json` |
| 新增 attribution r2 回归 | PASS | 0 | `05_attribution.stdout.log` / `.stderr.log` / `.run.json` |
| human_pipe_lib.test.js | PASS | 0 | `05_pipe.stdout.log` / `.stderr.log` / `.run.json` |
| human_replay_lib.test.js | PASS | 0 | `05_replay.stdout.log` / `.stderr.log` / `.run.json` |
| registration artifact/load 单元回归 | PASS | 0 | `05_registration.stdout.log` / `.stderr.log` / `.run.json` |
| 原R3.6 equivalence/digest 回归 | PASS | 0 | `05_r36.stdout.log` / `.stderr.log` / `.run.json` |
| 故障/当前STALE全帧SAFE回归 | PASS | 0 | `06_faults.stdout.log` / `.stderr.log` / `.run.json` |
| gate固定解诊断 | PASS | 0 | `07_gate.stdout.log` / `.stderr.log` / `.run.json` |
| 完整165帧shadow + 第二跑 | FAIL | 1 | `06_shadow_after.stdout.log` / `.stderr.log` / `.run.json` |

完整shadow的exit1是预注册T38-05/06失败，不是运行崩溃。新 metric5项、r2 attribution5项、旧pipe35项、replay45项通过；registration逐ID见下，不以单测数宣布收口。

唯一验收表：R3.7 `06_test_matrix.md` v1，SHA `70c82e401d0e4055ad85e1bef847d82dd32e718d682533ff25f22a24ac1f9b18`。所有状态是本机作者自验。

| ID | 状态 | 当前证据 |
|---|---|---|
| T37-01 | PASS | 05_registration.stdout.log |
| T37-02 | PASS | 05_registration.stdout.log |
| T37-03 | PASS | 05_registration.stdout.log |
| T37-04 | PASS | 05_registration.stdout.log |
| T37-05 | PASS | 05_registration.stdout.log |
| T37-05b | PASS | 05_registration.stdout.log |
| T37-06 | PASS | 05_registration.stdout.log |
| T37-07 | PASS | 05_registration.stdout.log |
| T37-08 | PASS | 05_registration.stdout.log |
| T37-09 | PASS | 05_registration.stdout.log |
| T37-10 | PASS | 05_registration.stdout.log |
| T37-11 | PASS | 05_registration.stdout.log |
| T37-12 | PASS | 05_registration.stdout.log |
| T37-13 | PASS | 05_registration.stdout.log |
| T37-14 | PASS | 05_registration.stdout.log |
| T37-15 | PASS | 05_registration.stdout.log |
| T37-16 | PASS | 05_registration.stdout.log |
| T37-17 | PASS | 05_registration.stdout.log |
| T37-18 | PASS | 05_registration.stdout.log |
| T37-19 | PASS | 05_registration.stdout.log |
| T37-21 | PASS | 05_registration.stdout.log |
| T37-20 | PASS | 06_shadow_results.json |
| T38-02 | PASS | 06_shadow_results.json |
| T38-03 | PASS | 06_shadow_results.json |
| T38-04 | PASS | 06_shadow_results.json |
| T38-05 | FAIL | 06_shadow_results.json |
| T38-06 | FAIL | 06_shadow_results.json |
| T38-11 | PASS | 06_shadow_results.json |
| T38-12 | PASS | 06_shadow_results.json |
| T38-07 | PASS | 06_fault_regression.json |
| T38-08 | PASS | 06_fault_regression.json |
| T38-09 | PASS | 06_fault_regression.json |
| T38-10 | PASS | 06_fault_regression.json |
| CURRENT_ARTIFACT_STALE_SAFE | PASS | 06_fault_regression.json |
| T38-01 | PASS | 05_r36_equivalence.json |
| T39-01–08 | NOT_RUN | registration生产未授权 |
| HP02 真人弯腰 | BLOCKED | 缺真人数据，合成不替代 |
| 设备/物理/部署/采集 | NOT_RUN | 本轮未授权 |
| W04–W09 | NOT_RUN | 本轮明确禁止 |

S1/2/3/5/6 PASS，S4/7 FAIL。T38-06可有限信赖，但值并非全0，且new confirmation门未过；不把修复NaN冒称共同门PASS。

## 7. 当前人体识别能力

已验证：冻结pair/165帧本机离线背景残留 WD01 93423→1754（98.1225%），WD02 159247→24508（84.6101%）；artifact绑定失效安全回退；统计修复输出等价/确定性与机械删除归因。

尚未验证：31点实际语义、155个非静态变化行真人身份和连续性、HP02真人弯腰、正式20–60s空场及跨距离/多人/遮挡、设备实时/物理外参、实际姿态/骨架/跌倒性能。

不能声称：人体识别准确率/Precision/Recall/F1、真人无损/无系统性track破坏、姿态精度、跌倒误报率/检测延迟。98.1%/84.6%仅是指定背景窗口残留改善。

## 8. 是否可以进入 W04

**不可以。** gate未过；31点语义可能包含脚腿；非WD01拓扑/候选损失的真人GT尚未闭合；原共同门FAIL。下一步仅人工GT与既定gate支撑/契约设计审查，不能顺手调matcher或继续骨架。

## 人工如何闭合 GT

打开 `09_point_review.html`（153帧分文件加载；原坐标未抽稀/舍入）；初始UNKNOWN，分别看P、S和损失点，查看逐行JSON。优先标31点的7帧、24个非WD01消失行、10split/2merge帧；其余非静态155行的完整帧清单见04。需标签：FOOT_SHOE/LOWER_LEG/GROUND_RESIDUE/HUMAN_GROUND_MIXED/REGISTRATION_REFERENCE_MISMATCH/UNKNOWN，以及cluster PERSON/STATIC_OBJECT/MIXED/UNKNOWN、连续性PRESERVED/FRAGMENTED/LOST/STATIC_NOT_HUMAN/UNKNOWN。导出必须填写标注人，写派生文件；不写原session。source="human"只有人工导出的标签，不把当前诊断改成human。

完成后先运行（输出必须新文件）：

```powershell
node docs/human_capture/evidence/2026-10-07_hrw03_r39_closeout/review_gt.js <人工导出.json> <新的GT复核结果.json>
```

GT脚本校验点id、frame/seq/track、来源SHA与leveling/artifact绑定；GT不能自行放行gate。需要再次跑全链时建立新evidence轮，将工具和baseline_code复制到新轮，`closeout_shadow.js --phase=after` 重新复现；当前固定结果均独占写入（wx），不能覆盖本轮。真实GT完成前不继续调算法。

## 证据与纪律

00_baseline含5466个原文件（含untracked/ignored可读输入及symlink身份）、branch/HEAD/dirty状态；收尾09_scope_check报告授权三行和文档增量。各run.json保存运行参数、真实exit与stdout/stderr；输入/sourceSHA见09_input_source_sha。历史结果、首次失败、原始captures均保留。未commit/push/reset/checkout/clean/部署/采集。ponytail实读 `C:/Users/30680/.codex/skills/ponytail/SKILL.md`，full。仅writer自验，独立复审NOT_RUN。



### 收尾补记（只追加，保留原提交正文）

`09_final_integrity.json/md`：受保护原文件264项SHA一致、PL精确三行改动；另观测到范围外28个原文件变化/消失及9个新增，包含其他会话和Console/HC文件，均保留，不能声称全仓未变。本实验绑定输入与历史证据不受影响。GT格式回归6项PASS但仅synthetic，真人GT仍BLOCKED。


### GT 后复跑路径补充

新 evidence 目录必须与本目录同处 docs/human_capture/evidence/ 下。除工具与 baseline_code 外，还需复制本轮不可变对账锚点 01_absorbed_points.json、03_confirmation_attribution.json、03_confirmation_attribution_r2.json；不要复制旧06输出，再在新目录运行 closeout_shadow.js --phase=after 生成新的06_shadow_results.json，并用 run_record.py 新前缀保留日志。review_gt.js 另读人工文件写独占新结果，原shadow门保持。人体GT和物理验收仍未完成。
