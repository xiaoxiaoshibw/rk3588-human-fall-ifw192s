

## DET-04 R1 — 2026-10-08 / Codex / SUBMITTED

- 唯一验收：docs/sidequests/DET04_ACCEPTANCE.md v1，提交SHA `7bb4d920ce041031875126659cf47f71e8d079866f1a131064873cfc20db75b5`；先行计划/当前baseline→实现→实验。
- 唯一writer Codex；实际本机Python3.12.10/PyTorch2.12.0+cpu，原固定PointPillars checkpoint；分支codex/human-detector-models，起始/结束HEAD cfbb80c57508be1a0435fdb92260f698dc763934；主树只读，无部署/采集/标注/提交/推送。
- ponytail full 实际读取路径：`C:/Users/30680/.codex/skills/ponytail/SKILL.md`。无独立skill API，按文件加载规则读取；未委派writer。

### 集中诊断与根因边界

只保留B同扫描圆柱相交柱，前三组local 0.056/0.233/0.303→0.348/0.483/0.476，第四0.356→0.133；加回固定[-0.15,0.30]m全部点整柱，前三下降0.167/0.245/0.171。冻结柱完整tensor/counts/源ID、retained encoder canvas逐值一致、deleted scatter为零。零counts直接进入上游encoder会除零；本实现保留完整审计零counts表，前向只发送非零柱，未改上游或权重。

既有context_cloud输出逐值为B点按C/E源ID删选，16输入/ID SHA重现；没有外来点值注入，故不能用本轮高分归因外来XYZI。外围结构与地面上下文有因果支持，统一主因仍未定。506对描述相关不作显著性；7负帧上带均增加、具体local anchor下降；empty17/35/53均同anchor158179约0.50–0.51，footprint高度覆盖提升也提高无人响应，不报误报率/P/R或识别可用。

### 实际变更

新 sidequests/human_detectors/det04.py；test_experiment.py新增冻结/删除/地面边界与感受野回归；README顶部同步。DET04计划/验收表、本轮新证据与新忽略artifacts/回传；DET-03未提交文件已纳入baseline，历史证据未回填。代码diff/源码SHA见17，完整消费资产变化及工作树变化见18/22。

### 逐ID自验

|ID|作者自验|证据|
|---|---|---|
|S01|PASS|00 baseline / plan / acceptance / 18 integrity|
|A01|PASS|01 audit / 06 deletion / 10 independent tensor-ID checks|
|A02|PASS|06 comparisons / 07 attribution / full metric table|
|B01|PASS|03 dose rows/CSV/summary; 506 pairs; 0 forwards|
|C01|PASS|04 negative anatomy; 7 frames; complete local anchors; 0 forwards|
|F01|PASS|05 FP anatomy; 7 anchors/support NPZ; 0 forwards|
|T01|PASS|08 regression: 10 tests -B -W error exit0; 09 experiment exit0|
|R01|PASS|17 index / code diff / manifest; 18 integrity; numbered logs|
|R02|PASS|return append / top README / this report / options|
|E03|BLOCKED|DET-03 resource limitation inherited; native ATen not run|
|G01|BLOCKED|10: torch2.12.0+cpu CUDA false; no GPU round authorized|
|L01|NOT_RUN|No labels/physical calibration executed|
|D01|NOT_RUN|No device/network/driver/deploy/capture/production actions|

### 验证、消费资产与未闭合

python -B -W error现有test_experiment.py 10tests exit0；唯一实验09 exit0，8新网络前向；H-B/C/D与独立复核0新网络前向。00b读schema失败保留，不是实验失败。原3211消费资产和DET-03忽略产物按当前baseline复核，差异清单见18；本轮新增消费既有DET-03 rows/config/trace/pillars和本轮代码/计划/config，绑定00/17，未改源会话/上游/权重/变换。

E03/G01仍BLOCKED；L01/D01 NOT_RUN；人体/家具GT、物理标定与泛化未闭合。执行PASS不等于识别可用，未自行ACCEPTED。

下一步三选一均需用户另行明确授权：优先(a)人体点GT后外围固定、纯人体柱覆盖，指标含GT人位/最近竞争位边距与GT相对排名；(b)已标定强度/z与同传感器权重适配；(c)GPU/原生ATen等价。完整(a)设计草案见报告，本轮未执行标注。

复审入口：[完整报告](../evidence/2026-10-08_det04_r1/README.md)，[唯一验收v1](../DET04_ACCEPTANCE.md)，编号日志/17diff+SHA/18完整性/22范围。当前状态SUBMITTED，等待独立复审或用户选下一轮。


## 最终完整性实录

18复核：原3211消费资产变化清单为空；已有5776忽略文件（含DET-03大数组/上游/旧资产）全部SHA不变。实验树10606基线项仅README/test_experiment.py两文件变化，本轮新文件见22清单。主树5190基线项观察到两份外部文档变化：docs/human_capture/FUSION_PRIORITY_RULE_DRAFT.md、docs/human_capture/HUMAN_RECOGNITION_REVIEW_AND_PLAN.md；本轮全部写入路径均在指定worktree，未写或回滚这两份文档，不能声称原树字节全未变。两树branch/HEAD均保持基线。

17首次打包因Windows默认gbk读取中文验收表而UnicodeDecodeError，exit1日志保留在17_packaging.log。17b显式UTF-8修复打包后通过，未重跑任何网络前向。config记录的是预运行验收SHA；02_acceptance_prerun.md验证该SHA并保留，最终追加自验的验收SHA另见17/22。
