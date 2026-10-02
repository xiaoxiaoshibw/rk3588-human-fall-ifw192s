# GL-02 验收基线 v1

建立：2026-10-01。按[流程v2](WORKFLOW.md)执行。冻结已有GL-02范围与可观察语义；缺覆盖在实现前集中检查，提交时补齐。历史通过仅代表对应检查，不代表整个条目PASS。

当前（2026-10-02）：A01–A12软件PASS、D01设备NOT_RUN、P01真实物理BLOCKED；GL-03软件前置已满足，本轮未启动。最新独立结果为[R7最终复审](evidence/2026-10-02_gl02_r7/CODEX_REVIEW.md)，覆盖R5/R6已闭合修复与完整入口/请求矩阵。下面R4栏为历史基线，不是当前状态；v1要求语义未改变。

## 要求来源与检查入口

| 简称 | 文件 |
|---|---|
| T | [GL02工单](tickets/GL-02_ground_frame.md) |
| P | [地面PLAN](GROUND_LEVELING_PLAN.md)，几何决定/关卡 |
| G | [几何契约](GEOMETRY_CONTRACT.md) |
| I | [交互契约](INTERACTION_CONTRACT.md) |
| C | [GL00获审扩展](evidence/2026-10-01_gl00_r4/25_contract_extension_draft.json)、[GL01边界](evidence/2026-10-01_gl01_r4/CODEX_REVIEW.md) |
| R | [R4要求](AI_PROMPT_GL02_CLAUDE_R4.md)、[R4复审](evidence/2026-10-01_gl02_r4/CODEX_REVIEW.md) |
| S0 | [仓库GL02测试](../../src/human_fall_detection/tests/test_gl02_ground_frame.py)及HF回归 |
| S2 | [R2集成](evidence/2026-10-01_gl02_r2/codex_r2_integration_checks.py)、[静态检查](evidence/2026-10-01_gl02_r2/static_probes.py) |
| S3 | [R3入口检查](evidence/2026-10-01_gl02_r3/codex_r3_context_checks.py) |
| S4 | [R4reload/pending检查](evidence/2026-10-01_gl02_r4/codex_r4_reload_checks.py)，最终失败60_* |

## 固定条目

下次回传/复审按ID填写结果与证据。“待补覆盖”不是新功能，要求来源已列出；不得将静态阅读一概冒充运行通过。

| ID | 来源 | 必需预期与反例 | R4覆盖事实/待补项 |
|---|---|---|---|
| A01 数学 | T1/2，P4，G | 多倾角/高度/轴方向，地面Z=0、任意点Z=n·p+d、逆变换恢复；退化轴/镜像/非刚体拒绝 | S0已有检查通过 |
| A02 输入 | T1/4，G，C | normal/offset/R/t/unit/frame/version/count有限且严格类型；bool、字符串、损坏ID/文件及父派生不一致不能启用或部分写入 | S0/S2多类反例通过；启动/reload/配套逐一确认 |
| A03 证据/兼容 | T3/5，G，C | 几何/身份/物理分离，老v1原义和未知外参/IMU保留，不伪造trusted/来源、不升级confirmed | S0/S2已有例通过；来源保存受A06约束 |
| A04 入口绑定 | T6，R1，G | full、ground-only、paired、空reload统一canonical及版本、caller解绑；bare和完整+局部混合拒绝 | S2/S3部分通过；完整入口矩阵需确认 |
| A05 版本资格 | T6，P4，R2 | calibration_id或GDID变化清旧目标/位置/快照/请求/基线/动作资格；相同上下文保留连续性；源seq/stamp/epoch与旧事件保留 | S0/S3覆盖新版本同GDID；ground-only及缓存/历史不变量待补查 |
| A06 完整产物 | T4/6，G独立产物，R复审1 | 空/相同reload保留input SHA/evidence/note/reference/transforms/rotations/status/verification和合法扩展且deepcopy；局部变化不继承矛盾旧关联证据，不冒用旧版本 | S4两方法FAIL；局部更新关联字段校验/失效待补 |
| A07 ROI可信 | T7，C | 自动AABB不当可信地面，稀疏/无可信支持unknown/degraded；有效范围/GL00门槛不放宽 | S0/S2已有例通过 |
| A08 监测 | T7，R4，C | 整片+0.1m持续同向平移触发，10%遮挡不锁存、双向散点不冒充整体变化；间断清连续，一帧好样本/同版本reload不能清锁存 | S0/S2/S3已有正负例通过；同版本reload锁存待核查 |
| A09 消费门控 | T5/6/7，R3 | monitor未知/降级/锁存时不发有效地面位置，不积累基线/动作有效证据；辅助IMU降级不等同地面失效，云显示/release可用 | S2位置例通过；恢复/辅助IMU/release按HF检查确认 |
| A10 请求全过程 | R3/4，I | monitor坏时新capture拒绝；accepted后失效有有界终态与原request_id回执，不无限pending，恢复不拼接失效前样本；ready旧资格处置明确 | S3新请求拒绝PASS，S4接受后失效FAIL；无帧/恢复/ready/重复请求待验证 |
| A11 导出 | T4，G | 新产物不覆盖历史，异常不能启用、文件冲突原内容不变；来源/质量/创建信息可追溯 | S0 CLI例通过；关联字段与A06合并检查 |
| A12 范围/回归 | T允许修改，AGENTS | 冻结配置、driver差异、Windows软链接表示保留；fall/follow/UI与只读输出不退化，无GL03/部署/采集混入 | R4 fall271/follow2/UI各18、23SHA通过；下轮按实际新SHA验证 |
| D01 设备兼容 | T，R | Python3.8.10/NumPy1.17.4隔离结果对应源码SHA；不可达NOT_RUN | R4 NOT_RUN，SSH255提交记录 |
| P01 真实物理 | T5，P7 | 身份/安装角度/点云原点高度/实测阈值需现场证据，未知不升级 | BLOCKED；不阻止合成软件范围验收，实际启用仍守关卡 |

## 上下文入口矩阵：一次检查完

| 入口/变化 | 合法行为 | 拒绝/不变量 | ID |
|---|---|---|---|
| 启动full | 校验/deepcopy完整产物，消费与发布同版本 | 同ID损坏拒绝，caller后改无影响 | A02/03/04/06 |
| 启动ground-only／无标定 | 合法ground稳定内容版本，无地面保持未知原义 | 不补身份变换、不丢非法输入错误 | A02/03/04 |
| full reload：新ID同GDID／新GDID | 原子切换，失效旧资格 | 失败完整旧上下文不变，时间/旧事件不改 | A02/04/05 |
| full reload：同ID同GDID | 校验解绑，完整保留产物及monitor连续性 | 不绕验证或静默清锁存 | A02/05/06/08 |
| paired reload：相同／变化 | 相同保留完整父产物，变化一致新版本 | caller解绑，不一致拒绝，来源不静默删 | A02/04/05/06 |
| ground-only reload：相同／变化 | 无derived时合法变化新版本，相同保留资格 | 有derived先验一致性，不混旧块 | A02/04/05/06 |
| 空reload | 完整校验/deepcopy当前上下文，保留ID/证据/连续性 | 不重建成缺字段产物 | A02/05/06/08 |
| bare derived／full+局部混合／损坏记录 | 获审边界明确拒绝 | 验证前不赋值、清缓存或重置monitor | A02/04/05 |

消费者至少查：calibration/ground/derived、monitor/latch、snapshot/state版本、tracker位置/动作代、selection快照/请求缓存、baseline/回执、features/fall资格、旧event与源时间。变更字段后核查整个消费链。

## 请求与恢复矩阵

| 过程 | 本轮收口策略/预期 | ID |
|---|---|---|
| monitor不可用→新capture | 拒绝且明确原因，不进pending | A09/10 |
| ok→accepted/pending→坏帧 | 首个处理到失效的帧取消/失败采集，保留失败历史，回原request_id终态；恢复不拼接旧样本 | A10 |
| ok→accepted/pending→无新云帧/watchdog | 既有接收单调钟watchdog判输入失效并取消，有界终态与回执不依赖下一帧；不推进源时间采样时长、不用接收秒补源秒；核查status_state与ROS回执发布 | A09/10；当前未验证，不宣称已确认新缺陷 |
| ready→失效→恢复 | 退休旧基线资格，恢复后重新请求，不自动复用旧ready | A05/09/10 |
| pending/ready→版本切换 | 退休旧资格，关联请求终态策略明确，新版本重新选择/采集 | A05/10 |
| 同版本reload且monitor一直ok | 保留有效任务/ready及正常监测连续性 | A05/06/10 |
| 锁存→好帧／同版本reload | 仍不可用，合法新上下文按获审规则重建资格 | A08/10 |
| 辅助IMU degraded、cloud/ground可用 | 保留HF原义，不触发地面取消策略 | A09/10 |
| 失败终态→同request_id重放 | 同内容返回原缓存回执且idempotent_replay=true，不重新执行；终态另发、对应原request_id，不默认替换原缓存；通过handle_request实测前置门控/缓存 | A10，I |

失效即收口、ready退休是本轮选择的最小实现策略；原R4也允许有界超时、ready暂停或失效，不能追认其他符合原契约的策略为缺陷。本轮复用collector/回执，不新增schema/物理门槛/通用框架。若与冻结契约冲突，按WORKFLOW集中解决并记录版本，不自行改断言。无帧等待验证路径先检查/复现，不凭风险推断判新缺陷；需要ROS回执透传时，只做必要生命周期连接并记录范围理由。

## 共用验证与提交条件

仓库根运行，下轮输出到自己的新证据目录，记录真实退出码/源SHA，不覆盖原日志：

```text
python -B -W error docs/human_fall/evidence/2026-10-01_gl02_r4/codex_r4_reload_checks.py
python -B -W error docs/human_fall/evidence/2026-10-01_gl02_r3/codex_r3_context_checks.py
python -B -W error docs/human_fall/evidence/2026-10-01_gl02_r2/codex_r2_integration_checks.py
python -B -W error docs/human_fall/evidence/2026-10-01_gl02_r2/static_probes.py
python -B -W error -m unittest discover -s src/human_fall_detection/tests -v
python -B -W error -m unittest discover -s src/human_follow_calibration/tests -v
node webui/human_fall/human_fall_lib.test.js
node webui/human_fall_preview/human_fall_lib.test.js
```

命令不覆盖所有缺口：集中诊断时补最小检查，映射条目/入口/转换，由Codex独立确认。手动赋pending不能替代handle_request真实流程。R1旧裸块断言的历史失败按R3获审例外保留，合法切换由S0/S2/S3覆盖。

A01–A12满足预期、有明确结论且缺口完成才软件PASS；D01/P01单列。新发现违反已有条目就返工并记录遗漏；没有违反现有语义的新能力需求另立项。

## 变更记录

| 版本 | 变更 | 依据 |
|---|---|---|
| v1 / 2026-10-01 | 集中GL02已有要求、入口与状态矩阵；A06/A10记录R4失败，明确失效收口策略；标出无帧/重复请求等待验证路径 | 原工单/契约/R4要求及独立复审；本次未运行新生产验收 |
| v1结果更新 / 2026-10-02 | A01–A12独立PASS；D01 NOT_RUN/P01 BLOCKED；不变更原验收语义 | R5→R7集中修复、R7 2+12方法与272回归、64条SHA；逐条见最新报告 |
