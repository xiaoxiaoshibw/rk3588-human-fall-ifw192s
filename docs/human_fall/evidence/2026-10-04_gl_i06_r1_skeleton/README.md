# GL-I06 R1 skeleton / README

2026-10-04。本目录是 R1 skeleton 轮的计划骨架证据。本轮只交付 Markdown / JSON schema 草案；未运行实验、未实现算法、未启动 probe/独审。

- 唯一验收表：[GLI06_ACCEPTANCE.md v1](../../GLI06_ACCEPTANCE.md)（A01–A07 / S01 / B01 / D01 / Q01–Q06）。
- 设计依据：[GROUND_LEVELING_ALGORITHM_DESIGN.md](../../GROUND_LEVELING_ALGORITHM_DESIGN.md)（算法路线、采用门、条件分支）。
- 本轮提示：[AI_PROMPT_GLI06_CODEX_R1.md](../../AI_PROMPT_GLI06_CODEX_R1.md)。
- 流程规则：[WORKFLOW.md](../../WORKFLOW.md)（单 writer、ponytail 硬要求、停写规则）。

文件一览：

- `00_diag.md` — 范围声明（什么不做）、R0 账本 shadow 计划要素、variant 命名要点。
- `00_SCOPE.md` — GLI06 v1 全条目与本骨架的 [ ] PLANNED / [ ] RESERVED / [ ] NOT_RUN 计划映射（真实状态不回填，以唯一表为准）。
- `99_STOP_WRITE.md` — 本目录范围内新增文件的 SHA256、branch/HEAD、git status 摘要、未运行/未实现/未 probe 声明。
- `planning/variant_naming.md` — variant_id 命名草案，逐条映射设计 §3 行。
- `planning/rejection_ledger_schema.md` — 逐关卡拒绝账本 JSON schema 草案。
- `planning/oracle_design.md` — 独立 oracle 设计草案（标量 GT、三域分开、ties/链/late 不吞）。

已知主线状态（仅引用，不改变）：GL-I06 的 R1 主线已由 Codex 提交并在 `docs/human_fall/returns/GL-I06.md` 登记指定独审 PASS（软件条目），B01 BLOCKED / D01 NOT_RUN。本 skeleton 计划与既有提交的合并、重排或作废，全部由 Codex/用户在下一步裁定；本目录不做该裁定。

终态：停写完成于 `99_STOP_WRITE.md`；等待用户/Codex 决定是否进入下一步。不 commit、不 push、不启动任何 OpenCode 会话。
