# HFUS-TCMS-02-REALDEV-02-S06

## R1 开发登记 / 2026-10-18

用户授权开发后OpenCode审核。唯一writer Codex；策略RESEARCH+ENGINEERING，科学验证与证据保留优先。实际技能路径：C:/Users/30680/.codex/skills/ponytail/SKILL.md；C:/Users/30680/.codex/skills/scientific-toolkit-skill/SKILL.md。唯一验收：../evidence/2026-10-18_hfus_tcms_02_s06_r1/ACCEPTANCE_V1.md；状态进行中，各项NOT_RUN。收尾追加结果与命令/源码SHA。WORKFLOW写入当前OS错误，旧字节未变；授权由本轮用户指令与当前顶部计划确定。

## 实施提交、OpenCode审核与R2文档勘误 / 2026-10-18

状态SUBMITTED（04 FAIL、06 BLOCKED），非ACCEPTED。唯一当前验收：evidence/2026-10-18_hfus_tcms_02_s06_r1/ACCEPTANCE_V2.md；最终逐ID：evidence/2026-10-18_hfus_tcms_02_s06_r2/FINAL_RESULTS.json。V2只纠正尾段事实前提，A数值门未变。原R1登记的V1/NOT_RUN是历史，r1 AUTHOR_RESULTS/REPORT的08/09也是scope/审核完成前快照；r1 AUTHOR_SUBMISSION已将08记为PASS。

- 起始branch/HEAD：master / c9c4ee421cb0c8a3e4590b8f5730828b093c759a；原树dirty。34660路径SHA基线（tracked+非忽略untracked），34716路径首尾核验无范围外差异，HEAD不变；ignored源双SHA另核。原用户差异保留，未Git写、未写data或junction。
- 唯一writer Codex；项目策略RESEARCH+ENGINEERING。实际技能 C:/Users/30680/.codex/skills/ponytail/SKILL.md 与 C:/Users/30680/.codex/skills/scientific-toolkit-skill/SKILL.md。
- 集中根因：背景吸收→r10唯一match覆盖；新增前景伴随轨迹67→162、歧义帧220→311、标定10→0，不能当效果改善；继承association最终matches未过滤candidate歧义，wire仍测量，原模块保持冻结；D原分类谓词无区分力，保持BLOCKED，不伪造静止人体结论。

| ID | 作者最终状态 | 证据/限制 |
|---|---|---|
|S06-01|PASS|INPUT_CHECK.json / BASELINE_ALL.json：源双SHA、六封存、13复用源/参数；branch/HEAD与全非忽略工作树SHA|
|S06-02|PASS|UNIT_R2.log 4 tests；近地包络strict边界/nearest/无资格/invalid/tau/AABB；r01 DEFAULTS零改动|
|S06-03|PASS|A_GATE.json：97空场+35尾段；+0.731/+0.738pp；32/35；main 132帧ledger精确一致|
|S06-04|FAIL|780帧执行与行守恒PASS；继承节点/标定门FAIL，且57/71次歧义候选仍测量；不采用变体|
|S06-05|PASS|163=74 node_jump+89 other；姿态原因UNKNOWN；两未标定边逐帧支撑+实际失败谓词；无修法|
|S06-06|BLOCKED|780字段/107帧计数重建PASS；107均可观测bg吸收但不能因果划分近地人体/人体静止，UNKNOWN；不冒称静止结论|
|S06-07|PASS|STD_RECONCILIATION / FINAL_HANDOFF_ALL / DELIVERY_INDEX_V2；五历史Codex正式复审NOT_RUN|
|S06-08|PASS|SCOPE_CHECK：34716路径核SHA，旧资产/输入/冻结源未变，HEAD unchanged；A/B/C/D资源在门内；ENVIRONMENT/UNIT/S3/SYNTHETIC日志。|
|S06-09|PASS|OpenCode readonly review actual specified model, exit0/436.217s/101 read tools, source SHA unchanged; independent execution NOT_RUN; final records here and return/REVIEW_LOG.|

实际命令均在repo root，以 python -B -W error 运行：r10/s06.py inputs/gate/candidates/calibration/skeleton 对应成功exit0；r10 unittest4/exit0；r04/tests unittest13/exit0；r08/synthetic.py（新输出）4/4场景、47/47within、46/47cal/exit0；r10/verify_delivery.py首轮assert exit1发现继承缺陷，R2执行exit0但语义PASS=false；measure与package scope/seal exit0。完整命令、源码SHA和原始日志见r1 IMPLEMENTATION_NOTES、SCOPE_CHECK与各log。失败保留，不改门。

A24.774s、B119.403s、诊断重测11.739s，主运行峰值1230196736B，r1封存68.6MB；预算未超；Python3.8语法检查通过。r1 seal 8f5c7870d7365b64617b3938cec51e1f302c7b0007a03b150abb83418ddbaa9b；r2仅文档补录另封存。未预测/display填无候选帧；原始节点/边/ledger逐帧核对，歧义候选契约仍FAIL。

OpenCode：probe9.599s/exit0、审核436.217s/exit0/stop，actual opencode-go/deepseek-v4.1-flash，session ses_eb325db04ffen6faiD1w6L8kpf；仅101次read/glob/grep，四源码SHA首尾一致。审核原文 evidence/2026-10-18_hfus_tcms_02_s06_review_r1/OPENCODE_REVIEW.md；独立执行NOT_RUN。r2补录由Codex核验，OpenCode未复审补录，不能伪称其批准算法或正式Codex复验。

交接入口 evidence/2026-10-18_hfus_tcms_02_s06_r2/FINAL_HANDOFF_ALL.md。变体不采用；关联修复/D新协议/S07未实施，五历史项Codex正式复审NOT_RUN；解剖/左右/物理高度/人体身份/效果/独立D UNKNOWN/BLOCKED，设备/部署/采集/训练/网络NOT_RUN。

提交源码SHA（均与审核前一致；本轮只新增r10，旧r08/r01/src/config SHA不变）：

- sidequests/hfus_tcms_02/realdev/r10/package.py: 4cd95815e736502b29ef96732f81161b26e0ea3ffd2848f6497edb70c2732557
- sidequests/hfus_tcms_02/realdev/r10/s06.py: 554ba8312b5269c6a82bdf966eeaa3f988fecb679e228d59dfd54ca6baf94d7f
- sidequests/hfus_tcms_02/realdev/r10/test_s06.py: 684613a1a83ffc838601c0b31edb8b15ad2bda6bbb7f4e73151b433116528384
- sidequests/hfus_tcms_02/realdev/r10/verify_delivery.py: 53084e123005271ac1cb0d5d0f52d370e9d3b71ba5c841266227ae9d3f2c9ad9
