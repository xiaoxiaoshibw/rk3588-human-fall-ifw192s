# HUMAN-FUSION-DEMO-V2 回传

## 2026-10-11 r1 / Codex唯一writer

- 状态SUBMITTED；逐条作者自验，未ACCEPTED。软件PASS条目V01–V05/T01/A01/E01/K01/K02；G01/P01 BLOCKED；S01 BLOCKED（外部既有结果漂移）；D01 NOT_RUN且明确禁止。
- 当前唯一表：[HUMAN_FUSION_DEMO_V2_ACCEPTANCE.md](../HUMAN_FUSION_DEMO_V2_ACCEPTANCE.md) v1；SHA 6ae60756d0427b34799558bdb3ce36570770578b0540a6d388c9abcaac7704af。
- 起始branch/HEAD：master / 026e06303f60ed1bbe4ddc4d037836db68da6d27；9452文件含untracked基线BASELINE.json；所有用户原差异保留，不reset/checkout/clean/commit/push。
- ponytail SKILL.md实际读取路径：C:/Users/30680/.codex/skills/ponytail/SKILL.md。
- 单writer仅V2新文件与当前文档；复用V1而不改其源和模型。不dispatch agent，不部署、采集、生产切换或激活ML。

## 集中诊断与实际变更

| ID | 根因与修复 | 入口/状态覆盖 |
|---|---|---|
| T01 | FusionTracker没有同帧占用，导致21次共享ID及多票；V2 Runtime复用UniqueTracker | 每model/begin/segment回退重建与reset；18全帧运行0重复 |
| V03 | V1切模型会改变候选，不是同候选比较；V2从同raw完整候选重提51/69特征 | UI四分数/18运行的同候选列；实际classifier仍单当前管线 |
| V05/G01 | S9 placeholder SHA、缺meta绑定；Runtime拒绝不可信GT，新草稿带双SHA | 缺/错/稀疏GT UNKNOWN；可信S9仍BLOCKED |
| A01 | V1无本页标注；派生V2添加投影矩形与3D框、下载/导入/撤销 | raw28B行、同帧track唯一/索引界限/源点/坐标/SHA校验；草稿不改旧GT |
| K01/K02 | 既有骨架原型不等于已实现可靠人体关节 | 只显示有支撑三表面轴，完整关节/肢体/姿态UNKNOWN，UNCALIBRATED |

实际新文件：v2_runtime.js / server_v2.js / demo_v2.html / start_demo_v2.cmd / annotation_v2.js，以及派生、验证、收口工具。全部最终SHA见DELIVERY_SHA256.json；全帧运行采用的Runtime前诊断版本已从唯一后续差异还原保存FULL_REPLAY_RUNTIME_PRE_DIAGNOSTICS.js（只追加layer_observations，不改变检测跟踪）。新文档只在README顶部追加入口、独立验收表/回传/新证据目录。

## 逐条验收与证据

| ID | 实际验证 | 结果 |
|---|---|---|
| V01/V02 | BROWSER_CHECK_03.json九会话切换、三视图、帧条/暂停/重置及分层；真实截图 | PASS |
| V03 | validate_v2.js十八运行的same_candidate指标；浏览器四分数 | PASS |
| V04 | 35代表帧CASES/CASE_DETAILS；成功/漏检/家具截图及九会话截图 | PASS |
| V05 | 当前GT SHA与会话绑定；S9错误源显示UNKNOWN；未知不算负例 | PASS |
| T01 | 5210tick全帧、每帧一票/失配/寿命及回退reset确定性；collect追加诊断后重验 | PASS |
| G01 | 源及各备份都错绑定，无可靠来源；新绑定草稿工具已交付，历史GT不冒修复 | BLOCKED |
| A01 | 浏览器保存/撤销实际索引草稿；annotation_v2 --test绑定/边界/重叠校验 | PASS |
| E01 | 十八运行的跨会话表、UNKNOWN和训练/历史留出分列；独立家具/人员资格保持未知 | PASS（评估交付，非泛化合格） |
| K01 | 原limb/HR-SKELETON代码与真实资格审查，15项旧数学测试-W error | PASS（状态核查） |
| K02 | OBSERVABILITY实际候选点支撑及代理输出，缺解剖标签明确UNKNOWN/UNCALIBRATED | PASS（代理诊断，非关节精度） |
| S01 | FREEZE_CHECK与FREEZE_FINAL，4既有结果外部变化，不回写；无本轮生产修改 | BLOCKED |
| D01/P01 | 未部署/生产/采集；用户效果与物理确认不能由作者代替 | NOT_RUN / BLOCKED |

## 未闭合与复审入口

[完整实际报告](../evidence/2026-10-11_human_fusion_demo_v2_r1/REPORT.md)包含启动地址、真实例、模型对比、骨架分层与明确后续任务。第一批browser检查因CASES尚未生成失败，原日志保留；03轮通过。初次全帧检查在冻结断言失败，十八已完成结果保存并新collect归档，不改失败记录。不将自验冒称独立复审；若后续复审，以上现行表/源码SHA/完整日志为入口。

当前下一步为S9真实人工重标、独立家具验证及S6背景/清理/提案分层改善；解剖可见性/节点GT及可靠物理标定待补。保持用户未确认离线检测、骨架、姿态效果前禁止板端部署、生产替换、现场发布。

## 本轮最终冻结补充

最终9451文件核对发现5项外部变化：先前4个结果及V1 server.js（V2不导入该文件）。此前4项为较早检查记录，保留不回填。S01保持BLOCKED；当前验收表SHA 1605db6a24ab47adfc2812edb64f6754a973a09b89fba44a795dc4f12ce89964。最终报告入口：[REPORT_FINAL.md](../evidence/2026-10-11_human_fusion_demo_v2_r1/REPORT_FINAL.md)。其余逐ID软件自验与D01/P01/G01边界不变。
