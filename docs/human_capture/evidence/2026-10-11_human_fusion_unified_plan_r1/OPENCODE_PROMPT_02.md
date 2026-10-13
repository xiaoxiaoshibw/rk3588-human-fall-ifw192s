这是用户要求的统一算法开发计划定点复审，指定opencode-go/deepseek-v4.1-flash/defaultDB。只读，禁止edit/write/bash/task/网络工具，不实施算法，不切provider/model/DB/auth。

请第一步实际用read读取 C:/Users/30680/.codex/skills/ponytail/SKILL.md；不能仅声明已经读过。再读取本工单HC README顶部、AGENTS约束。

审核v2冻结计划：docs/human_capture/evidence/2026-10-11_human_fusion_unified_plan_r1/PLAN_SUBMITTED_02.md，ACCEPTANCE_SUBMITTED_02.md，SUBMISSION_02.json，REVIEW_RESPONSE_01.md，SOURCE_CHECK_02.json，OPENCODE_PROVENANCE_01.json。首次裁定READY，但有文档小修与两条错误事实判断，需复核而非照抄前次。

只需重点核以下改动，其他架构沿用首次完整审核，避免重读大目录和自己的活动日志：
1. 基线表现在列全8个有资格场景（S1+7人体会话），加总510 PERSON、候选504/127/6、track491/112/19。SOURCE_CHECK_01原本xgb_rows有9会话，不是4；SOURCE_CHECK_02简表足以核算，S9标UNKNOWN不合计。
2. 物理限制统一PHY01。
3. pipeline retention真实调用链必须读取 sidequests/human_fusion_lab/core/engine.js offset=490 limit=45 和 offset=310 limit=30（按工具约定offset是行号）；FUSION先pipe_ctx.tracker.tick，a_tracks入bank，再Unique更新输出。不得沿用首次“PIPE只服务pipechain”的错误解释。
4. v2图retention重新进入PA/PB聚类，非直入union；共同BG入口和classifier前提案不被破坏。
5. 无工具probe tool_calls=0；正式审核只读权限true与实际工具read/glob/grep；没有取配置文件/凭据。第一次技能声明缺实际read日志，本次实际读取后记录。
6. 算法仍DEV01 NOT_RUN，人工资格DEV02 BLOCKED、设备D01 NOT_RUN、PHY01 BLOCKED；规划READY不等于系统ACCEPTED。

逐P01～P09给PASS/FAIL/NOT_RUN/BLOCKED；P02最后整树对账与P09编排收口尚未完成可NOT_RUN。指出仍存在的可复现问题，不扩成已实现算法审核；回复两条首次事实误判的复核结论。结尾给READY/REWORK_REQUIRED/BLOCKED并写 REVIEW_COMPLETE。全文输出stdout，编排者保存；不写文件。不要浏览BASELINE巨大JSON或重新读取自己正在产生的jsonl，已有PROVENANCE/SOURCE_CHECK简明证据足够。
