# GL-03 连续返工原因与开发计划审查 / 2026-10-02

触发：用户要求连续失败后先调研审查、判断计划或模型问题。依据 WORKFLOW v2 第5节，同根因重复未闭合/已列入口复审遗漏须审查，不继续零散追加补丁。本文是对已有证据和当前调用链的本地调研，不是新一轮生产实现或真机评价。

结论：**已确认 Codex 派工前覆盖不足，以及实现者遗漏已明确要求；没有证据证明指定模型能力不足。** 软件仍按验收v1 G03/G04/G05 FAIL、整体REWORK。O01探索性统计PASS，G06/真实身份BLOCKED、D01 NOT_RUN/BLOCKED；不把数据/服务限制算为同一次算法修复失败。

## 证据与责任

| 发现 | 已有证据 | 判定 |
|---|---|---|
| 四方法反例覆盖不足 | R2 codex_reference_checks.py覆盖from/to/无ground/newID reload；没有同ID改T、standalone原地修改、损坏父reference/record的事前检查 | Codex审查与计划覆盖失误，已确认。应提前沿入口和状态矩阵提供检查，不等提交后逐轮补漏 |
| 工单已有要求未实现 | R3提示词第1项已明确同版本reference内容不能混旧资格、caller解绑；R3源码仍只按calibration ID/GDID判断changed，standalone保留caller引用 | 实现遗漏，已确认；不能归为用户新增需求 |
| 诊断偏向原四方法 | R3 00_diag聚焦实际frame/目标标签/canonical矩阵，新resolver仅数值加载；node启动与reload共用优先权规则 | 实现诊断没有覆盖全部契约；Codex也没有用事前设计审查阻止遗漏 |
| 计划措辞有解释空间 | “artifact权威/覆盖旧standalone”与“显式冲突不可用”都存在，启动参数冲突与合法新版本reload未形成独立操作表 | Codex应明确两种不同操作；并非证明底层数学架构错误 |
| 数学/统计能被修好 | G01/G02、原四方法和O01同mask统计通过独立验证 | 反对“所有失败都是模型做不到”的泛化结论；不证明模型对剩余问题足够可靠 |
| 403/SQL问题 | 旧 CODEX_BLOCKED及CLI日志 | 服务/工具链阻塞，不能证明模型推理能力差；用户手动R3后来已提交 |
| 没有完整场景真值 | ROI截断/跨帧pool，无地面身份、目标环境运行证据 | 现场验收条件不足；不靠软件重写或模型更换解除 |

上述“计划失败/实现遗漏”为已确认事实；“模型能力不足”为未验证假设。回传自报实际模型不等于能力对照实验，当前没有另一模型在相同输入/限制/验收下的对照。不得凭返工次数换模型或把责任全部归给OpenCode。

来源：../codex_review_01/CODEX_REVIEW.md、17_extended_checks.txt；../00_diag.md；../../2026-10-02_gl03_r2/CODEX_REVIEW.md、codex_reference_checks.py；../../../AI_PROMPT_GL03_OPENCODE_R3.md。这些是既有证据，不重跑已通过回归来制造新轮次。

## 当前调用链与根因

纯API build_snapshot → resolve_reference_transform → reference几何；node startup → _resolve_reference_binding → snapshot/tracker；apply_ground_context → 新calibration/ground → 新reference绑定 → 以ID判断是否清旧资格；prediction → 用当前绑定逆变换tracker坐标。

同一个上下文有“是否合法、来自谁、内容是否固定、是否与track同版本”四个属性。R3补了正常来源/新ID路径，未保证四者同时成立，因此局部四方法通过仍可同ID换矩阵错8m。根因审查应围绕这组不变量，而不是继续分散修frame或prediction症状。

现有 resolver + calibration严格工具 + 现有生命周期边界足以承载修复。当前没有证据需要重写候选/跟踪算法、引入热更新框架/模型或新schema。开发计划需调整步骤和覆盖，不能无证据推翻已过数学实现。

## 修订后的开发计划（替代继续零散补丁）

### 阶段1：Codex先明确规则与反例

判据仍是GL03_ACCEPTANCE v1；先区分输入形态和操作：完整artifact、旧最小摘要、standalone；startup、相同内容reload、同ID内容不同、新ID reload、caller原地修改、外来frame。

| 操作/输入 | 必须成立的预期 | 最小实现方向 |
|---|---|---|
| 完整父artifact损坏/newer、known transform记录不合法 | 拒绝或reference不可用，不报告成功坐标 | 复用严格资格验证；完整父与legacy摘要分支明确，不将无derived视为父资格免验 |
| 合法standalone + 没有矛盾known父记录 | 保留旧支持，绑定后不受caller修改影响 | 在绑定边界拷贝规范化有效记录，消费者不持原始caller引用 |
| startup显式T与known父T冲突 | 明确拒绝或不可用，不能忽略冲突参数后投影 | 先检查输入冲突，再决定有效T |
| 相同ID、相同reference内容reload | 保持既有资格/语义 | 比较规范化有效内容，不能只比对象引用或任意metadata |
| 相同ID、实际reference内容变化 | 拒绝且live状态不变，要求新ID | 校验/比较在任何赋值前完成；不另造自动新ID |
| 新ID、合法新artifact T | 用新T；清旧snapshot/track/baseline/request相关资格，保留旧事件/源epoch语义 | 原apply_ground_context原子切换和失效路径，不能拿旧启动参数误阻新artifact |
| 外来frame/invalid、stale、occluded、pending/status/request | 坐标不可错标、预测不当实测，所有消费者同一绑定 | 追查现有共享门控/生命周期，不新增平行变换来源 |

事前独立反例已在R3 codex_review_01/review_checks.py，覆盖损坏父/record、启动冲突、同ID变化、同IDocclusion、caller修改。事前检查不要求改旧断言；补充矩阵遗漏须在实现前写明来源，不在提交后突然提出新业务门槛。Codex承认这组反例在R3之前没有准备充分。

### 阶段2：实现者先交集中设计，再写生产代码

先在R4 00_diag.md写：每种输入/操作选哪个canonical T、调用哪个现有严格工具、在哪一步深拷贝/拒绝、哪些状态失效、拒绝失败为何没有副作用、每行对应哪个检查。必须自行对照上表，不能仅写“复用resolver”就开始改。

以上表为已审方向：same-ID内容变化采用**拒绝要求新ID**，startup冲突与reload授权分开，standalone绑定固定；不让实现者在“拒绝/更新但保留旧资格”之间猜。设计若发现旧契约真矛盾，先记录具体旧行为/调用者/来源，Codex完成审查后再修矛盾处；独立可做工作继续，无需例行用户确认。

### 阶段3：一个写入者集中实现、逐入口验证

仅修既有G03/G04/G05，保留G01/G02/O01。先原9/4方法和R3扩展反例，再受影响生命周期矩阵，再当前主线/follow回归；检查命令与提交SHA对应。无新分离、真机或GL04，不重复统计已过O01。当前主线数量按实时树，不把支线六测试算入主线。

### 阶段4：Codex独立判定下一次失败的性质

- 预期有歧义、事前漏了已列入口或检查无效：记Codex计划/审查问题，先修规则或覆盖，不责怪模型。
- 事前规则/反例明确，模型实现仍违反：记具体实现错误及其入口；若再次同根因，则先读实现者设计/实际调用轨迹/失败原始输出，定位未理解或未执行哪条规则，不继续同文重试。
- SHA漂移/环境/服务失败：记对应外部条件，不算模型算法能力失败。
- 有完整清晰任务和有效反例仍反复无法实现时，才形成能力不足候选诊断；比较模型须同输入/约束/检查并记录实际模型。更换指定模型需用户授权，不擅自执行能力对照/并行生产写入。

## 本轮范围与下一步

只修改调研审查/开发计划和协调入口，不启动OpenCode、不新增生产写入者、不修改源码/原测试/旧证据。R4手动工单增加“先集中设计与不变量检查”作为首个阶段，仍是同一工单同一验收表，避免用户拼接多份要求。若用户已派发R4，本文不代表远程中止其会话，也不授权发送消息给其他聊天；回传后按同份规则审查。

结束核对发现外部写入：calibration.py/node_runtime.py/test_gl03_candidates_geometry.py已不同于R3提交SHA，lidar_candidates.py仍匹配，见SOURCE_STATUS.json。这里只能确认源码变化，不能据此确认写入者身份或R4完成状态。上述FAIL/责任归因属于R3固定证据；新源码未验收，不直接沿用旧失败作为新版本结论。未触碰外部源码、未重复运行其变动中的套件，待停止写入/正式回传后核对新SHA。
