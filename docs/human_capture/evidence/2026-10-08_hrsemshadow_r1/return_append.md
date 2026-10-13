

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
