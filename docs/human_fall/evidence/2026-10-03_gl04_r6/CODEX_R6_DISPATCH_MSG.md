# Codex R6 恢复后派工指令 / 2026-10-03

Codex 恢复后，按以下顺序执行，不跳过。 当前无活动生产写入者，GL-04 是唯一活动工单，R6 就位。

1. 按 CLAUDE_STANDBY 冷启动读入口：WORKFLOW顶行/DISPATCH顶行/GL04_ACCEPTANCE v1/CLI_RECOVERY顶行/evidence/2026-10-03_gl04_r5/CODEX_REVIEW.md/evidence/2026-10-03_gl04_r6/PLAN_REVIEW.md/AI_PROMPT_GL04_OPENCODE_R6.md/returns/GL-04.md 末尾 SUBMITTED。
2. 现场 SHA 再核一遍，与 `evidence/2026-10-03_gl04_r5/claude_r5_baseline_sha.txt` 一致才不重启证据。
3. **先 ≤1 分钟无工具probe**：`opencode-go/deepseek-v4.1-flash` / cwd=`D:/Code/ldiar` / **default DB，不设 OPENCODE_DB**。计时起止、真实 exit、原始 stdout/stderr 写本轮证据目录 `probe_*.jsonl`；超时/失败即写 BLOCKED，不启动第二写入者，不启动生产写入者。
4. probe 通过 **唯一生产写入者提示词为** `docs/human_fall/AI_PROMPT_GL04_OPENCODE_R6.md`，提示其必须先写 `r6/00_diag.md` 才能动生产代码。范围仅限四 preview 文件 + 新 r6 证据 + returns/GL-04.md 末尾追加 SUBMITTED/BLOCKED；不改 core/config/driver/正式页/其它 webui/原 44 断言/旧证据/原数据；不 commit/push/reset/checkout/clean。
5. Codex **独审**：核对 90/92/91 旧41/2/48 及 exit0 复用、补 95/97 及全部新消费者反例、原 fixture 资格正负例；四 preview SHA 与提交回传 SHA 双重核对；浏览器真实生命周期按需另跑；不轻信实现者自验，不把 SUBMITTED 当 ACCEPTED。
6. 服务不可用回退：工作流已给：BLOCKED 登记/只读诊断/用户手动转发 R6 工单；**不换模型、不改认证/DB、不启动第二写入者**。

浏览器反例索引（只看图，不运行）：source ground unknown 仍 upright——
- `evidence/2026-10-03_gl04_r5/browser_01/14_source_unknown_upright.jpg`
- `evidence/2026-10-03_gl04_r5/browser_01/15b_unknown_upright_visible.jpg`

现场 SHA 与 2026-10-03 Claude 交接基线一致（今日再核：
- webui/human_fall_preview/human_fall.js `d2e3278e…6bc139`
- human_fall_lib.js `2788e71f…ff946`
- human_fall_lib.test.js `77e9cce9…055d3d`
- index.html `6e687d95…8cd62f`
