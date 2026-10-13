# HR-SEM-SHADOW 独立复审（2026-10-08，Asia/Shanghai）

**结论：REWORK_REQUIRED。本单“离线证据与设计交付”暂不接受；生产接入不具备资格。**

r1 的主要全帧数字、冻结函数、源输入和原 Tracker 机械问题得到独立复核支持。但人工审阅页存在实际成员绑定缺陷，**SEM-12 从原自验 PASS 改判 FAIL**。WD02 的阻断原因还需更正：源数据与派生产物未漂移，是审核 harness 额外要求历史生成代码等于当前代码。本轮只诊断，未重跑 WD02、换 job 或放行。四段人体及旧对抗目标仍有 GT/覆盖缺口；不能用这些工具检查代替算法目标通过。

## 范围与方法

- 用户仅授权 PC 离线独立审核。实读 AGENTS.md、HC README、工单、唯一表 v1、return、r1 README/设计/状态/完整性/源码绑定与相关源码、原始数据、真实日志。HC/HR 与 HF/GL 的验收体系未混用。
- 唯一表 `docs/human_capture/HR_SEM_SHADOW_ACCEPTANCE.md` v1，SHA `3b5b83da5a83c460bc7590011034647f77272be70d1f92f7c2ddb9c0bd8498dd`；工单 SHA `f9e9e4f705c2ed571d495f7164341bead7e768106eb48458ce40f474f4e819d6`。
- 起始 master / `cfbb80c57508be1a0435fdb92260f698dc763934`；本轮基线 **6056 个实际文件、43,280,721,488 字节**，含 tracked/untracked、ignored captures、既有 HC evidence 和 console dist。缺失的旧 tracked 路径另存，不替换 `src/CMakeLists.txt`。见 `baseline.json`、`dirty.txt`、`dirty.patch`。
- r1 起始 5908 个记录、143 个提交产物 SHA、12 个审核工具源码 SHA 全部重新比较，零不符；不是采用 r1 的 `pass:true` 字段。两对 digest 逐文件读取实际内容重新哈希，覆盖 frames/clusters/votes/review/points/binding/summary/reconciliation 以及全部旧负例输出。见 `hash_and_log_audit.json`。
- 实读 ponytail：**C:/Users/30680/.codex/skills/ponytail/SKILL.md**，full。复用只读纯函数、stdlib、已安装 NumPy，不安装依赖，不运行会写 r1 的 main/run/prepare/submit/review_check/vote_repro。
- `replay_audit.js` 从固定 raw meta/bin、TLS 和矩阵重算全部 1561 个分支帧，逐字段核对 4311 个簇、9366 个阶段 row 序列哈希、1561 份 FrameVotes 和原 Tracker 快照。另由 raw global row 独立逐点重建 **12,019,508 条候选成员坐标**。见 `recompute.json`、`full_recompute.*`。纯函数复用核查与独立 row/票窗约束并用，不声称另一套全新算法实现。
- `data_audit.py` 独立流式核对帧/簇/阶段守恒、global row、无效源 row、三值、小簇、实际帧窗、GT 来源及负例明细；`edge_audit.py` 从 raw+固定变换重建全部 52228 条边缘线索。所有 Python 执行使用 `-B -W error -X utf8`。

## SEM-01～SEM-16 独立判定

下列 PASS 仅针对该行的离线要求；BLOCKED 项没有取得 GT 资格，NOT_RUN 子项没有被计作通过。证据路径相对于本复审目录；`../2026-10-08_hrsemshadow_r1/` 表示只读原轮。

| ID | 独立状态 | 判断依据与证据位置 |
|---|---|---|
| SEM-01 | **PASS** | 当前 branch/HEAD、dirty、旧 tracked/untracked/ignored 记录重新绑定；五段源 meta/bin、固定 job、TLS/report/manifest、诊断矩阵及当前管线 SHA 核对一致。`baseline.json`、`hash_and_log_audit.json`、`recompute.json`；原 `pass3/binding.json`。WD02 的额外历史代码检查另列工具缺陷，不将其说成五段输入漂移。 |
| SEM-02 | **PASS** | 原文 TH+sub/kmeans1d/feats 精确片段复用，`w_min=0.06` 保留；原文件 SHA `33b4323c…`，函数片段 SHA `015c60b6…`，适配器 SHA `48969bef…`。24 次相关 ROI 特征复核及 12 个原空场抽样逐值对账。`semantic.*`、`negative_recompute.json`、`negatives2.*`；不运行历史 main。 |
| SEM-03 | **PASS** | 1276 原始帧，1561 分支行，4311 候选簇全量重算一致。旧规则与语义均使用同一原 cleanup 簇的全部有效成员，保留未经修改的原 pipeline/Tracker。语义前未使用旧人体硬门或圆柱预筛。无簇、小簇、少于3体素的散点及删除分母保留。`data_audit.json`、`stage_hashes.json`、`recompute.json`。 |
| SEM-04 | **PASS** | 三值、原因、结构/数值输出可核对；有效点不足400一律 POINTS_LOW/UNKNOWN，不补头或关节，NECK=null。无效零XYZ不进入最终正结构函数；原背景/cleanup拓扑仍受虚点影响，已独立披露，不能推导生产 I01 或坐标物理检查通过。`data_audit.json`、`recompute.json`、`semantic.*`；原 `audit_checks.json`。 |
| SEM-05 | **BLOCKED** | 114205 仅 REF_SHADOW：13/244（5.33%）为任意真实候选 HUMAN 帧上界。已证实冻结整簇证据上界不足95%，但正式身份验收依表仍因全帧簇 GT 未闭合而 BLOCKED；不伪造正式漏检率。`recompute.json` 中该会话与 f122/c1；原 `pass3/clusters.jsonl`。 |
| SEM-06 | **BLOCKED** | 114254 仅 REF_SHADOW：269/271（99.26%）为结构代理，不能升级为人体准确率。非ROI成员、家具混入/身份连续性未人工确认，gate 仍 WARN。`recompute.json`、`data_audit.json`；原 `pass3/review.jsonl`。 |
| SEM-07 | **BLOCKED** | 114340 仅 V2 函数层离线：281/281 HUMAN代理。区域91.92%不是人体保留率；185+5点及全部边缘身份仍 UNKNOWN，未补 GT。`recompute.json`、`edge_source_audit.json`；原 `edge_review.json`。 |
| SEM-08 | **BLOCKED** | 114422 仅 V2 函数层离线：1/195（0.51%）结构上界，HEAD 0、ARM 45、LEGS 1、TORSO 195，不能称95%通过或举手识别已解决。正式 GT 未闭合，依表 BLOCKED，另记已证实的数值目标不足。`recompute.json` 的 f97/c1；原 `pass3/summary.json`、逐簇索引。 |
| SEM-09 | **PASS** | 全285帧两口径重算：V2_IDENTITY 0候选/0 HUMAN，WORKSPACE 1582候选=1097 OBJECT+485 UNKNOWN、0 HUMAN。V2 10375前景点、6974 cleanup删除、2880未成分量点、146小分量未被藏掉。WORKSPACE虚点影响不作为静态身份/物理正确性证明。`recompute.json`、`data_audit.json`；原 `pass3/frames.jsonl`。 |
| SEM-10 | **BLOCKED** | 旧可用三段448分支帧/2210簇及458个区域输出独立复算；旧空场54帧283簇0 HUMAN。WD01区域 P4/WS12个 HUMAN待真人/混合归属；箱子64帧均UNKNOWN，low_bar64帧全空→有效负例NOT_RUN，格栅NOT_RUN。WD02本轮未运行；输入/产物 SHA 实际完整，额外代码相等检查是 harness契约问题，需先澄清。`negative_recompute.json`、`data_audit.json`、`WD02_contract.json`；原 `negative4/coverage.json`。 |
| SEM-11 | **PASS** | 离线机器身份每帧≤1票，最近5个实际帧含缺失0，至少3票且age≥3；歧义=null/UNKNOWN。逐行独立约束及全重算均通过；43碰撞帧=114254的8+空场WS的35；114205原确认中的88帧不满足实际帧票。合成碰撞/断帧再次复现。真人身份始终BLOCKED，生产Tracker/Fall不变。`data_audit.json`、`recompute.json`、`vote_repro_independent.json`。 |
| SEM-12 | **FAIL（原PASS改判）** | 原185点、5 cleanup点、52228线索均可按sid/ordinal/seq/source row定位，34嵌入案例可执行；但全帧审阅入口接受未绑定的任意簇索引，显示被替换成员时仍复制原member SHA。已有validator接受该记录，破坏可信人工审阅。`review_index_challenge.json`、`gt_challenge.json`、`tools.*`、`gt_challenge.*`；原 `review_template.html:49–59`、`finish.py:41–66`。实际浏览器UI仍BLOCKED，不能用headless替代。 |
| SEM-13 | **PASS** | 各段原始分母、HUMAN/OBJECT/UNKNOWN、旧粗候选/瞬时joint/当帧track-confirmed/active确认/参照确认区分清楚。ROI=PROVISIONAL，WD01有真人场景未整段叫静态误报；无准确率、95%或真人连续性伪造。`data_audit.json`、`recompute.json`、`negative_recompute.json`；原 README/summary。 |
| SEM-14 | **PASS** | 两对实际文件digest重哈希一致；冻结抽样、票repro、GT格式检查及当前相关回归独立重跑。PL38、replay45、registration实际23ID exit0；T37-20不在该suite内。r1旧两次exit1及空跑r2真实保留；本轮审核工具的中断/跨VM断言失败另存并解释，不算算法失败或成功。`hash_and_log_audit.json`、各 `*.run.json/stdout.log/stderr.log`。此PASS不覆盖SEM-12的页面安全缺陷。 |
| SEM-15 | **PASS** | r1起始5908记录与提交143产物哈希重新核对无漂移；本轮结束再检全部6056旧文件及return旧字节前缀。仅新复审目录和本return追加；不修改生产、冻结项、captures或旧证据，不签/装artifact，不启旗标/板端/ML。`hash_and_log_audit.json`、`integrity.json`、`changes.json`。 |
| SEM-16 | **PASS** | 原执行者实读ponytail路径与停止点有记录，SUBMITTED/REWORK_REQUIRED未自封ACCEPTED。接入设计默认关、回退/历史隔离、三值票源、生命周期、源码触点、GT与独立复审依赖明确，不建议直接生产切换。审核指出返工但不实施。原 `integration_design.md`、return；本 `REVIEW.md`。交付总体仍REWORK_REQUIRED。 |

## 全帧、成员与无效点的实证

| 会话/分支 | 原始分母 | 候选簇 | HUMAN/OBJECT/UNKNOWN | 60–199 / 200–399 / ≥400 | 无簇帧 |
|---|---:|---:|---|---|---:|
| 114205 REF_SHADOW | 244 | 519 | 13 / 468 / 38 | 31 / 0 / 488 | 0 |
| 114254 REF_SHADOW | 271 | 819 | 269 / 255 / 295 | 271 / 22 / 526 | 0 |
| 114340 V2 | 281 | 815 | 281 / 0 / 534 | 534 / 0 / 281 | 0 |
| 114422 V2 | 195 | 576 | 1 / 72 / 503 | 381 / 0 / 195 | 0 |
| 114819 V2_IDENTITY | 285 | 0 | 0 / 0 / 0 | 0 / 0 / 0 | 285 |
| 114819 WORKSPACE | 285 | 1582 | 0 / 1097 / 485 | 447 / 38 / 1097 | 0 |

合计候选分档1664/60/2587。空场在两个分支重复检查，原始帧总数仍1276，不能报1561个独立原始帧。上述HUMAN是簇帧数；四个人体会话恰好每个HUMAN帧只有一个HUMAN簇，所以对应13/269/281/1帧，仍不是GT准确率。

原聚类门是至少3个XY体素，再按n≥60产生实际候选；不会把小于3体素的点偷偷升为候选。所有剩余点仍在cleanup原row集合和unassigned计数里。row不是坐标去重键；重复坐标依原顺序逐条保留。各簇与小簇row不交叉，cleanup剩余集合大小等于unassigned；global row精确等于原meta offset_points+source row。实际点布局28B，与源码RL常量一致，README的16B示例未被拿来解释真实数据。

11,744,951个无效零/非有限源row独立从raw重算。五段这些点经现有变换全部进入denoise/workspace；四个人体主分支候选invalid=0，空场WS有285个含虚点簇，invalid成员合计2,623,664。旧比较与新分类剔除同簇全部invalid成员，没有为原始零点赋予正结构支撑。但原参考/在线图、点数门、cleanup和连接关系都先消费了虚点；**有效成员对照不能证明图/拓扑未污染，也不能代替入口I01修复的独立验证。** 本轮保留该风险，没有重建替代图或改变冻结算法。

## 正负例、GT及票源边界

114205 f122/c1完整2416点，ROI2337点，多79个ROI外成员：完整输入HEAD=false、LEGS=false、TORSO=true、FLAT_TOP=true，w=.190、cv=.104→OBJECT；原ROI特征为HUMAN。114422 f97/c1完整2443点、ROI2361点，多82点；完整HEAD/LEGS/ARM=false、TORSO=true，w=.185、cv=.115→UNKNOWN。冻结v1依赖顶部极值与腿带全成员，已证明对这些整簇边缘敏感；不能先裁ROI给它凑通过。截图只支持查看真实点云，颜色不是人工标签。独立查看了原 `full_cluster_cases_zoom.png`。

四段原meta人工标注数均0；执行产物GT为diagnostic/UNKNOWN。114254、114340虽代理高，不能以人全程存在推导每个候选为PERSON。114205与114422即使把每个HUMAN帧都当真人，仍达不到95%；正式行依唯一表保留BLOCKED，数值目标上界已明确不足，不能归结为“仅等GT就能通过”。

WD01金标是历史静态物/区域归属，不是半径.55内每帧每点永远静态的逐点真值。P区域HUMAN f65/66/147/148和WS的12次要检查真人进入/遮挡/MIXED与区域裁剪差异；不能把同场景其他真人簇输出也归为静态假阳性。整簇与区域成员交集另存 `negative_recompute.json/WD01_hits`；P代表f2/42/150近目标位置948/957/949点整簇仍UNKNOWN。WS合簇形心不代表WD01身份，只能按成员交集定位，未凭最近形心认定目标。箱子逐帧64次UNKNOWN不能当充分对抗通过；low_bar空输入、未绑定格栅和未运行WD02远场各保留覆盖缺口。

52228边缘线索全部从raw全局row独立重建，覆盖114340所有281帧；中帧原185点与前轮坐标数组完全一致，5个cleanup点的ordinal/seq/row见 `edge_source_audit.json`。这些是定位事实，点身份仍BLOCKED。

FrameVotes仅唯一双向0.75m门续接机器空间身份，EMA=.35、lost_max=8不变；一对多/多对一不以最近质心强认真人。出生前不虚构身份观测，出生后每个实际帧窗口连续，缺失记0，歧义记null；age按原实际帧跨度计算，min_age=3。原Tracker逐簇快照与最终active状态区分保留。114205当帧簇确认25帧、active确认98帧、严格旧票参照10帧；其中88个active确认帧不满足实际帧票门。参照旧票10、语义票3并非真人身份确认。114254原碰撞8、空场WS碰撞35；合成同帧三正簇及f0/f1正→f2–8缺失→f9正再次复现，后者新窗仅1票。生产Tracker/Fall没有任何改动。

## 实际缺陷与最小返工要求

| 类别/编号 | 实际问题与影响 | 最小返工要求（本轮未执行） |
|---|---|---|
| 实现错误 R-01 / SEM-12 | `review_template.html:49–59` 不校验外部clusters.jsonl文件SHA、行级成员哈希、seq/row范围/唯一性，直接把输入member SHA复制到导出。把114205/REF_SHADOW/f0/c0从1029个真实成员改成row0，仍显示“源SHA已核对；全成员1点”；其UNKNOWN审阅记录在合成内存夹具中通过原check_gt。人工可能看错成员却产出绑定正确的标签。 | 在新的返工证据轮绑定实际index文件digest；加载行核对sid/mode/ordinal/seq、row合法/唯一、row列表重算member SHA，必要时核重建XYZ SHA。导出只消费已验证记录，失败阻断。新增正常全帧载入及本次篡改/重复/越界拒绝检查；保留r1。不得把GT validator格式通过当标签真实性。 |
| 工具契约问题 R-02 / SEM-10 | `shadow.level:29–32` 将report历史生成代码SHA==当前源码作为额外硬阻断。WD02 raw meta/bin、tf/report/manifest.source、report SHA及全部TLS/SVD/RANSAC产物SHA均一致，现有 `registration.levelingBinding:97–109` 可读取同一个固定job。只有leveling.py历史4b8d7ae…与当前3c3a881…不同；不能说输入漂移或据此要求重签。 | 先在报告区分历史生成者provenance、冻结输入完整性与当前消费者源码绑定；由后续授权澄清是否要求历史代码重现，再最小调整审核器/协议并针对同一固定job补诊断。**本轮不改检查、不绕过H.level执行WD02、不换job、不签/装artifact或loader放行。** |
| 验收目标未达 R-03 / SEM-05、08 | 冻结v1真实整簇HUMAN上界5.33%与0.51%，原24相关ROI成功不能外推整簇。 | 保留原失败证据；按原integration_design先记录结构支持成员/端部腿带污染，补GT后在独立校准资料上提出新版本。不得在本单调阈值、裁干净ROI或重定义95%/分母。 |
| GT缺口 R-04 / SEM-05～08、10 | 四段全帧PERSON/STATIC_OBJECT/MIXED/UNKNOWN及人工批准的连续person_id未闭合；185+5点、WD01新HUMAN区域与非ROI成员身份不明。 | 补可追溯人工审阅与覆盖报告；UNKNOWN/MIXED/无簇不算命中、不移出分母。机器轨道ID、ROI交集或scene有人不能代替GT。旧WD01负例也需可绑定审阅入口/sidecar，原工具仅列五段新会话，不应假设已经覆盖旧负例标注。 |
| 覆盖不足 R-05 / SEM-10 | 箱子低支撑UNKNOWN、low_bar全空、独立格栅未覆盖、WD02未运行；新空场巨簇不能代表各类对抗结构。 | 列出实际非空、分档、独立资产与GT；只补获授权的离线绑定样本，空输入保持NOT_RUN。缺数据需未来授权，不启动采集/ML。 |
| 上游既有风险 R-06 / SEM-04、11 | 零XYZ污染背景与拓扑；原Tracker同帧复用/观测窗不老化。当前有效成员/参照票只是审核对照。 | I01/T01/T02单独授权和回归；不把FrameVotes复制为生产，不顺带改Fall/图/参数。 |
| 工具限制 R-07 / SEM-12 | r1浏览器环回超时及file协议策略阻断，真实UI未验证；34例headless只证明部分JS执行。 | 保留BLOCKED；返工后经允许的浏览器入口核真实载入、投影、拾取、导出/校验。不得绕过浏览器安全策略。该限制与R-01实际实现错误分别记录。 |

## 可复审性、命令及停止

实际重跑命令、exit和stdout/stderr均在本目录 `*.run.json`/`*.stdout.log`/`*.stderr.log`；汇总见 `commands.md`。Node v24.14.0，Python 3.12.10（`C:/Users/30680/scoop/apps/python312/current/python.exe`）、NumPy1.26.4。源码及审核工具SHA见 `changes.json`。

r1真实失败完整保留：old_negative1 exit1为WD02额外绑定断言；registration首轮exit1为T37-09临时目录rename EPERM，错误在stdout；r2仅require未run、exit0空日志不能计测试；r3真实run23ID成功。最终pass2/pass3和negative3/negative4所有实际结果文件digest一致，不是只比较摘要文字。本轮第一次data扫描因审核器重复构造大Set性能问题主动终止，exit4294967295，优化仅本审核工具后data2成功；第一次negative核对在最后12样本的跨VM对象deepStrictEqual处exit1（数值相同、对象原型不同），改为规范化值哈希比较后negatives2成功。所有失败/中断日志保留，不覆盖或当算法通过。

现有接入设计已明确三值票源、默认关、回退时隔离/重放轨道历史、seek/重复/倒退reset、cleanup后取全有效成员、未来PC及浏览器触点、GT/独立复审依赖和新版本数据划分。没有直接生产切换建议。数学冻结自检PASS、空场0 HUMAN和质量gate PASS，都不能证明loader VALID、真人GT、通用姿态或生产安全。

**生产资格：不具备；生产调用点/旗标/artifact签发或安装均NOT_RUN，设备/物理/板端/部署/采集/网络驱动/ML/下一工单均NOT_RUN。** 本复审只新增本目录并追加 `returns/HR-SEM-SHADOW.md`，保留旧证据和旧return前缀。审核后停止，不自动修复、不启动实施CLI、不进入下一单。
