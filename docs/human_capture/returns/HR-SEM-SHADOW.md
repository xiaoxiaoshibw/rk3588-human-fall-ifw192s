# HR-SEM-SHADOW 回传记录

## 2026-10-08 工单制定轮（Codex）

- 用户请求：制定工单供用户转发给Codex；状态DRAFT_READY_FOR_DISPATCH，未启动实施。
- 已制定 tickets/HR-SEM-SHADOW.md v1、唯一表 HR_SEM_SHADOW_ACCEPTANCE.md v1（SEM-01..16全部NOT_RUN），README与tickets/INDEX只追加登记。
- 范围：冻结S-A+的真实整簇全帧离线旁路、三值判定/负例、按实际帧3/5审计、GT审阅材料、生产接入设计；生产源码、参数、artifact、旗标、Tracker/Fall、部署采集/ML不授权。
- 工单依据：五段新会话诊断与新样本冻结语义复核；4×3×2相关区域判定不是独立24样本，空场12簇帧不是12独立物体；不把这些自验当生产验收。
- 起始branch/HEAD及完整tracked+untracked SHA：evidence/2026-10-08_hrsemshadow_plan_r1/00_baseline.json。
- 本次仅Markdown文档：检查16个唯一ID、文档链接/关键输入存在性、原登记文档前缀未变、冻结资产SHA；未运行算法测试或执行任何SEM验收。
- ponytail实际读取路径沿用本聊天 C:/Users/30680/.codex/skills/ponytail/SKILL.md；本次文档制定无算法实现。
- 交给用户转发开工，执行者需重新实读skill/核对最新树并逐ID回传；不由本聊天代发消息或创建聊天。


## 2026-10-08T13:34:58.999927+08:00 HR-SEM-SHADOW 执行 r1（Codex）

### 本轮信息

- 工单HR-SEM-SHADOW / r1 / 本聊天Codex单writer；用户直接授权A–D的PC离线范围。无子代理/OpenCode/改模型；模型运行标识未核实不填。
- 唯一表docs/human_capture/HR_SEM_SHADOW_ACCEPTANCE.md v1，SHA `3b5b83da5a83c460bc7590011034647f77272be70d1f92f7c2ddb9c0bd8498dd`；工单SHA `f9e9e4f705c2ed571d495f7164341bead7e768106eb48458ce40f474f4e819d6`。
- 状态 **SUBMITTED / REWORK_REQUIRED，未 ACCEPTED**；SEM-05～08与SEM-10 BLOCKED。设备/物理/板端/部署/采集/网络驱动/ML/生产切换/独立复审均NOT_RUN；实际浏览器UI检查单列BLOCKED。
- 起始branch/HEAD：master / `cfbb80c57508be1a0435fdb92260f698dc763934`；dirty/完整tracked+untracked+ignored资产SHA见 `docs/human_capture/evidence/2026-10-08_hrsemshadow_r1/00_baseline.json`、00_dirty.patch；用户原差异保留。生产、捕获与旧证据最终逐文件完整性见 `docs/human_capture/evidence/2026-10-08_hrsemshadow_r1/integrity.json`，return只追加、原前缀不动。
- ponytail实读路径：`C:/Users/30680/.codex/skills/ponytail/SKILL.md`（full）；复用冻结原函数、PL/registration/RL、stdlib与既有matplotlib，无新依赖。matplotlib技能实读完整路径 `C:/Users/30680/.codex/skills/scientific-toolkit-skill/references/scientific-skills/matplotlib/SKILL.md`。

### 集中诊断与根因覆盖

| 缺陷/验收ID | 根因 / 证据 | 入口与消费者 | 本轮处理位置 | 保留行为 |
|---|---|---|---|---|
| SEM-05/08整簇退化 | ROI外79/82成员改变顶团/腿柱/剖面；HUMAN帧13/244、1/195 | cleanup完整成员→冻结S-A+；旧联合判定/Tracker | 全帧harness与报告；不修冻结原型 | 不裁干净ROI、不试阈值；GT缺口保留 |
| SEM-11原票缺陷 | 同帧复用、缺失不老化；真实碰撞43帧、114205过期确认88帧 | PL.Tracker.tick；pipeline_frame；browser重复/seek消费者已读 | votes.jsonl、FrameVotes审计、vote_repro | 原Tracker/Fall零修改；歧义UNKNOWN，身份BLOCKED |
| SEM-04输入虚点 | 零XYZ无条件TLS/registration后通过高度/距窗 | registration.loadFrames/transformBuffer、浏览器载入、pipeline输入 | 原row账与同簇有效成员对照 | 不落地I01、不改变原图/聚类/产物绑定 |
| SEM-10负例不闭合 | WD02生成源码绑定不符；WD01区域不是全成员GT；格栅缺绑定样本 | 固定job、旧静态区域与全簇扫描 | negative4 + coverage.json | 不换job、不重签、不编家具标签/误报率 |

### 实际变更

| 文件 | 用途 / 用户原差异区分 | 源SHA |
|---|---|---|
| `docs/human_capture/evidence/2026-10-08_hrsemshadow_r1/record.py` | 本轮新增离线工具；原生产脏树不动 | `b5b457ae2958edf576fe1a59eabec7ed5c13e2417deab90dc01e9205106cbd9e` |
| `docs/human_capture/evidence/2026-10-08_hrsemshadow_r1/semantic.js` | 本轮新增离线工具；原生产脏树不动 | `48969bef8a474dbf98207d7d6558d789163ad6f3f35b3e7d53c888bcbd117233` |
| `docs/human_capture/evidence/2026-10-08_hrsemshadow_r1/shadow.js` | 本轮新增离线工具；原生产脏树不动 | `400aa4ac89f2d4dd0f0540056622bfa9f444142b92d81bcb1f2e42a9e0c42f44` |
| `docs/human_capture/evidence/2026-10-08_hrsemshadow_r1/negatives.js` | 本轮新增离线工具；原生产脏树不动 | `b1ff657b7f627c60b0817aad17b3229519b244386890d41d247c079ac41e4ee2` |
| `docs/human_capture/evidence/2026-10-08_hrsemshadow_r1/finish.py` | 本轮新增离线工具；原生产脏树不动 | `35f538ccf19aa0c940979ae585f3c34ba6469e1ed623f3bd7b2dc1f05ad8331f` |
| `docs/human_capture/evidence/2026-10-08_hrsemshadow_r1/review_template.html` | 本轮新增离线工具；原生产脏树不动 | `34d3150e470fefe59b9c6755bea73915c044742610589ec526dd309fdc775e68` |
| `docs/human_capture/evidence/2026-10-08_hrsemshadow_r1/review_check.js` | 本轮新增离线工具；原生产脏树不动 | `d022094cf77032c0cafcc4bd91d50985f75acf8ab1d1cdc2bde76c1996579729` |
| `docs/human_capture/evidence/2026-10-08_hrsemshadow_r1/vote_repro.js` | 本轮新增离线工具；原生产脏树不动 | `75f28963d18b7fbfd2b2d17a74f6d9f0a4bb4799353ebb3c42bf9dc6044470c9` |
| `docs/human_capture/evidence/2026-10-08_hrsemshadow_r1/plot_cases.py` | 本轮新增离线工具；原生产脏树不动 | `1bf4a79edebc1e23ff7cfc9d9b6997fc98685752e4ac443429d1b27cb984ae58` |
| `docs/human_capture/evidence/2026-10-08_hrsemshadow_r1/submit.py` | 本轮新增离线工具；原生产脏树不动 | `0a49dc6ea796bfc26ca95ea507c733fd1c1df246e90557815de1b9130203e09f` |


全部产物位于 `docs/human_capture/evidence/2026-10-08_hrsemshadow_r1/`，另仅本return追加。主输出为pass3（pass2同digest），旧负例negative4（negative3同digest）；CSV含JSONL byte offset、逐簇/帧row索引；源码和固定参数绑定见pass3/binding.json/source_hashes.json。历史发现pass1/negative1/2、失败日志和工具快照保留，不改旧evidence。

### 逐条验收（self-check，非独立验收）

| ID | 自验 | 证据与限制 |
|---|---|---|
| SEM-01 | PASS | 00_baseline.json + pass3/binding.json + integrity.json；5908 起始文件、五段原始源/固定TLS/诊断代码绑定；最终完整性检查后生效。 |
| SEM-02 | PASS | 原函数/阈值精确片段 SHA；24 ROI 特征与12空场抽样逐值一致；semantic_selfcheck exit0。 |
| SEM-03 | PASS | 1276 原始帧，1561 帧分支行，4311 实际候选簇；同原cleanup簇全部有效成员；全零/无效源row独立记账，原输出同时保存。 |
| SEM-04 | PASS | 三值/标志/数值原因齐全；小簇分档、空点与无效点自检；NECK未显式分类=null，不补骨架；valid_member_size_bins见audit_checks。 |
| SEM-05 | BLOCKED | 114205 REF影子：HUMAN证据13/244（5.33%诊断上界）；人工簇身份/全帧连续映射0覆盖，不可报95%通过。 |
| SEM-06 | BLOCKED | 114254 REF影子：269/271（99.26%代理）；非ROI成员与家具混入身份待GT，gate仍WARN。 |
| SEM-07 | BLOCKED | 114340离线V2：281/281代理；185点与5 cleanup点身份UNKNOWN，不能把区域保留率当人体保留率。 |
| SEM-08 | BLOCKED | 114422离线V2：1/195（0.51%诊断上界）；HEAD全0、ARM45/195，腿证据1帧；GT未闭合，目标不宣布通过。 |
| SEM-09 | PASS | 空场285帧：V2残留0簇/0 HUMAN；工作空间1582簇=0 HUMAN/1097 OBJECT/485 UNKNOWN；全部小簇与虚点影响公开。 |
| SEM-10 | BLOCKED | 旧空场54帧283簇0 HUMAN；WD01区域出现4(P)/12(WS) HUMAN待身份审阅；WD02固定job代码绑定不符BLOCKED；格栅NOT_RUN，低横条cleanup后0点不计有效负例。 |
| SEM-11 | PASS | 按最近5个实际储存帧、含缺失帧、每机器身份每帧<=1票、原min_age；歧义UNKNOWN，真人身份BLOCKED；43碰撞帧、88过期确认帧及合成repro完整披露。 |
| SEM-12 | PASS | 52228边缘线索、原185点+原5 cleanup点精确对账；34关键帧、全帧本地载入/sidecar校验工具完成；点身份BLOCKED_GT，实际浏览器UI子检查BLOCKED。 |
| SEM-13 | PASS | 逐段分母、全簇三值/上游/粗候选/瞬时joint/原track/参照票分开；ROI全部PROVISIONAL，旧负例未冒充GT准确率。 |
| SEM-14 | PASS | pass2==pass3与negative3==negative4所有数据digest；30语义检查、票repro、GT负例检查、34页内案例headless检查；PL38/replay45/registration23实际全过；早期失败保留。 |
| SEM-15 | PASS | 本轮只新增evidence与追加return；全旧资产/SHA与return原前缀复验，见integrity.json；生产、captures、阈值、artifact与旗标未变。 |
| SEM-16 | PASS | SUBMITTED / REWORK_REQUIRED分项；ponytail实读路径已记录；接入与最小修订设计已提交，停在证据可复审，不自封ACCEPTED。 |


逐ID详细证据见 `docs/human_capture/evidence/2026-10-08_hrsemshadow_r1/acceptance_status.json` / [本轮报告](../evidence/2026-10-08_hrsemshadow_r1/README.md)。实际全帧/prepare/selfcheck日志exit0；SEM-05～08、10的BLOCKED不因exit0变PASS。SEM-01/15由最后实际integrity.json闭合；若漂移将追加修订。

回归：PL38、replay45、registration实际23ID通过，日志`regression_*.stdout/stderr/run.json`。registration首轮exit1(T37-09临时目录EPERM)、r2仅模块加载无执行不计回归、r3本轮隔离夹具实际run全过。old_negative1 exit1是WD02绑定不符，后续保留该输入BLOCKED而继续独立范围。两对数据digest逐文件一致；semantic 24原抽样+6边界检查、12空场抽样、991历史retention帧逐值对账；机械票repro/GT格式拒绝/headless34案例exit0。测试数字不替代本表项。

### 未闭合与限制

- 每会话正式95%目标仍缺所有实际帧的人工簇/成员身份或人工批准连续person_id映射。13/244与1/195只是当前任何候选HUMAN的诊断上界，明显未达到目标；269/271、281/281是代理证据，不发布准确率。
- 原185点与5 cleanup点精确定位、扩展52228区域删除线索均UNKNOWN；MIXED/人家具合簇不能由ROI重叠自动命名。WD01区域P4/WS12个HUMAN帧须人工排查；旧代表f2/42/150完整目标均UNKNOWN。格栅/有效low_bar未覆盖；WD02代码绑定阻断。
- reference票只作PROVISIONAL机器身份参照，关联不明UNKNOWN；不假装真人稳定确认。无效XYZ upstream图/拓扑影响仍在，有效成员对照不是生产补丁。
- 浏览器真实UI工具访问BLOCKED，单列browser_ui_status.json；页面逻辑34case/headless、人工标签拒绝检查及两幅真实PNG已验证，不能冒充浏览器截图。
- 弯腰/坐蹲/卧、多人物、物理地面、安装外参、真实跌倒、关节精度、板端与采集等NOT_RUN/BLOCKED，当前数据不提供这些结论。

### 交给独立复审 / 当前停止点

- 现行唯一表及本轮逐ID状态、完整命令exit/SHA/digest、原Tracker轨迹、无效row账、成功与失败均在本轮目录。
- 人工入口 [review.html](../evidence/2026-10-08_hrsemshadow_r1/review.html)，未预填source:human；gt_review_template.json为diagnostic，`finish.py validate`只校格式/绑定、不校人工标签真值或95%覆盖。优先审阅边缘/合粘/未知簇、43碰撞帧、88过期确认帧及WD01区域HUMAN案例。
- [接入与最小修订设计](../evidence/2026-10-08_hrsemshadow_r1/integration_design.md)：目前不建议生产切换；接口/三值票、默认关/回退、seek/reset、源码触点、GT和独立review依赖已列；校准按人物/场景/采集日分组，本轮数据不称全盲集。
- 停止在“证据和设计可复审”；未修改生产/冻结参数、未签artifact、未开生产旗标、未部署采集或进入下一工单。未自动启动独立复审。


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


## 2026-10-08T22:36:33.061879+08:00 HR-SEM-SHADOW-R2 证据可信性修复与重验（Codex）

### 本轮信息

- 单writer：本聊天Codex，PC离线；无子代理/OpenCode/改模型。用户明确允许Phase0–4最小修复和复审。
- 状态 **SUBMITTED / BLOCKED，未 ACCEPTED**；离线交付BLOCKED，生产接入仍未授权；WD02待规范裁定，SEM-05～08、10保持BLOCKED。
- 唯一表 `docs/human_capture/HR_SEM_SHADOW_ACCEPTANCE.md` v1，SHA `3b5b83da5a83c460bc7590011034647f77272be70d1f92f7c2ddb9c0bd8498dd`；工单SHA `f9e9e4f705c2ed571d495f7164341bead7e768106eb48458ce40f474f4e819d6`，两者未修改。
- 起始master / cfbb80c57508be1a0435fdb92260f698dc763934；dirty和6140起始路径/43,283,465,274字节基线见 `docs/human_capture/evidence/2026-10-08_hrsemshadow_r2/00_baseline.json`，用户原差异全部保留。
- ponytail实际读取：`C:/Users/30680/.codex/skills/ponytail/SKILL.md`，full；复用stdlib/既有Node与NumPy，不装依赖。

### 集中诊断与根因覆盖

| 缺陷 | 入口/根因 | 本轮修复/处理 | 保留行为 |
|---|---|---|---|
| SEM-12 | 外部index未绑定、SHA只字段对比、row摘要非内容摘要、显示/票据身份脱节 | 固定独立权威digest+实际raw28B/XYZ重建+receipt绑定+拒绝后清空显示；切帧清拾取row | 新R2入口；R1源码/evidence原样保留；GT真值不伪造 |
| WD02 | H.level额外历史生成源码==当前；源/产物SHA实读完整 | wd02_audit保留原断言，区分正式registration消费契约与历史leveling provenance，提交两案裁定 | BLOCKED；0处理帧，不换job、不重签、不自行放行 |
| SEM-05～08、10 | 人工全帧/实例GT与有效对抗覆盖缺口；05/08上界不足95% | 既有输入必要全帧/负例/边缘重放；逐项依赖和真实分母报告 | 门槛/算法不变，BLOCKED不自动变PASS |

### 实际变更

仅新增 `docs/human_capture/evidence/2026-10-08_hrsemshadow_r2/` 中review_binding.js（authority/source/content/receipt/validate）、build_review.js、review_template.html、sem12.test.js与必要独立审核/报告/日志；copied审核工具只适配R2输出/基线名。`changes.json`记录全部源码SHA，`delivery_manifest.json`记录新交付SHA。旧finish.py、旧页面和所有R1 assets零修改。本return仅字节追加。

### 逐条验收

| ID | R2结果 | 证据/限制（均在本轮目录） |
|---|---|---|
| SEM-01 | PASS | baseline/data_r2/full_recompute/integrity |
| SEM-02 | PASS | full_recompute30 checks+24ROI; negatives12 samples |
| SEM-03 | PASS | data_r2+full_recompute full-frame/member conservation |
| SEM-04 | PASS | data_audit/recompute trivalues, invalid row disclosure |
| SEM-05 | BLOCKED | 13/244 upper bound; human identity GT absent |
| SEM-06 | BLOCKED | 269/271 proxy; GT absent; WARN |
| SEM-07 | BLOCKED | 281/281 proxy; edge185+cleanup5 identities UNKNOWN |
| SEM-08 | BLOCKED | 1/195 upper bound; HEAD0; GT absent |
| SEM-09 | PASS | 285 frames both branches zero HUMAN |
| SEM-10 | BLOCKED | WD01 GT, valid adversarial coverage, WD02 adjudication unresolved |
| SEM-11 | PASS | 1561 votes + independent actual-frame constraints; original43 collision/88 stale disclosed |
| SEM-12 | PASS | sem12_verified4 accepted/17 rejected; independent_receipts_final; real browser |
| SEM-13 | PASS | separate denominators/proxies/truth/votes and costs disclosed |
| SEM-14 | PASS | actual two-pair digests + necessary regressions38/45/23 exit0 |
| SEM-15 | PASS | final integrity old assets + return prefix |
| SEM-16 | PASS | return/ponytail/reports and authorized stopping point |

- WD02 **BLOCKED_CONTRACT_ADJUDICATION**：12派生产物+raw/report/domain SHA完整；唯一leveling.py历史代码差异，不以诊断exit0计WD02通过。
- 实际命令/exit/stdout/stderr/源码SHA：`commands.md`与同名run/log；最终SEM12 4合法+17拒绝/0失败、34切帧；PL38/0、replay45/0、registration23ID/0（T37-20未跑）。独立receipt34案例/100簇/2358删除点/183340坐标；全1561分支帧/4311簇/12019508成员坐标/9366阶段/1561票重算一致；旧可用448分支帧/2210簇/458区域，52228边缘源row和185+5对账。
- 实际浏览器：篡改拒绝、禁止保存、合法4311索引/3441成员载入、投影/拾取/合成UNKNOWN导出及校验通过，最终切帧状态正确；`browser_ui_status.json`/`browser_review.jpg`。synthetic导出不计真实GT，真实标签0。
- R2早期失败（基线名、结果独占写EEXIST）和ResourceWarning记录保留，最终干净执行为准。R1失败不覆盖。旧资产/return前缀由最终 `docs/human_capture/evidence/2026-10-08_hrsemshadow_r2/integrity.json` + `05_integrity.md`闭合。

### 未闭合与停止点

SEM-05/08上界13/244、1/195低于95%；06/07代理高仍无成员GT。185+5、WD01 P4/WS12 HUMAN归属UNKNOWN；low_bar空输入和格栅未覆盖NOT_RUN；WD02需人工规范裁定。旧负例可信审阅入口依赖与原无效点/Tracker风险登记，不扩大本单。零候选帧外部index没有行的原有载入可用性缺口登记；嵌入空帧可看。

复审采用本writer以独立raw/NumPy逻辑与明确攻击预期核查，无第三方审阅人签署声明。硬件/物理/板端/部署/采集/网络驱动/ML/生产全部NOT_RUN/未授权，不commit/push/reset/checkout/clean、不改生产算法、不签装artifact。现在停在R2证据可复审；仅建议WD02规则裁定、可信人工GT/有效覆盖补齐，必要新算法版本另授权，不推进生产。

报告入口：[docs/human_capture/evidence/2026-10-08_hrsemshadow_r2/REVIEW_R2.md](../evidence/2026-10-08_hrsemshadow_r2/REVIEW_R2.md)，依次00_audit、01_sem12_fix、02_wd02_review、03_blocked_revalidation、04_regression、05_integrity及最终manifest。


### 2026-10-08T22:43:10.248440+08:00 R2 完整性收尾

- integrity_final实测exit0：6139非return路径无变化；return原18732字节前缀不变；HEAD未变、范围外新增0。R1执行/复审证据均零改写。最终05_integrity与delivery_manifest已生成；临时本地server已停止。SEM-15按实测恢复PASS；整单仍SUBMITTED/BLOCKED、未ACCEPTED，生产未授权。
