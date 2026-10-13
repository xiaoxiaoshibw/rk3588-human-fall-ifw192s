# R3 标注工具易用性复审

SUBMITTED / BLOCKED，未ACCEPTED；单writer Codex，无代理/OpenCode/外部签署。用户“不会用啊看不懂”是本轮现有离线审阅工具返工依据，没有扩大算法或数据范围。

根因：用户真实侧栏约570px宽，原三图并排只有约165px/图；完整SHA/JSON和英文参数在主要操作路径中。新R3只新增review.html、guide.js、只读serve_review.py及测试/记录，不改旧页或生产。一次一张大投影、四个中文目标答案、中文帧/部位/错误、分步保存/下载；诊断和原row折叠保留。冻结R1 loader/receipt/row picking/invalid source/export仍直接只读复用，原enum/value/id不改。侧栏实测与before/after截图留档。

user_unsubmitted_draft.json保存用户旧页已圈选但未提交的控件值，明确unsubmitted/counts_as_real_gt=false；未代填reviewer、PERSON、连续身份或可见正例。旧用户页保持原状态；新页面由用户实际判断。其余未检查部位“不确定”快捷按钮只有用户主动明确选择时才填写不确定，无自动人体资格或坐标。

guide_tests_verified实际exit0，10项合成检查涵盖枚举/索引不变、幂等翻译、视图、点数、错误、原ID唯一和R1源码/输入/参数SHA。实际浏览器10项UI/边界检查见browser_checks.json；与合成分列。可见但无圈点/异簇row/缺reviewer均拒绝，空帧保留；实际human文件由Codex创建0。测试页已关闭，用户新旧页面保留。首次重跑自测因固定结果文件已存在exit1（exclusive output保护），失败日志保留；指定新输出文件后通过。首次自动化填点编号没有展开折叠区而中断，展开后完成实测；未以中断算PASS。

新Python3.8语法检查PASS；实际仍PC Python3.12，Python3.8实际执行NOT_RUN。无新依赖、采集、板端连接、部署、driver/config/artifact/ML/W04-W07变更。旧6711路径逐SHA/大小/缺失/符号链接核对，changed=[]、unexpected_new=[]，HEAD/branch不变；return末尾追加并另核旧前缀。

ponytail实际读取 C:/Users/30680/.codex/skills/ponytail/SKILL.md（full）；复用现成loader/export与canvas，不引入新框架或新模型。

下表原算法项沿用已核SHA的R1证据，本轮不宣称重跑或解除真人GT阻断。唯一表仍HR_SKELETON_OFFLINE_ACCEPTANCE.md v1。

| ID | status | scope |
|---|---|---|
| SKO-01 | PASS | R3 full baseline 6711 paths/44,727,944,634 bytes; dirty/tracked/untracked/ignored assets included |
| SKO-02 | PASS | R1 unchanged evidence carried forward: R2全部交付SHA/传递导入、固定TLS与诊断矩阵核对；独立raw复算336簇/871476坐标/票据 |
| SKO-03 | PASS | R1 unchanged evidence carried forward: 100唯一raw帧/120分支行；336未审簇/20无簇行全部保留；固定按会话划分，不称盲测 |
| SKO-04 | BLOCKED | R1 unchanged evidence carried forward: 真实reviewer/PERSON/连续person_id=0；两个开发sid各3连续实际帧门未满足，用户回复无 |
| SKO-05 | PASS | R1 unchanged evidence carried forward: CONTRACT/params-v1在首算法前冻结；参数SHA三次源码冻结间未变；无验证调参；真人参数标定BLOCKED |
| SKO-06 | PASS | R1 unchanged evidence carried forward: 纯XY平移、全有效成员/原Z/row保存；synthetic独立逆变换0m≤1e-5；真实PERSON标准化BLOCKED |
| SKO-07 | PASS | R1 unchanged evidence carried forward: 完整raw/member/global映射独立核验；20绑定/节点区域挑战；synthetic合法节点support独立重算；真人支撑BLOCKED |
| SKO-08 | PASS | R1 unchanged evidence carried forward: 空、非有限/原零XYZ、低支撑、家具/MIXED/UNKNOWN拒绝测试；184125无效源成员已定位，无上游重聚类 |
| SKO-09 | BLOCKED | R1 unchanged evidence carried forward: synthetic真实形状数学正例产7节点，真人可见躯干正例没有GT；不得用全拒绝算阳性通过 |
| SKO-10 | BLOCKED | R1 unchanged evidence carried forward: synthetic头/手和缺头拒绝PASS；实际举手窗口HEAD可见性未标，不验证真实头能力 |
| SKO-11 | BLOCKED | R1 unchanged evidence carried forward: PCA退化/符号UNKNOWN、单下部/双A-B synthetic PASS；真实分离/朝向GT未闭合 |
| SKO-12 | PASS | R1 unchanged evidence carried forward: 独立SkeletonTracker；实际整数stamp/dt；重复/倒退/seek/缺帧/换5类键/恢复/跳变实测；原Tracker/Fall无变化 |
| SKO-13 | PASS | Chinese responsive guided UI; 10 synthetic UI contracts and 10 actual browser checks; original receipt/enum/source/export core reused; user old unsubmitted draft backed up, original tab untouched |
| SKO-14 | BLOCKED | R1 unchanged evidence carried forward: 逐节点336未审/valid0/UNKNOWN336；1680槽观测；区域误差、真人跳变/恢复和精度均BLOCKED，无伪造正确率 |
| SKO-15 | BLOCKED | R1 unchanged evidence carried forward: 固定验证/举手/空场拒绝流程运行；40空场分支行0有效PERSON节点；隔板/举手真人效果因GT缺失BLOCKED |
| SKO-16 | PASS | R1 unchanged evidence carried forward: 独立struct+标量变换复算raw/票据，synthetic显式胸中心[10,20,1.05]/support/逆变换；最终pass5/6三个数据SHA相等 |
| SKO-17 | PASS | R3 guide_tests_verified exit0; Python -B -W error; old6711 asset SHA unchanged; return old prefix checked before/after append; original production/algorithms/evidence unchanged |
| SKO-18 | PASS | R3 UI-only SUBMITTED/BLOCKED; ponytail read and recorded; no agents, no production, no new algorithm or fabricated GT |

停止于现有标注工具可操作的handoff，不自动执行真实节点或进入主线。服务保留运行给用户实际标注，符合当前用户交接意图。
