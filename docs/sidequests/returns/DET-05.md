## DET-05 R1 — 2026-10-08 / OpenCode / SUBMITTED

- 唯一验收：docs/sidequests/DET05_ACCEPTANCE.md v1，提交SHA `462c91519c18d4242a467bcb92146550faa8e810df608f746e65816d51c2b537`；先行计划/当前baseline→实现→实验；用户 2026-10-08 会话授权 (a) 轮并确认"writer 初标 + 用户确认后冻结"。
- 唯一writer OpenCode（opencode-go/deepseek-v4.1-flash）；ponytail full 经 opencode skill 工具实际加载（id=ponytail；base dir `C:/Users/30680/.config/opencode/skills/ponytail`，SKILL.md 已核对）；分支 codex/human-detector-models，起始/结束HEAD cfbb80c57508be1a0435fdb92260f698dc763934；主树只读，无部署/采集/训练/提交/推送。
- 标注：10 帧（4 固定代表帧 + 215643 负帧 3/7/11/12/17/28/37）；scope 32205 点中 human 13466 / furniture 17913 / mixed_uncertain 826；每点绑定 prepared 行与 raw 采集行（`.ids`/`.rows` 链断言）；用户确认原文"全部确认，冻结 gt_v1"（无修正）；gt_v1=行列表/质心/顶高/AABB 冻结，冻结后未改。
- 纯度：严格"柱内全部有效点均 human"规则；每条目纯柱 1–6 根、可切换（>32 点）0–2 根；主要排除=scope 外未标点（未标不默认背景的保守规则）。
- 主结果（仅纯柱 first32→z_rank32，其余逐值冻结，20 新前向）：215540/32 GT 位置分 0.0557→0.1472、GT 匹配 anchor 全库排名 148→7、首次出现含 GT 终框（IoU 0.490）、边距 −0.1449→−0.0117（竞争位 1.49m/0.1589）；215623/33 0.3031→0.3190（排名 24→17）；215643/28 −0.0026；负帧 E 组 Δlocal −0.0113…0 或不可切换；607/33、643/3、643/37 无可切换纯柱、两输入完全相同。
- 验证：12 回归测试 `python -B -W error` exit0；10 独立检查 exit0（base 与 DET-03 存档 seed 三值逐位一致 exact=true）；switch 隔离逐柱复核；20 前向=预算；3211 资产及既有忽略文件清单见 18。
- E03/G01 BLOCKED 继承；L01/D01 NOT_RUN；单帧同人同场景、描述性，不报 P/R；执行 PASS ≠ 识别可用；未自行 ACCEPTED。
### 逐ID自验

|ID|作者自验|证据|
|---|---|---|
|S01|PASS|00 baseline（两树+3211资产全匹配）/ plan / acceptance / 18 integrity|
|A01|PASS|03 annotation proposal + 渲染 + prepared/raw 双链绑定 / 10 independent checks|
|A02|PASS|03b 用户确认原文 / 03c freeze / labels_v1 + gt_v1|
|B01|PASS|04 purity audit（纯柱1-6/条；可切换0-2）/ 10 checks 独立复算|
|C01|PASS|05 run rows / switch isolation（非纯柱逐值相等）/ 20 forwards|
|M01|PASS|06 metrics（GT三口径/anchor排名/0.8m竞争位与边距/框包含与IoU）/ seed三值 exact|
|T01|PASS|08 regression: 12 tests -B -W error exit0|
|R01|PASS|17 diff/快照/manifest/索引; 18 integrity; 编号日志含失败|
|R02|PASS|return append / 顶层README / 完整报告 / options|
|E03|BLOCKED|DET-03 资源限制继承；native ATen 未运行|
|G01|BLOCKED|仅CPU；无GPU轮授权|
|L01|NOT_RUN|物理/辐射标定与独立人/场景泛化未做|
|D01|NOT_RUN|无设备/网络/驱动/部署/采集/生产动作|

- 下一步需新授权：(b) 已标定强度/z 与同传感器权重适配轮；(c) GPU/原生 ATen 等价轮；（帧集/规则/IoU 口径的任何变化需重新预注册）。
- 复审入口：[完整报告](../evidence/2026-10-08_det05_r1/README.md)，[唯一验收v1](../DET05_ACCEPTANCE.md)，编号日志 / 17 diff+manifest+index / 18 完整性 / 22 范围。


## 最终完整性实录

18复核：原3211消费资产变化清单为空；已有 5809 个基线忽略文件（含 DET-03/04 大数组/上游/旧资产）全部SHA不变。实验树 10720 基线项中既有文件变化仅 [('sidequests/human_detectors/README.md', '4188b7b9->5df5ca6b'), ('sidequests/human_detectors/test_experiment.py', '5f68012d->d94a2e54')]，本轮新文件 95 项见22清单。主树 6053 基线项变化清单为空（本轮未写主树）。两树branch/HEAD均保持基线。

17记录：02预运行副本/代码前后快照与diff/17 manifest/逐文件SHA索引；03标注首跑相对路径bug失败保留（03_annotation_dev_fail.log），修复后重跑通过；08回归、09实验（20前向）、10独立检查、18完整性均 exit0。
