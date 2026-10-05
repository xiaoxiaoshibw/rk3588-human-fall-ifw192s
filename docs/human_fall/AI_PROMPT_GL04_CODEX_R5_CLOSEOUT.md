# Codex GL04 R5 收口与续进：读入现状、复审收口、浏览器复核、获审后并入正式页

你是唯一生效编排/独立复审/状态收口角色，按 WORKFLOW v2 及 2026-10-01/02 用户授权行动：可直接派 OpenCode CLI `opencode-go/deepseek-v4.1-flash`、default DB、自动跟进与独立复审；派工前先做 ≤1 分钟 probe，不用隔离 DB，不换模型。生产代码单写入者仍 OpenCode，你只复审/收口，不写生产代码。工作区 `D:\Code\ldiar`。

先读（不凭旧聊天）：根 `CLAUDE.md`、`AGENTS.md`；`docs/human_fall/WORKFLOW.md`（顶几行最新授权优先）、`DISPATCH.md`、`GL04_ACCEPTANCE.md` v1、`GROUND_LEVELING_PLAN.md`、`deployment.md`、`returns/GL-04.md`（最后 R5 段）、`evidence/2026-10-03_gl04_r5/{PLAN_REVIEW.md,00_diag.md,claude_r5_baseline_sha.txt}`、`evidence/2026-10-02_gl04_r4/CODEX_REVIEW.md`、WORKFLOW §4–6 复审与收口规则。只写代码者（OpenCode）开工前必须读 ponytail SKILL.md 并在回传声明；你不写码不发生此义务。

当前事实（磁盘核对，2026-10-03）：

- R5 实现已由 OpenCode 完成：`evidence/2026-10-03_gl04_r5/03_opencode_meta.json` exit 0、模型 `opencode-go/deepseek-v4.1-flash`、default DB；`returns/GL-04.md` 第 5 段 SUBMITTED。改的是 preview 四文件中的三（`index.html` 本轮未改），core/config/driver/正式页未动。
- r5 证据目录内已有 `90_codex_results.json`（41 项全 PASS）、`92_codex_consumers_results.json`（2 PASS）、`93_codex_exits.json`（三个 harness exit 0）、`91_codex_lib.txt`、`claude_*` 重跑件。这些是你（先前会话）独立复跑的中间产物，但**尚无正式 R5 CODEX_REVIEW.md、REVIEW_LOG 与验收表结果列未更新**。
- 真实浏览器复核（V04/M03/M11、六图、真实 DPR）在 R4 后仍是 NOT_RUN，是收口主要缺口。
- V10 生产 build_snapshot 缺显式 R/t/support → 结构性 BLOCKED（不改 core/topic）；D01 设备/物理未授权 → NOT_RUN。此两条按既有分层处理，不挡软件收口结论本身。

按序执行：

1. **R5 独立复审收口**。核对 R5 源码 SHA 与 `claude_r5_baseline_sha.txt`/returns 一致；对预防文件被后续改动，以现场 SHA 为准重跑你的 90/92/91 独立 harness（node，改后必跑，未改且SHA一致可引用，但须写明引用依据）；44 断言 lib 测试须 exit 0。对 R4 的 5+2 条 FAIL 反例逐条确认闭合。产物写 `evidence/2026-10-03_gl04_r5/CODEX_REVIEW.md`，逐 V01–V10/D01 与 C01–C15 给结论，标注哪些仍 NOT_RUN 及原因。不覆写 r1–r4 任何证据。
2. **若仍有 FAIL**：按既有授权直接派 OpenCode R6（同一验收 v1、设计前置矩阵按 WORKFLOW §1/§5 连续失败规则执行；R5 已做过计划/责任审查，本轮按缺口写清单）。不做多写入者、不换模型。
3. **若软件条目全 PASS**（V10/D01 分层除外）：执行**真实浏览器复核**——按 returns 第 5 段给出的入口 `?synthetic=normal|tilted|no_extrinsics&fixture=<r5 fixtures 路径>` 跑三场景×source/ground 共六图，rotate/zoom/resize，断连/silent expiry 恢复；真实 DPR 你环境切不动就保持 NOT_RUN 并写明，不虚报、不以纯函数检查冒充浏览器证据。截图与指标落证据目录（新子目录或 r6 证据目录，不覆盖旧的）。
4. **浏览器复核通过后并入正式页**：按用户 2026-10-03 询问卡确认的预览页边界裁决执行——预览为隔离开发/验收面；正式页冻结至获审，获审后**以同版本特性集并入 `webui/human_fall/` 当前源码，保留外部 Q/E/帮助等外部变动，整文件不覆盖**。若该裁决你在确认链路上查不到记录，先复述裁决要点向用户确认，再动正式页。并入由 OpenCode 写入（同样 ponytail 强制），写前后 SHA 入证据；并入后你的复审引用 V09 既有策略：正式源码未变部分复用 R7 回归，不重跑 326/7/12+2；变更部分逐项回原断言并补检查。此步**只同步源码，不部署**——部署只走 GL-05 的 `deploy_human_fall.sh` release 管线，本单不放行。
5. **收口**：按 WORKFLOW §6 更新 `REVIEW_LOG.md`（R5 一节）、`GL04_ACCEPTANCE.md` 结果列（加 R5 结论块，判据 v1 不动）、`DISPATCH.md` 顶部当前入口。若全部软件 PASS，宣布 GL-04 软件收口、V10/D01 分层待办，**不启动 GL-05/部署/采集**，后续等用户授权。

硬边界：不 commit/push/reset/checkout user dirty files；不改 core/config/driver/其它 webui 页面/旧证据目录/原 44 断言语义；不板端联网、不部署、不采集；工作树用户改动（含正式页 Q/E/帮助、HR 提交、根目录重组）保留不覆盖。证据目录按轮次新命名，`evidence/2026-10-03_gl04_r5/` 内只补正式复审件，不删既有项。回传/报告按 `RETURN_TEMPLATE.md` 与 REVIEW_LOG 惯例，逐条PASS/FAIL/NOT_RUN/BLOCKED 给证据路径，不得以"实现者自验 exit 0"代替独立复审。
