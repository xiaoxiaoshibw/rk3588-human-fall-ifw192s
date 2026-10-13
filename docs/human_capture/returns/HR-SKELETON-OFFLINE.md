# HR-SKELETON-OFFLINE 回传记录

## 2026-10-08T23:40:07.320903+08:00 计划制定轮（Codex）

### 本轮信息

- 工单HR-SKELETON-OFFLINE / plan r1 / 本聊天Codex单writer，用户只请求“制定下一个阶段计划”。无算法实施、人工标签生成、采集或部署；无子代理/OpenCode/模型切换。
- 状态DRAFT_READY_FOR_DISPATCH / PLAN_RECORDED，未开工，未ACCEPTED。唯一表HR_SKELETON_OFFLINE_ACCEPTANCE.md v1，SHA `92d92f70ee67061f9dad59bad2acdc6df9281fbafb6755bd715510ab7f0d1e10`；工单SHA `b998c0237be7a58ed3e339dc9178e0d5b9302f302a168b55371815f6a50a517a`。
- 起始 master / cfbb80c57508be1a0435fdb92260f698dc763934；全tracked/untracked及ignored captures/HC evidence/console dist的6263路径、43,359,798,841字节基线，见evidence/2026-10-08_hrskeleton_plan_r1/00_baseline.json及dirty记录。
- ponytail实读 `C:/Users/30680/.codex/skills/ponytail/SKILL.md`，full；本轮只进行代码范围设计和文档制作，不改算法。

### 诊断与范围设计

| 已知问题 | 本计划处理 | 保留边界 |
|---|---|---|
| 当前GT不足、HEAD0/195、05/08结构上界低 | 先绑定/人工身份与节点可见性，固定开发/验证窗口；无点UNKNOWN | 不把工具修复当人体性能通过，不修改SEM原表 |
| HR-07旧纯几何错误锁家具 | 新任务仅已确认完整人体簇，身份不是密度/PCA/pin推断 | 不重开关闭支线，不声称自动识别人 |
| W03未冻结、WD02争议 | 独立离线可行性；不消费WD02，正式W04/W05门保留 | 不绕过检查、生产旗标或原验收 |

### 实际文档变更

新增HUMAN_SKELETON_OFFLINE_PLAN.md、tickets/HR-SKELETON-OFFLINE.md、唯一验收表、本return及本计划evidence；README/INDEX/HUMAN_RECOGNITION_NEXT_STAGE_PLAN只末尾追加登记，原前缀最终检查。新文件SHA见01_document_checks.json/manifest.json。

### 逐条验收状态

SKO-01～18 **全部NOT_RUN**：本轮制定工单，不执行骨架验收。文档检查独立记录为01_document_checks.json，不冒充任何算法条目PASS。设备/物理/生产/采集/部署/模型/正式W04/W05全部NOT_RUN/未授权。

### 计划出口与停止点

A固定数据→B真实最小GT→C可逆标准化→D有支撑粗节点→E独立时序→F固定验证与独立复审。100唯一帧/120分支行预登记，开发/验证按会话分开；先两个开发会话各3连续PERSON帧的可信GT才做真实节点，未标部分BLOCKED；这个工作量条件不是人体/骨架精度门。

当前停止在计划可转发。本轮不启动算法或要求用户现在标注；未来开工由用户另行明确授权，GT缺失时独立可做部分继续、真人效果项BLOCKED。完整四肢、精确关节、多姿态/跌倒和生产接入不在本单范围；无commit/push或旧资产重写。


### 计划制定轮最终完整性

- 已核6263旧路径，三项登记文档原字节前缀均不变；范围外变更/新增0，HEAD不变。仅新计划/工单/唯一表/return与本轮evidence。18项仍全部NOT_RUN，算法未执行；manifest记录最终文档与工具SHA。


## 2026-10-09T00:44:27.426538+08:00 HR-SKELETON-OFFLINE r1 实施回传（Codex）

本轮用户明确授权A–F PC离线实施；单writer、本聊天Codex，无代理/OpenCode/模型切换。唯一表HR_SKELETON_OFFLINE_ACCEPTANCE.md v1 SHA `92d92f70ee67061f9dad59bad2acdc6df9281fbafb6755bd715510ab7f0d1e10`。

起始master / cfbb80c57508be1a0435fdb92260f698dc763934；6299旧路径/44,460,273,500字节基线。ponytail实读 C:/Users/30680/.codex/skills/ponytail/SKILL.md（full）。

状态 **SUBMITTED / BLOCKED，未ACCEPTED**；用户确认真实sidecar无，336簇未审、100唯一帧/120分支行保留。工具已实现/测试/交付，真人阳性/效果阻断；设备/物理/生产NOT_RUN。

实际工具、原因、集中根因、失败、GT/节点/代价、六类最终结果及停止点见 [REVIEW.md](../evidence/2026-10-09_hrskeleton_offline_r1/REVIEW.md)，实际命令/exit/runtime/SHA见COMMANDS.md与同名run/log；完整变更SHA见changes/delivery_manifest。绑定首次2失败及摘要挑战1失败保留，修复新工具后20绑定检查通过；参数始终冻结不变。

15 Python + 20绑定 + 6 headless审阅检查exit0；replay45/pipe38/registration23回归exit0；实际浏览器显示/拾取/切帧/篡改12检查与声明门通过，真人导出未发生。独立raw 336簇/871476坐标/184125无效源成员复算通过，synthetic支撑及逆变换0m核验，最终pass5/6三文件SHA相等。

| ID | 状态 | 实测证据与限定 |
|---|---|---|
| SKO-01 | PASS | 6299旧路径/44,460,273,500字节基线；branch/HEAD不变；用户本轮明确离线授权 |
| SKO-02 | PASS | R2全部交付SHA/传递导入、固定TLS与诊断矩阵核对；独立raw复算336簇/871476坐标/票据 |
| SKO-03 | PASS | 100唯一raw帧/120分支行；336未审簇/20无簇行全部保留；固定按会话划分，不称盲测 |
| SKO-04 | BLOCKED | 真实reviewer/PERSON/连续person_id=0；两个开发sid各3连续实际帧门未满足，用户回复无 |
| SKO-05 | PASS | CONTRACT/params-v1在首算法前冻结；参数SHA三次源码冻结间未变；无验证调参；真人参数标定BLOCKED |
| SKO-06 | PASS | 纯XY平移、全有效成员/原Z/row保存；synthetic独立逆变换0m≤1e-5；真实PERSON标准化BLOCKED |
| SKO-07 | PASS | 完整raw/member/global映射独立核验；20绑定/节点区域挑战；synthetic合法节点support独立重算；真人支撑BLOCKED |
| SKO-08 | PASS | 空、非有限/原零XYZ、低支撑、家具/MIXED/UNKNOWN拒绝测试；184125无效源成员已定位，无上游重聚类 |
| SKO-09 | BLOCKED | synthetic真实形状数学正例产7节点，真人可见躯干正例没有GT；不得用全拒绝算阳性通过 |
| SKO-10 | BLOCKED | synthetic头/手和缺头拒绝PASS；实际举手窗口HEAD可见性未标，不验证真实头能力 |
| SKO-11 | BLOCKED | PCA退化/符号UNKNOWN、单下部/双A-B synthetic PASS；真实分离/朝向GT未闭合 |
| SKO-12 | PASS | 独立SkeletonTracker；实际整数stamp/dt；重复/倒退/seek/缺帧/换5类键/恢复/跳变实测；原Tracker/Fall无变化 |
| SKO-13 | PASS | 实际浏览器12检查+人工声明门；完整簇/row拾取/切帧/空场/篡改清状态；headless 6合成导出绑定检查另列；真人导出未发生 |
| SKO-14 | BLOCKED | 逐节点336未审/valid0/UNKNOWN336；1680槽观测；区域误差、真人跳变/恢复和精度均BLOCKED，无伪造正确率 |
| SKO-15 | BLOCKED | 固定验证/举手/空场拒绝流程运行；40空场分支行0有效PERSON节点；隔板/举手真人效果因GT缺失BLOCKED |
| SKO-16 | PASS | 独立struct+标量变换复算raw/票据，synthetic显式胸中心[10,20,1.05]/support/逆变换；最终pass5/6三个数据SHA相等 |
| SKO-17 | PASS | Python -B -W error；15 Python+20绑定+6审阅工具检查；replay45/pipe38/registration23回归exit0；旧资产SHA无变化，最终return前缀另核 |
| SKO-18 | PASS | 本轮工具/GT/效果/资产/失败/停止报告齐全；ponytail实读路径；SUBMITTED/BLOCKED，未ACCEPTED，无代理或下一阶段 |

旧资产integrity_final PASS：changed=[]、unexpected_new=[]，HEAD/branch不变；return原前缀在本次追加前已核SHA，追加后prefix_check再核。只新增本r1证据并追加本return，未改上游或旧证据。

后续仅建议人工review两个开发会话各3连续PERSON帧及可见躯干/拒绝对照；GT_TASKS/gt_pending/frame_index提供全部成员与URL。WD02继续BLOCKED；正式W03/W04/W05门不变。无外部独立签署；没有部署/采集/板端连接/重签/commit/push/reset/checkout/clean。临时127.0.0.1服务已停。停止于本轮可复审交付，不自动进入W06/W07或生产。


## 2026-10-09T01:03:11.659981+08:00 人工标注入口开放（R2，仅工具展示）

用户反馈“人工GT如何标注，什么都没有”。重新启动R1已有serve_review.py（python -B -W error -X utf8，127.0.0.1:8883，exec session61867）并打开可操作页面，实际显示114205/REF_SHADOW/112、SHA verified；页面保留用于用户人工操作。R2仅新增入口说明/截图/记录，没有改R1或生产源码，没有新算法运行，没有填写人工标签，原SKO分项和GT阻断状态不变。原R1关闭服务记录不覆盖，此次保留运行直到用户完成标注。详见 [入口说明](../evidence/2026-10-09_hrskeleton_offline_r2/README.md)。


## 2026-10-09T01:27:09.989756+08:00 R3：标注工具易用性返工

用户反馈“不会用啊看不懂”。单writer Codex只新增R3中文分步审阅入口（127.0.0.1:8884）、UI helper/只读服务/测试和证据；复用冻结R1可信加载/圈点/导出核心。大图逐视图切换、四个中文目标判断、中文部位与错误，诊断折叠。用户旧圈选已备份为未提交草稿，旧页未改，不计GT。

ponytail实际读取 C:/Users/30680/.codex/skills/ponytail/SKILL.md（full）。起始master / cfbb80c57508be1a0435fdb92260f698dc763934；全6711路径/44,727,944,634字节基线与dirty记录见本R3。guide_tests_verified exit0（10合成检查），browser_checks另列10实际浏览器检查，首次输出重跑保护/折叠区自动化中断记录保留。Python -B -W error与3.8语法通过。

状态SUBMITTED / BLOCKED，未ACCEPTED；SKO13界面检查PASS，其他算法/GT项只沿用未改R1证据，仍12 PASS/6 BLOCKED，不冒充新人体性能。6711旧路径SHA无漂移，HEAD/branch不变，return旧前缀追加前后核对。完整逐ID/原因/源SHA/边界见 [R3 REVIEW](../evidence/2026-10-09_hrskeleton_offline_r3/REVIEW.md)。

没有真实人工标签由Codex生成，无新算法运行，无代理、生产修改、板端/采集/部署/commit/push/重签/ML；新旧只读服务留给用户实际标注（8884 session30960，8883 session61867），测试页已关闭。交付后不自动进入后续阶段。
