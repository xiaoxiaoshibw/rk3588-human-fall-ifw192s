# OpenCode CLI执行与长会话恢复 / 2026-10-02

适用于当前指定`opencode-go/deepseek-v4.1-flash`，以本机版本/help/API为准，不照搬V2文档到V1。当前实查1.18.34。用户授权Codex管理派工、返工与流程，不主动询问例行事项；仍守单生产写入者、冻结资产和物理证据边界。

顶替登记 2026-10-03：Codex额度在GL-I05启动前耗尽（“你已达到使用上限…2026年10月4日 00:13后重试”），用户本轮明确“你顶替codex/方案A/以后不要问我建议”。Claude Code顶替Codex任GL-I05 R1唯一研究writer；HEAD `cbd0be1`，活动单 GL-I05 R1（GLI05_TASK/ACCEPTANCE v1）。本单无生产src路径，与“Claude不写生产代码”边界一致；替换生效。恢复后将由OpenCode Go Flash/defaultDB做独立只读二审。

恢复登记 2026-10-04：用户明确“让codex顶替你的位置”，Codex额度已过00:13恢复期，接回全部编排/收口角色。顶替期间成果：GL-I05 R1 **已SUBMITTED**（Claude为唯一研究writer，已停写，无生产src修改，生产423/423测试OK，研究13/13自检PASS，32 case全oracle_match/closure_safe）；产物在`evidence/2026-10-03_gl_i05_r1/research_01/`（含11_submission_manifest.json），回传在`returns/GL-I05.md`。待办移交给Codex：一次≤1min指定Go Flash/defaultDB无工具probe→按`AI_PROMPT_GLI05_OPENCODE_SECOND_REVIEW_R1.md`只读独立二审→逐ID收口。Claude自此不再写入。

编排者顶替登记：当Codex因额度/服务故障不可用时，Claude Code按[CLAUDE_STANDBY.md](CLAUDE_STANDBY.md)顶任其全部角色；顶替生效后由顶替者在本文件追加一行记录（时间、顶替原因与证据、当时HEAD、当前活动工单与轮次、恢复锚点），此后任何时刻只有一个生效编排者。

## 派工与成本控制

**WF-CODEX-R1 / R3 派工前置probe（2026-10-02）**：每次派工前对指定provider/model做一次无工具最小probe，总时限≤1分钟，超时即停止本次probe，不启动生产写入者。本轮证据目录单独记录服务probe的provider/model、起止时间、耗时、真实exit、原始输出/错误；超时记录超时原因及实际退出情况，不伪造exit。失败即登记服务BLOCKED及原因，转用户手动派发或Codex只读诊断/证据整理的备用通道；不得自动换模型、改认证/DB或启动第二写入者。本轮已由default DB成功probe及用户明确指令恢复自动派工；每次派工仍实查指定模型，隔离DB故障不外推为订阅故障。

服务probe与后续排障使用独立服务日志、单独计时，物理分流于算法诊断/实现/复审证据；不占用算法返工轮次，不将服务失败计入连续算法失败触发。证据：[GL03 R3服务阻塞](evidence/2026-10-02_gl03_r3/CODEX_BLOCKED.md)记录SQL store错误及同模型无工具probe订阅403；[R3计划/责任审查](evidence/2026-10-02_gl03_r3/codex_plan_audit_01/PLAN_REVIEW.md)明确服务/工具链阻塞不能作为模型推理能力或算法失败证据。本条补派工前门槛，不授权重跑当前R5或进行服务排障。

1. 每张工单建立一份验收表，把**每一入口/状态行**映射到运行检查或有依据的源码审查。提交前逐行核对，不能只覆盖Axx大类名称；GL02 R6漏掉pending标定切换是明确反例。
2. 一次集中返工列共享根因、最小文件范围、失败脚本和保留行为。当前代码写入由指定Flash负责，Codex诊断/验收；不并行试多个实现模型。
3. 本单续接明确session，引用文件与失败日志；不要重复注入全部历轮报告/原始工具输出。新工单另建紧凑会话，使用已审摘要、验收表和源码SHA作上下文。
4. 测试日志落文件，只向模型反馈退出码、摘要和失败部分；读源码按调用链必要片段，避免完整历史大段进入会话。源码不变且相关证据有效的无关回归复用；变更/失败才重跑。
5. 从step_finish/导出tokens监测上下文。本次约200k附近HTTP400；这是观测相关性，不是证实模型硬上限。后续本单约120k时先压缩，给失败诊断和输出留余量；不改全局配置或擅自换模型。

## API/CLI失败处理

先等进程停止并保留stdout/stderr/真实exit；核查已做修改、测试日志和SHA。失败可能发生在收尾，不要重置/重写已经通过的代码。错误发生前同根因多次修改失败，先重新复现全部兄弟入口、合并诊断；错误是HTTP/上下文时，不把它伪装成算法失败。

同模型只做一次无工具最小probe区分服务不可用与长会话问题。服务正常且长会话过大时，按[官方V1接口](https://dev.opencode.ai/docs/server/)恢复：

- `opencode serve --hostname 127.0.0.1 --port <专用未占用端口>`；后台助手必须隐藏，不能接管用户TUI。实际本机`/doc`核对endpoint与body。
- `POST /session/<已记录session>/summarize?directory=<工作目录>`，body只指定原providerID/modelID。此调用可消耗模型配额，仍沿用用户指定模型。
- 不能只靠HTTP成功判定压缩完成；导出核summary=True、实际模型、finish和session状态。
- 同session `opencode run --attach <本机地址>`续接紧凑任务。若代码已完成，只要求补范围/回传，不重复开发。保留原失败和新恢复日志。
- 恢复后再独立核SHA/运行有意义检查。结束只停止本次自建helper，核端口owner/命令行，不按名称批量杀OpenCode。

如压缩/续接仍重复失败：保留原会话，在不留活动写入者的条件下，以已验证源码SHA和紧凑工单建立新会话；不无限重复相同长提示，不擅自升级CLI或替换指定模型。服务完全不可用时继续Codex只读诊断/证据整理，缺外部条件明确记录，不能造通过。

实证：[GL02最终复审](evidence/2026-10-02_gl02_r7/CODEX_REVIEW.md)、原HTTP400、probe、summary、续接与metrics在同目录。成本数字仅为CLI自报，不足以宣称全市场最优；以修复通过率、验收闭合、上下文量、重跑次数和时间继续校准执行方案。

## 历史 SQL store不兼容与403 / 2026-10-02补记（结论以下方恢复事实为准）

当session list/summarize报no such column或Session not found时，先只读核对schema/当前版本，不手工迁移、删DB或覆写auth。官方数据库路径实现支持OPENCODE_DB；历史尝试曾在单个进程环境选私有task DB；本轮已确认此隔离变量触发Go项目绑定403，恢复派工使用default DB与仓库cwd，不再沿用隔离库，不改全局配置或认证。新会话必须用已审摘要、源码SHA及具体未闭合脚本，不假装原session已恢复。

GL03 R3实际隔离store可创建session，但指定Go Flash无工具probe403要求有效Go订阅。旧auth与当前Go credential key指纹相同，不能称错用旧key；没有新凭据可替换。不得盲目重复HTTP403或擅自换模型/购买服务。继续只读证据整理，写明未完成源代码与恢复工单；服务/账号权限恢复后再由指定模型实现。详evidence/2026-10-02_gl03_r3/CODEX_BLOCKED.md。

### 2026-10-02 最新事实：default DB Go 推理恢复，自动派工恢复

- 原始服务证据：[06_defaultdb_probe.jsonl](evidence/2026-10-02_service_probe/06_defaultdb_probe.jsonl)。17:49 在 default DB + cwd=D:/Code/ldiar，指定 `opencode-go/deepseek-v4.1-flash` 返回 PROBE_OK，step_finish reason=stop，input 8294/output 4，cost 0.001251492。核对的是Go推理成功，不只Console连通。
- 用户已核实：R3及后续隔离DB（OPENCODE_DB）403为上下文/project绑定问题，不是订阅故障。01–05失败原始日志及R3 CODEX_BLOCKED保留为历史，不覆写；不能继续用其阻断整个default DB通道。HTTP400长上下文故障另行分流，不计算法失败。
- 自动派工已按用户本轮明确授权恢复：Codex直接调用CLI派范围内返工并独立复审，不经用户搬运；生产代码单写入者仍OpenCode。R3起手动转发为临时历史安排，现已作废。
- 后续派工使用default DB与仓库cwd，不设置OPENCODE_DB隔离库，不更改auth/全局配置/模型。每次派工仍执行≤1分钟无工具probe并记录真实exit/输出/session/实际模型；失败只记录该条件下服务BLOCKED，先区分隔离变量，不盲目重试或更换模型。
- GL03 R7独立复审未发现新FAIL，故本轮未启动CLI推理/新probe/生产写入者；不把17:49证据写成当前时刻的新服务实测。GL04仍需用户授权。

### 编排交接登记 / 2026-10-02

- 2026-10-02 18:08:23 +08:00：按用户本轮交接说明，Claude Code于17:54按CLAUDE_STANDBY顶替后交回Codex；此刻登记Codex接回唯一生效编排/独立复审/状态收口角色，Claude Code不再并行编排。HEAD `8a5a2b28f922794bc25277319fd8dc85681802f1`；活动工单GL-03/R7独立复审已软件闭合，真实身份/设备分层保留；恢复锚点[R7复审](evidence/2026-10-02_gl03_r7/codex_review_01/CODEX_REVIEW.md)。无活动实现写入者，生产源码只由指定OpenCode写入。


收口外部变化补记：复审运行阶段 HEAD 8a5a2b2 未变；文档收口期间外部 human_capture/HR-01 提交推进至 2f5385ab8ff44213a5bbcc904dfc4c379a56d306，仅 docs/human_capture 与 pc_apps/human_replay 五文件。非本轮操作，保留、不归因不回滚；GL03 提交源码及旧证据 SHA 未变，最终核查见 evidence/2026-10-02_gl03_r7/codex_review_01/16_final_verify.json。

### GL04 R2恢复 / 2026-10-02

Codex在R1已停止写入后尝试同session官方V1 summarize（指定Go Flash/default DB）240秒超时，导出未出现summary=True；停止本轮自建4098 helper PID34700，未停用户其它进程。R2无工具probe exit0/12.23秒/无OPENCODE_DB；按用户允许同model default-DB新会话，用紧凑R2工单继续，R1原session保留，不假称压缩成功。证据[evidence/2026-10-02_gl04_r2/02_SERVICE_RECOVERY.md](evidence/2026-10-02_gl04_r2/02_SERVICE_RECOVERY.md)。服务超时不计算法失败。

### 编排交接登记 / 2026-10-03

04:18:21+08:00：用户明确“开始继续调用opencode开发”；Codex核无活动writer、四preview SHA仍R5，记录1679文件新范围基线。指定Go Flash/default DB无工具新probe8.828秒PROBE_OK/exit0，session ses_f01bb8798ffeZ3UKvzZ5ol43qI；[SERVICE_RECOVERED](evidence/2026-10-03_gl04_r6/SERVICE_RECOVERED.md)。恢复OpenCode唯一writer按R6先诊断后实施，不并入正式/不设备操作，原55.313秒超时是历史服务记录。

本轮用户恢复指令覆盖Claude临时顶替：Codex接回唯一编排/独立复审/状态收口，读取实际R5提交与SHA，不写生产代码。R5正式独审仍REWORK，后续R6已集中准备但指定Go Flash/default DB probe55.313秒超时/真实exit1，无活动生产写入者；详[evidence/2026-10-03_gl04_r5/CODEX_REVIEW.md](evidence/2026-10-03_gl04_r5/CODEX_REVIEW.md)与[R6服务BLOCKED](evidence/2026-10-03_gl04_r6/CODEX_BLOCKED.md)。原顶替登记下文保留；本轮无更换模型/DB/认证/配置，无部署/采集/板端网络/GL05。恢复服务后按当前R6集中工单先≤1分钟probe，不将本次服务超时计算法失败。

### 编排交接登记 / 2026-10-03 顶替（Claude Code 接 Codex）

- **顶替时间**：2026-10-03（Asia/Shanghai，本登记写入时点的当日会话）。
- **顶替原因与证据**：Codex 在推进 GL-I01/R1 实施阶段中报额度耗尽（`你已达到使用上限。升级套餐或充值额度以继续，或在 18:45后重试`）；用户明确指令 `接替codex继续开发`。
- **顶替范围**：按 [CLAUDE_STANDBY.md](CLAUDE_STANDBY.md) 顶替其全部角色（编排/独立复审/状态收口），不写生产代码，唯一生产代码写入者仍 `opencode-go/deepseek-v4.1-flash`（default DB，无隔离库）。
- **当时 HEAD**：`cbd0be1c86a1051a9a5800dfb7263f842896e1e6`（master，工作树故意脏，保留用户差异与未跟踪源码）。
- **当前唯一活动工单与轮次**：GL-I01 / R1（离线 capture 数值输入适配，本地离线）。
- **恢复锚点**：`docs/human_fall/evidence/2026-10-03_gl_i01_r1/`（同 session 两次压缩续接成立：`10_compact_verified.json` 与 `14_compact_verified.json` 均导出 `summary=true`/`finish=stop`/`modelID=deepseek-v4.1-flash`/`providerID=opencode-go`/`http 200`；`16_opencode_compacted.jsonl` 尾部 step_finish `stop`/`reason=manual context control at123501` 记为对齐保留）。
- **回传已追加**：`docs/human_fall/returns/GL-I01.md` 本轮 R1 段已写入（SUBMITTED，实现者自报）。
- **SHA 已核对（白名单四文件 + return 申报逐项吻合）**：`core/capture_input.py 56355e9594433d91…`、`scripts/prepare_capture_input.py 648a8da63a6656b0…`、`scripts/calibrate_sensors.py 3f30cf945d70b06f…`、`tests/test_gli01_capture_input.py 50f615d7a5ffdc49…`（完整 64 位见 return 中表格）。
- **冻结资产未改**：`src/human_capture/scripts/capture_server.py`、`src/CMakeLists.txt`、`webui/{human_fall,human_fall_preview}/`、`pc_apps/human_replay/` 差异仍是历史用户痕迹，非本轮写入。
- **Claude Code DONE 清单**（顶替生效前自检）：已读 WORKFLOW/DISPATCH/CLI_RECOVERY/CLAUDE_STANDBY 顶几行+当前工单 `GLI01_ACCEPTANCE.md`、工单 R1 设计与实施证据 `06_DESIGN_REVIEW.md`、`09_DESIGN_APPROVED.md`、return 末尾 17_implementation_checks.md；HEAD/工作树/SHA 已核；未触碰生产代码、未新建 probe/工单/复审。
- **当前 NO-RUN/BLOCKED 分层**：GL-I01 软件 `I01–I08`/`M01–M13` 仍未开始条目级独立复审（当前状态仍是实现者 SUBMITTED 自述）；B01 原 bag 布局证据 BLOCKED、D01 设备/物理 NOT_RUN；GL04 真实 DPR NOT_RUN/正式不合并；GL05 设备/板端网络/采集/部署未授权。

### 编排交接登记 / 2026-10-03 Claude Code 交回 Codex（候补）

- **交回发起**：用户指令"给我codex接管提示词"。Claude Code 已准备完整交接包 [CODEX_HANDOVER.md](CODEX_HANDOVER.md)（事实源、SHA 表、技术锚点、待决策项、铁律）。
- **顶替期间完成**（Claude 全角色）：① GL-I01 R1 独立复审 PASS（I01–I08/M01–M13，B01 BLOCKED/D01 NOT_RUN）；② 依用户授权派工 GL-I02 R1 两阶段（00_diag → 04_DESIGN_REVIEW 设计门 → OpenCode 实施 577s exit0）并完成独立复审；③ 与用户多轮迭代现场协议（up_axis 纠正为 `[0.438371,0,0.898794]`、高度 `[1.2,1.7]`、fit/3×validation 圈定）；④ 真实 fit 走通尝试确认协议-场景矛盾（采样 80<100），用户选路线3冻结真实 fit，GL-I02 R1 收口（SYNTH PASS/REAL NOT_RUN）；⑤ 起草 GL-I03 R1 工单（K01–K06，独立 override config 路线），**未派工、待 Codex 复核放行**。
- **未做**：未写任何生产代码/测试（OpenCode 仍唯一生产 writer）；未 commit/push/reset/checkout/clean；未启动 GL04 DPR/GL05/设备/采集/部署/板端网络；GL-I03 未建正式验收表（草稿在工单内）。
- **HEAD**：`cbd0be1c86a1051a9a5800dfb7263f842896e1e6`（master，工作树故意脏，SHA 对照见 CODEX_HANDOVER.md §四）。
- **交回等待**：Codex 额度恢复（用户提示 18:45）后，应先在本文追加正式"接回登记"，以 CODEX_HANDOVER.md 为唯一恢复锚点；此后唯一生效编排者为 Codex，Claude Code 不再并行编排。


### Claude Code 未顶替观察期登记 / 2026-10-03

今日用户此时段又通报"Codex 已恢复"。**Claude Code 未进入正式顶替**（上方登记只到隔壁 DONE 清单为止，后续 CLAUDE_STANDBY 顶替脚本未被本轮触发/未走完）；本条仅作为事实补充，此刻唯一生效编排/独立复审/状态收口/自动派工者仍是 **Codex**，Claude Code 在此支线只做消息路由与证索引，**不写生产/测试代码，不启动 probe/工单/复审**。现场 SHA 今日已再核（`sha256sum webui/human_fall_preview/{human_fall.js,human_fall_lib.js,human_fall_lib.test.js,index.html}` 四项与 `evidence/2026-10-03_gl04_r5/claude_r5_baseline_sha.txt` 完全一致）；HEAD `cbd0be1c86a1051a9a5800dfb7263f842896e1e6`；恢复锚点 [R5 CODEX_REVIEW](evidence/2026-10-03_gl04_r5/CODEX_REVIEW.md) 与 [R6 工单](../AI_PROMPT_GL04_OPENCODE_R6.md)。R6 服务 BLOCKED 55.313 秒超时/exit1 事实维持；恢复后由 Codex 先 ≤1 分钟无工具 probe，不重启服务、不并行第二写入者、不换模型/DB/认证/全局配置。浏览器反例整理并保存在 [R5/browser_01](evidence/2026-10-03_gl04_r5/browser_01/)（14/15 为 source-unknown 仍 upright 反例图），不覆写。

- 2026-10-03（登记时刻，Asia/Shanghai）：Codex 在 GL-04 R5 独立复审的浏览器复核阶段报额度耗尽（用户原话："你已达到使用上限。升级套餐或充值额度以继续，或在 03:34后重试"，并指令 Claude Code 顶替）。Claude Code 按 CLAUDE_STANDBY.md 顶替其全部角色（编排/独立复审/状态收口），不写生产代码。HEAD `cbd0be1c86a1051a9a5800dfb7263f842896e1e6`（master）；活动工单 GL-04/R5 复审进行中；恢复锚点：R5 回传（returns/GL-04.md 末段 SUBMITTED）+ Codex 已完成的 SHA-256 记录与独立复跑通过结果（会话口述：41 运行时检查、2 legacy 消费者检查、48 lib 检查全过）。当前源码 SHA-256：lib.js `2788e71f…ff946`，fall.js `d2e3278e…6bc139`，lib.test.js `77e9cce9…055d3d`，preview index.html `6e687d95…8cd62f`（与回传单表 Git blob SHA 逐项匹配，无提交后源码变化）。无活动实现写入者。Claude Code DONE 清单：已读 WORKFLOW/DISPATCH 顶行/GL04_ACCEPTANCE v1/R5 回传/CLAUDE_STANDBY；SHA 已核；未触生产代码。


### 正式接回登记 / 2026-10-03 Codex 接回

- **接回时间**：2026-10-03 19:13:45 +08:00（Asia/Shanghai）。
- **原因**：用户本轮确认 Codex 额度恢复，并明确终止 Claude Code 顶替。
- **本提示词时刻核得 HEAD**：master / cbd0be1c86a1051a9a5800dfb7263f842896e1e6。
- **当前活动工单/轮次**：GL-I03 / R1 草稿复核待派工；GL-I02 / R1 路线3已收口，GL04真实DPR仍NOT_RUN。
- **唯一恢复锚点**：[CODEX_HANDOVER.md](CODEX_HANDOVER.md)（七节完整交接包）。
- **角色**：此刻起 Codex 恢复唯一生效编排/派工/独立复审/状态收口角色；Claude Code 顶替终止。唯一生产 writer 保持 OpenCode CLI opencode-go/deepseek-v4.1-flash，default DB，无隔离库。
- **接回门槛**：接着逐项核用户十文件SHA及完整读取交接包；任何不一致先停查源，不启动派工。未执行reset/checkout/clean/commit/push、设备或冻结支线操作。
### Codex 接回核查完成与本轮状态 / 2026-10-03 20:01:34 +08:00

接回登记后已完整读 CODEX_HANDOVER.md 七节、WORKFLOW v2；master / cbd0be1c86a1051a9a5800dfb7263f842896e1e6 与用户十项 SHA 全匹配，独立结束仍保持。Claude Code 顶替已终止，Codex 唯一编排/派工/独审/收口。

GL-I03 R1 清洗草稿、唯一 GLI03_ACCEPTANCE.md v1、阶段一诊断390.344秒/exit0/无生产写入、Codex设计门PASS已完成。首次实施59.266秒exit0但tool-calls终止、外部技能自动审批拒绝、上下文120139，没有实现者SUBMITTED；新紧凑同Go Flash/defaultDB提示已备，尚未执行：新probe55.078秒超时/真实exit1，当前服务BLOCKED，停止、不重试、不切modelDBauth、无writer。事实见 evidence/2026-10-03_gl_i03_r1/CODEX_BLOCKED.md 与 codex_review_01/CODEX_REVIEW.md；不是算法失败轮次。

真实两参数变体 sampled1193仍ground_degenerate：828角度/2height拒、evaluated0，ROI诊断法向与已审up_axis约52.27°。K04 REAL candidate BLOCKED；不调整用户先验/冻结门，不改历史路线3。407/2默认回归与24独立旧探针通过，仅为安全基线。生产十SHA/原1997保护文件/旧证据/Windows软链表示保持，外部human_limb六新增保留。GL04真实DPR环境无可用控制仍NOT_RUN/正式不合并，GL05设备/部署/采集/网络/HR冻结。

后续恢复先新≤1min指定模型/defaultDB无工具probe，成功才用 AI_PROMPT_GLI03_OPENCODE_R1_RESUME.md 单writer三文件实施并独审；native ponytail入口不更改权限。辅助export挂起已停止确切自建进程，未假称导出/压缩成功，仅以SQLite mode=ro核指定session实际模型，不读credential不改DB。
## Codex GL-I03 R1本次继续开发恢复门 / 2026-10-03 20:23:34 +08:00

用户“好的继续开发”授权本次恢复检查：13_resume_before_manifest基线2304文件、master/cbd0be1与接回十SHA一致，无活动writer。仅一次14_resume_service_probe，55.047秒超时/真实exit1，stdout/stderr/session事件空，立即BLOCKED不自动再试、不换modelDBauth，生产实现未派发。

只读CLI日志本次run=cb195cf5停在配置加载，无模型stream；前次08的run=b79ea463另发现内部session及Go上游“An active OpenCode Go subscription is required to use Go models.”拒绝，补证见15_readonly_boot_logs.json，不能把它说成本次请求/当前账号状态，也不改旧空stdout证据。没有新的自动审批拒绝；旧外部技能拒绝为历史。root本次只写流程/本轮新证据，未写生产代码。

唯一GLI03_ACCEPTANCE v1条目结果维持：K01/K02/K05与显式矩阵NOT_RUN；K03默认/K06范围/P01/P06既有证据PASS；K04 SYNTH NOT_RUN/REAL BLOCKED、B01 BLOCKED、D01/D02 NOT_RUN。SHA未变旧407/2与24探针仍适用，不为服务失败重跑。范围外.mirasim/limb_server.log及human_limb两源码外部变化保留不回滚。最新记录：[15_RESUME_BLOCKED](evidence/2026-10-03_gl_i03_r1/15_RESUME_BLOCKED.md)，紧凑RESUME提示保持具体可派，需先恢复指定通道、freshprobe后才实施/独审。GL04真实DPR/正式页与GL05设备边界不变，未ACCEPTED。
## Codex GL-I03 R1开发 / OpenCode独立二审与研究计划修订 / 2026-10-03 21:17:09 +08:00

用户授权Codex开发、OpenCode二审，并要求边研究判断归纳反思优化计划。root已落实三生产文件后停写：wrapper显式config入口、独立YAML只0.05/8、新集中tests；默认/emit/manifest/人工选择/source/physical/exclusive保持，冻结数学/原config/原tests/data/UI/driver不改。实际完整读取ponytail源C:/Users/30680/.codex/skills/ponytail/SKILL.md。27probe12.781秒exit0/PROBE_OK恢复指定Go Flash/defaultDB；28独立二审408.547秒exit0/finish stop，实际模型/会话SQLite mode=ro核验，native技能路径.config/opencode/skills/ponytail/SKILL.md。

独审逐ID：K01/K02/K03/K05/K06/P01/P02/P03/P05/P06 PASS；K04 SYNTH PASS/REAL BLOCKED，P04 SOFTWARE PASS/REAL BLOCKED；B01 BLOCKED、D01/D02 NOT_RUN。软件范围无FAIL/无需返工，整单未ACCEPTED。独立415fall/2follow、新8methods/对抗CLI/真实默认80和变体1193拒绝证据完整；三SHA首尾同，合法wrapper变化fddeeee0...26322c8/newconfig16c9d983...44cd49aa/newtests6433fa21...d948eccb，其余接回9冻结SHA保持。最新[收口](evidence/2026-10-03_gl_i03_r1/32_CLOSEOUT.md)/[二审](evidence/2026-10-03_gl_i03_r1/opencode_second_review_01/00_review.md)，自验/助手复核/独审分别署名，不伪装角色。

研究推翻三个假设：细采样不能解52°先验差；WHAT_IF负X/ROI法向仍搜索截断保守拒（精炼1块/ambiguous false，不等于真实双地面）；直接对best算三holdout都fail且89帧偏差稳定。历史方程角度正X53.0643°/负X2.74724°，旧正X2.7°记录追加纠错不覆写；未替换批准先验或ROI/阈值。已查9月30实际SDK enable/六零，但不能证明10月2日163621录制配置。新版计划先source坐标/录制身份，再局部几何和验证污染，再受控搜索完整性，不盲调采样、筛验证点自证或重采集。研究25/26/30原始JSON与[计划](evidence/2026-10-03_gl_i03_r1/research_01/27_PLAN_REVISION.md)和31归纳已成具体证据。

29scope二审期间主线源码/data/UI无漂移，外部limb代码/日志变化保留；src/CMakeLists.txt root lstat一致，二审差异序列化不当造成的drift文字不当真实修改。当前无生产writer/审核进程，未commit/push/reset/checkout/clean/部署/采集/设备/网络、GL05/正式合并。用户最新研究授权优先，后续语义变更用具体证据/计划/验收记录承接，不由旧模板机械阻断，也不伪报physics。

2026-10-04 Codex接回GL-I05 R1：fresh probe14.718秒exit0，指定Go Flash/defaultDB二审987.890秒exit0/stop，session ses_efd6ab110ffeW3TtBoZU04eyAW。C01/C02/C03/C06/E01 FAIL，C04/C05/E02/S01 PASS；Q01/Q03/Q05/Q08/Q09 FAIL，其余Q PASS；B01/B02 BLOCKED，D01/D02 NOT_RUN，未ACCEPTED。收口evidence/2026-10-04_gl_i05_r1/09_CLOSEOUT.md。用户继续授权同项R2，Codex唯一研究writer，只新2026-10-04_gl_i05_r2，旧提交/生产/输入/旧证据只读。


## 2026-10-04 GL-I05 R2 Codex最终独审收口

C01–C06/E01–E02/S01/Q01–Q10 PASS，B01/B02 BLOCKED，D01/D02 NOT_RUN；整单未ACCEPTED。唯一GLI05_ACCEPTANCE.md v1、收口evidence/2026-10-04_gl_i05_r2/31_CLOSEOUT.md、最终指定Go Flash/defaultDB二审opencode_second_review_02/00_review.md。实际最终probe10.891s/exit0，复验155.906s/exit0/stop，session ses_efd29d375ffeh5FIoGvw4SS2G2；29_revalidation_session.json核实际provider/model，首尾76 SHA与13检查器SHA不变。原940.140s算法二审自身检查器覆盖偏差从原始CLI流恢复27脚本版本/26命令输出，新编号一次执行复验后才收口S01/Q10，不掩盖历史。38case同序列正确、六synthetic dominant正例、源点351255行精确匹配；Python3.8 AST通过，冻结代码不变复用423/2回归。无writer、无新FAIL、不派R3；只离线研究与证据工具，不生产接入/部署/采集/网络/driver，GL04/GL05边界保持。


## 2026-10-04 GL-E01 R1独审收口

GLE01_ACCEPTANCE.md v1：A01–A05/S01/Q01–Q06 PASS，B01仅原bag→bin→NPZ来源链PASS；B02物理BLOCKED，D01 NOT_RUN，D02 DPR环境BLOCKED。用户继续主线后用既有SSH只读恢复原bag，89frames/4372400points/全量bytes与XYZ及headers精确对应，既定bag time round6原义保持；不回填旧NPZ/旧GL-I05当时来源未核字段。指定Go Flash/defaultDB probe11.468s/exit0，独审1099.531s/exit0/stop，session ses_efcf6b467ffewHbmcPqpeFNz16（15_review_session.json）；source/decoder/scope首尾不变；无新部署/采集/driver/网络配置/算法设备测试。timestamp逐点f64→f32最大数值误差0.007811已独立测得，不声称单位/微秒精度/同步；header精确保持。收口evidence/2026-10-04_mainline_evidence_r1/17_CLOSEOUT.md；GL-I05软件PASS保持，当前来源缺口已补，录制外参/ROI身份与GL04真实DPR仍待证据。
