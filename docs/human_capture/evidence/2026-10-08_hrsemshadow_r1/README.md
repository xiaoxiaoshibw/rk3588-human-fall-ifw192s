# HR-SEM-SHADOW r1：全帧整簇冻结语义旁路

状态 **SUBMITTED / REWORK_REQUIRED，未 ACCEPTED**。工具和离线证据已交付；四段人体目标的全帧身份GT缺失，SEM-05～08 BLOCKED；旧对抗覆盖SEM-10 BLOCKED。设备/物理/部署/采集/独立复审/生产切换 NOT_RUN。本轮在接入设计后停止。

冻结 S-A+ v1 在真实整簇上并未普遍复现区域抽样表现：中央普通静立仅13/244帧、举左手仅1/195帧输出HUMAN证据；两段的“任意候选HUMAN帧”诊断上界也低于95%。右桌前269/271、隔板旁281/281是候选结构/ROI代理结果，不能称准确率或正式95%通过。新空场两种口径均0 HUMAN，允许UNKNOWN并公开全部分母。

## 输入、冻结与复现

- 执行者：本聊天 Codex，单writer，无子代理/OpenCode/改模型；实际模型标识未通过运行接口核实，不编造worker身份。用户本轮直接授权A–D；README/工单初始DRAFT字样不被改写。
- 起始 master / `cfbb80c57508be1a0435fdb92260f698dc763934`；完整基线5908文件、35,826,341,519字节（tracked+untracked及ignored captures/既有HC证据/console dist），脏树原样保留。详情00_baseline.json、00_dirty.patch；当前轮排除于旧资产保护集。
- 唯一表 [HR_SEM_SHADOW_ACCEPTANCE.md v1](../../HR_SEM_SHADOW_ACCEPTANCE.md)，SHA `3b5b83da5a83c460bc7590011034647f77272be70d1f92f7c2ddb9c0bd8498dd`；工单SHA `f9e9e4f705c2ed571d495f7164341bead7e768106eb48458ce40f474f4e819d6`。不替换W03或HR-RET-V2验收表。
- 五段固定源帧244/271/281/195/285=1276，源点62,680,017。固定job与TLS/manifest/report/代码/源meta-bin全部绑定在pass3/binding.json。没有ICP重估、按mtime换job或loader放行。114205/114254只REF_SHADOW；114340/114422只离线V2函数试验；空场identity-reference不证明跨会话PASS/VALID。
- Frozen bodies SHA `015c60b6ae2f820969a75445001a644a31d51eea5c797b4d2acd1cddc0436756`，原文件SHA `33b4323c7b4afcc71cc6c5a9fb5d03c7965200df3a8580b32e435078b9699b70`；适配器源片段、数学和参数精确保留（含w_min=.06）。semantic_selfcheck 30检查、24 ROI结果；全管线991帧与历史retention逐值一致，24 ROI点数组/特征与12空场抽样逐值一致。历史S-A+生成时PL SHA早于inc2，不执行历史main；本轮新数据诊断的PL/registration代码绑定与当前逐文件相同。
- 实际原始布局是28B/点（meta与RL.STRIDE_BYTES对账），不是README示例16B。source row为帧内原始row，global row=offset_points+row；逐级顺序子序列映射有断言，重复坐标依序保留，不靠坐标Set折叠源row。

## 每段结果，分母不可偷换

| 会话/分支 | 总帧 | 整簇HUMAN证据帧 | ROI关联HUMAN帧（代理） | 旧粗候选帧 | 旧瞬时联合确认帧 | 原当帧簇track-confirmed | 原active轨道确认 | 参照旧票确认 | 参照语义票确认 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 114205 / REF_SHADOW | 244 | 13 | 13 | 244 | 31 | 25 | 98 | 10 | 3 |
| 114254 / REF_SHADOW | 271 | 269 | 269 | 271 | 267 | 268 | 268 | 268 | 269 |
| 114340 / V2 | 281 | 281 | 281 | 281 | 214 | 230 | 230 | 230 | 279 |
| 114422 / V2 | 195 | 1 | 1 | 195 | 3 | 0 | 0 | 0 | 0 |
| 114819 / V2_IDENTITY | 285 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 114819 / WORKSPACE | 285 | 0 | 0 | 265 | 111 | 76 | 76 | 76 | 0 |


“原当帧簇track-confirmed”是候选处理时快照；“原active轨道确认”包括lost轨道保留的状态，因此114205为25与98，而人体ROI关联旧确认是0。原pipeline里的`confirmed`不是有效字段，实际记录`human_confirmed`及每簇`track_confirmed`。上表原窗口与严格实际帧参照必须区分；参照身份仅PROVISIONAL机器空间身份，真人确认仍BLOCKED。所有无簇帧留在总帧分母。

| 会话/分支 | 全候选簇帧 | HUMAN | OBJECT | UNKNOWN | 60–199 | 200–399 | ≥400 | 无簇帧 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 114205/REF_SHADOW | 519 | 13 | 468 | 38 | 31 | 0 | 488 | 0 |
| 114254/REF_SHADOW | 819 | 269 | 255 | 295 | 271 | 22 | 526 | 0 |
| 114340/V2 | 815 | 281 | 0 | 534 | 534 | 0 | 281 | 0 |
| 114422/V2 | 576 | 1 | 72 | 503 | 381 | 0 | 195 | 0 |
| 114819/V2_IDENTITY | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 285 |
| 114819/WORKSPACE | 1582 | 0 | 1097 | 485 | 447 | 38 | 1097 | 0 |


分档按原聚类候选总n；无效源row过滤后的有效n另在audit_checks.valid_member_size_bins和CSV中计数。小于400的冻结v1一律UNKNOWN/POINTS_LOW；本轮工作空间空场485/1582（30.66%）UNKNOWN，1097 OBJECT。V2空场虽0候选，仍有10375前景点、6974 cleanup删除、2880未成分量点、146个小分量，不能把0候选说成点已完全清空。所有低于候选门的小分量/散点在frames.jsonl记账。

## 整簇边界与最小诊断

114205中帧f122/c1：全簇2416点、ROI重叠2337点；冻结区域诊断HEAD/LEGS/TORSO正证据，完整簇HEAD=false、LEGS=false、TORSO=true、FLAT_TOP=true → OBJECT。全簇cv=.104、w_torso=.190，而ROI cv=.235、w=.173。只多79个ROI之外成员就使组合证据改变，不能把手工ROI的结果推广到整簇，更不能偷偷先裁干净人体。

114422中帧f97/c1：全簇2443点、ROI重叠2361，w=.185、cv=.115、HEAD/LEGS/ARM=false → UNKNOWN。全部195主大簇TORSO=true，但HEAD=0、LEGS=1、ARM=45，导致HUMAN仅1；72帧FLAT_TOP，122帧INSUFFICIENT_OR_CONFLICT。此为真实完整候选与原区域结构的差异；哪些外缘成员属于家具、人体或混合仍需GT。

114254中帧c1含32个ROI外成员，114340含11个；不能因此自动写MIXED或STATIC_OBJECT。NECK参数/标志在冻结实现中没有显式分类，本轮保持null；min_bands虽在TH中，实际cv要求至少5个15点带，不能把TH.min_bands=3当已实施的可见性判据。没有新增头/关节坐标、骨架拟合或缺点补全。

![四段中帧全簇点云，局部坐标显示](full_cluster_cases_zoom.png)

图中的绿/灰/紫是算法证据，不是人工身份；红色为删除线索。缩放只改变显示坐标范围，分类始终使用全成员。未缩放视图见full_cluster_cases.png；所有点可按row定位。

## 无效XYZ与上游保留

| 会话 | 原始无效XYZ | 变换后通过denoise/workspace | 主前景候选无效成员 | 碰撞帧 | 旧确认不满足实际帧票的帧 |
|---|---:|---:|---:|---:|---:|
| 114205 | 2245889 | 2245889 | 0 | 0 | 88 |
| 114254 | 2494048 | 2494048 | 0 | 8 | 0 |
| 114340 | 2586274 | 2586274 | 0 | 0 | 0 |
| 114422 | 1795076 | 1795076 | 0 | 0 | 0 |
| 114819 | 2623664 | 2623664 | 0 | 0 | 0 |


五段原始无效XYZ总11,744,951，均与既有report.invalid_xyz_count一致。当前变换把零XYZ平移到有效高度，继续进入冻结背景/工作空间；本轮没有修生产I01或重建替代图。四段主前景及V2空场候选无invalid成员，参考匹配把这些点移出前景。

未删背景空场285个候选含2,623,664个虚点。最终两遍把同一原cleanup簇的全部有效源成员交给旧结构规则与语义规则，另存未经改变的原pipeline/Tracker输出；不重聚类、不让placeholder提供正证据。虚点可能已影响原图和簇拓扑，本轮有效成员对照不构成生产I01补丁已落地或物理坐标已核验。初始pass1曾把含虚点的整簇保守UNKNOWN；其证据保留，当前仅pass2/pass3有效成员对照支持结论。

上游逐帧workspace、reference删除、online-supported删除、cleanup删除与未成簇都有完整row账。隔板区域“91.9%保留”仍是原固定区域口径，不作真实人体损失8%结论。52228条区域删除线索中，f140原185个reference删除点与原数组精确匹配；5个cleanup区域点分别列在edge_review.json，全部身份UNKNOWN。

## 旧负例与覆盖缺口

- 旧空场233658：54帧、283整簇=217 OBJECT/66 UNKNOWN/0 HUMAN；有效原成员口径，两遍一致。
- WD01源223757：P165帧884簇、workspace165帧810簇；场景有真人，不能把整个场景的89/38个HUMAN簇当静态误报。历史WD01半径.55区域P在f65/66/147/148输出4次HUMAN，workspace12次；静态区域标签不是逐点身份，可能有遮挡/真人进入，优先审阅这些源row，不发布假阳性率。正式金标代表f2/42/150同位置全候选分别948/957/949点，均UNKNOWN，未凭机器补STATIC_OBJECT标签。
- 箱子历史区域64帧均有点，但逐帧支撑不足/结构不足全部UNKNOWN；只有合并校准集曾过400门，不能声称逐帧已排除家具误报。
- low_bar历史区域在本轮cleanup后64/64帧为0点，NOT_RUN有效结构覆盖；不能用空输入0 HUMAN做强负例。格栅没有独立来源/row身份，在现有资产中未找到可绑定样本，NOT_RUN，不把low_bar改名格栅。
- WD02固定旧job c9712acad48c4fb7a78cb119c08d4cdb 的leveling生成源码SHA与当前不符：历史leveling.py `4b8d7ae...` vs当前`3c3a881...`。本轮保持BLOCKED_INPUT_BINDING，保留失败日志，不改SHA、不换job、不重签或重新配平。新空场远场候选不能替代WD02金标。

## 原Tracker与独立3/5票

最近5个**实际储存原始帧ordinal**开窗；每候选机器身份每帧至多1票，缺失记0，关联歧义记null/UNKNOWN；至少3正票且原min_age=3。源seq缺口原样记录，不虚构未录制帧。仅唯一双向0.75m门关联才接续机器身份，仍用EMA.35与lost_max8；一对多/多对一拒绝强行近邻认人。不会把参照写回Tracker/Fall。

真实同帧track复用：114254共8帧、空场workspace35帧；空场有35帧参照关联UNKNOWN。114205原active确认98帧中88帧不满足按实际帧去重的原票参照，这包括缺失时不老化的状态；不把这些全部归因为真人误确认。逐簇处理快照、最终track状态、原5观测票、最近5实际帧票、missing/关联边和ID分歧均在votes.jsonl / vote_examples.json。

合成机械repro还复现原Tracker年龄3时，同一实际帧3个正簇可给一track3票；f0/f1正、f2–8空、f9正仍旧确认，但参照最近5帧仅1票。合成只是逻辑证据；两段真实输入的同帧碰撞/轨道拆合不是人工真人身份，依赖GT。冻结门与Fall从未修改。

## 人工审阅工具与GT纪律

[review.html](review.html)自包含34关键帧，可逐簇/点查看、投影切换、拾取原row；全帧入口选择pass3/clusters.jsonl与目标原始meta/bin，核SHA后固定变换重建全部成员。默认UNKNOWN/PENDING；簇PERSON需要人工person_id，点级标签只接受已绑定删除线索，导出需实际reviewer。机器未导出任何source:human真实标签。

gt_review_template.json与pass3/review.jsonl均source:diagnostic。手工导出后运行 `python -X utf8 -B -W error docs/human_capture/evidence/2026-10-08_hrsemshadow_r1/finish.py validate <人工sidecar路径>`，校源/变换/代码、ID/seq、成员SHA、重复项、标签枚举与PERSON身份。校格式不验证标签真实性/覆盖；全帧每簇PERSON/STATIC_OBJECT/MIXED/UNKNOWN以及连续person_id必须由人工确认或批准的映射闭合，才评95%目标。

查看页34案例的headless渲染/表单拒绝逻辑exit0，GT校验器1个合成有效格式+8个拒绝例、真实标签创建0；实际浏览器UI烟测被环回连接超时和file协议策略阻止，单列BLOCKED（browser_ui_status.json），不声称截图/浏览器实操通过。两幅真实点云PNG已视觉检查。临时127.0.0.1只读helper已停止，未连接板端。

## 当前交付与日志

最终输入和结果：pass3（与pass2完全一致）/negative4（与negative3一致）。每个JSONL在CSV中有byte offset，可按sid/mode/ordinal/ci定位；完整row成员在clusters.jsonl，阶段删除在frames.jsonl，票在votes.jsonl。determinism.json保存全部数据文件的两对digest。

Node v24.14.0，Python3.12.10；Python统一-B -W error -X utf8，无新依赖。PL38/replay45/registration23实际PASS（T37-20不在该套自动运行内，不以这组回归改变历史验收）。registration首轮T37-09为临时目录rename EPERM/exit1，日志保留；r2仅require模块没有执行suite，不计测试；r3将夹具限定到本轮test_tmp并实际run，23ID全PASS。old_negative1遇到WD02绑定assert/exit1，继续独立输入的negative2/3/4保存BLOCKED，未绕过绑定。

初始pass1及negative1/2保留；shadow_initial.js保存发现时工具，当前工具版本见各run.json/本轮source_hashes.json。所有正式数据重放均exit0，确定性一致；初始失败/限制不是被覆盖或算通过。

## SEM逐项自验

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


SEM-01/15以最后完整旧资产检查integrity.json的实际结果为准；仅允许本轮输出与return追加，发现范围外漂移须追加修订，不能把PASS预期替代检查。当前状态不等于独立验收。

## 下一步设计与停止

见[integration_design.md](integration_design.md)。冻结v1的整簇鲁棒性不足，当前不建议直接切换票源。优先补身份/成员GT、端部与腿带污染诊断；后续校准必须按人物/场景分组，不能把本轮已经多次观察的五段称为全盲留出。接入、修订实现、配准治理、artifact、ML、多姿态/采集各需另行明确工单。本轮完成证据与设计后停止。
