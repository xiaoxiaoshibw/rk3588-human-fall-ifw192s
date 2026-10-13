

## 2026-10-08 HR-SEM-SHADOW 独立复审 r1（Codex，PC离线）

### 本轮信息

- 用户直接授权独立PC离线复审；单审核者，无子代理/OpenCode/实施CLI；实际模型标识未核实不填。
- 唯一表 `docs/human_capture/HR_SEM_SHADOW_ACCEPTANCE.md` v1，SHA `3b5b83da5a83c460bc7590011034647f77272be70d1f92f7c2ddb9c0bd8498dd`；工单SHA `f9e9e4f705c2ed571d495f7164341bead7e768106eb48458ce40f474f4e819d6`。
- **独立结论 REWORK_REQUIRED：本单离线证据与设计交付暂不接受，生产接入不具备资格。** SEM-12从执行者PASS明确改判FAIL；其余逐项见下表。原执行记录保留，不重写历史。
- 起始 master / `cfbb80c57508be1a0435fdb92260f698dc763934`；完整本轮基线6056实际文件43,280,721,488字节，dirty及用户原差异保留。r1起始5908记录、143产物、12工具源码及实际digest重新核对，零漂移。
- ponytail实际实读路径：`C:/Users/30680/.codex/skills/ponytail/SKILL.md`（full）。stdlib、已安装NumPy和只读纯函数；无新依赖，无生产修复。
- 审核报告：[REVIEW.md](../evidence/2026-10-08_hrsemshadow_review_r1/REVIEW.md)；全部工具/日志/结果只在 `evidence/2026-10-08_hrsemshadow_review_r1/`；实际命令/exit：[commands.md](../evidence/2026-10-08_hrsemshadow_review_r1/commands.md)。

### 集中诊断与根因覆盖

| 类别/ID | 根因与实际影响 | 最小返工要求与边界 |
|---|---|---|
| 实现错误 / SEM-12 | 全帧查看入口不绑定所选clusters.jsonl及行成员。1029点真实簇换成row0，仍复制原member SHA并显示源SHA通过；原GT格式validator接受该合成内存记录。 | 新轮绑定index digest、重算成员SHA、校frame/seq/rows并阻断篡改，补正常载入/拒绝检查。本轮只复现，不修代码，不造真人GT。 |
| 工具契约 / SEM-10 | WD02源与全部派生产物SHA完整；只有历史leveling.py与当前生成代码不同。shadow.level额外要求二者相等，现有levelingBinding契约没有该条件。 | 更正“输入漂移”归因，区分生成provenance与当前消费者绑定，后续澄清协议。WD02本轮仍未运行，不换job、不重签、不放行。 |
| 目标不足 / SEM-05、08 | 完整簇HUMAN帧上界13/244、1/195；ROI抽样成功不能外推整簇。 | 保留数值目标不足与GT阻断两层事实；后续独立校准/版本设计，不调当前阈值或95%分母。 |
| GT/覆盖 / SEM-05～08、10 | 真人全帧簇/连续person_id、185+5边缘点、WD01区域HUMAN身份未闭合；箱子UNKNOWN、low_bar全空、格栅未覆盖、WD02未跑。 | 人工可追溯标签与实际非空覆盖；机器ID/ROI不作GT，空输入不计负例通过。 |
| 既有风险 / SEM-04、11 | 无效点污染原图/拓扑；原Tracker同帧复用及观测票不老化。 | 保留审计对照；I01/T01/T02需另授权，本轮不改生产Tracker/Fall。 |
| 工具限制 / SEM-12 | r1实际浏览器UI环回超时/file策略阻断，headless不能替代。 | 保留BLOCKED，不能绕过浏览器安全策略；与索引绑定实现错误分开。 |

### 实际变更与独立验收

仅新增本复审目录和本return末尾段；详细文件SHA/用途见本轮 `changes.json`。旧生产源码、冻结参数、captures、旧evidence和原return前缀完整性见本轮 `integrity.json`。没有commit/push/reset/checkout/clean、签装artifact、生产旗标、板端连接、部署采集、ML或后续工单。

| ID | 独立状态 | 依据 |
|---|---|---|
| SEM-01 | PASS | [独立依据与定位](../evidence/2026-10-08_hrsemshadow_review_r1/REVIEW.md) |
| SEM-02 | PASS | [独立依据与定位](../evidence/2026-10-08_hrsemshadow_review_r1/REVIEW.md) |
| SEM-03 | PASS | [独立依据与定位](../evidence/2026-10-08_hrsemshadow_review_r1/REVIEW.md) |
| SEM-04 | PASS | [独立依据与定位](../evidence/2026-10-08_hrsemshadow_review_r1/REVIEW.md) |
| SEM-05 | BLOCKED | [独立依据与定位](../evidence/2026-10-08_hrsemshadow_review_r1/REVIEW.md) |
| SEM-06 | BLOCKED | [独立依据与定位](../evidence/2026-10-08_hrsemshadow_review_r1/REVIEW.md) |
| SEM-07 | BLOCKED | [独立依据与定位](../evidence/2026-10-08_hrsemshadow_review_r1/REVIEW.md) |
| SEM-08 | BLOCKED | [独立依据与定位](../evidence/2026-10-08_hrsemshadow_review_r1/REVIEW.md) |
| SEM-09 | PASS | [独立依据与定位](../evidence/2026-10-08_hrsemshadow_review_r1/REVIEW.md) |
| SEM-10 | BLOCKED | [独立依据与定位](../evidence/2026-10-08_hrsemshadow_review_r1/REVIEW.md) |
| SEM-11 | PASS | [独立依据与定位](../evidence/2026-10-08_hrsemshadow_review_r1/REVIEW.md) |
| SEM-12 | FAIL | [独立依据与定位](../evidence/2026-10-08_hrsemshadow_review_r1/REVIEW.md) |
| SEM-13 | PASS | [独立依据与定位](../evidence/2026-10-08_hrsemshadow_review_r1/REVIEW.md) |
| SEM-14 | PASS | [独立依据与定位](../evidence/2026-10-08_hrsemshadow_review_r1/REVIEW.md) |
| SEM-15 | PASS | [独立依据与定位](../evidence/2026-10-08_hrsemshadow_review_r1/REVIEW.md) |
| SEM-16 | PASS | [独立依据与定位](../evidence/2026-10-08_hrsemshadow_review_r1/REVIEW.md) |

### 验证、限制与停止

- 原始输入全重算：1276原始帧/1561分支帧/4311簇，9366阶段序列、1561参照票及原Tracker快照、12,019,508成员坐标与r1一致。无效源row独立核对11,744,951；52228边缘线索全部按原row重建，185+5对账。
- 旧可用负例448分支帧/2210簇/458区域输出、24ROI与12空场冻结抽样重新核对。空场两口径0 HUMAN成立，UNKNOWN/小簇/无簇及上游删除分母保留；四段HUMAN帧13/244、269/271、281/281、1/195是结构代理，不是GT准确率。
- 原碰撞43帧=114254的8+空场WS的35，114205过期确认88帧；每机器身份每实际帧≤1票、五个实际帧含缺失、3票+min_age通过；关联歧义UNKNOWN，真人身份BLOCKED。
- 实际回归PL38、replay45、registration23ID exit0；两对数据实际digest核对，r1旧失败保留。本审核初次data中断exit4294967295、negative跨VM断言exit1保留，仅审核工具修正后data2/negatives2 exit0；不修改生产或算法值。全部实际命令、源码SHA、退出码及日志可复审。
- 设计默认关/回退/三值票源/生命周期/源码触点/GT和独立复审依赖明确；目前不建议生产切换。设备/物理/板端/部署/采集/网络驱动/ML/生产接入/下一工单均NOT_RUN，实际浏览器UI仍BLOCKED。
- 本轮审核完成后停止；不自动修复、不启动实施CLI、不进入下一工单。后续若返工，应新增证据轮并保留r1与本复审记录。
