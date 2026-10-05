# GL-I06 R1 skeleton / 99_STOP_WRITE

2026-10-04。本文件是本轮 stop-write 记录：写完即停，不 commit、不 push、不启动 OpenCode 会话。

## 基线

- Branch：`master`（本目录工作树当前 HEAD 分支；未创建任何新分支、未 checkout、未 merge）
- HEAD sha：`cbd0be1c86a1051a9a5800dfb7263f842896e1e6`
- 记录时刻（UTC）：2026-10-04T07:13:42Z 附近（同一 git status 采集时刻）

## git status 摘要（采集于写文件前，之后未再改动仓库其它文件）

- ` M`（modified）：30 项 —— 包含 `.gitignore`、`AGENTS.md`、`CLAUDE.md`、`docs/human_fall/*`（CLI_RECOVERY/DISPATCH/GL03_ACCEPTANCE/GROUND_LEVELING_PLAN/README/REVIEW_LOG/WORKFLOW/returns/GL-03.md/tickets/*）、`docs/sidequests/REVIEW.md`、`pc_apps/human_replay/*`、`src/CMakeLists.txt`（Windows 下 catkin 软链接的已知表示，不修）、`src/human_capture/scripts/capture_server.py`、`webui/*` 等。
- ` D`（deleted）：4 项 —— `build_ros1.sh` / `build_ros2.sh` / `open_webui.bat` / `rk.txt`。
- `??`（untracked）：110 项 —— 包括 `.mirasim/`、`ML/`、`docs/human_capture/tickets|returns 下 HR-06..09 与 INDEX`、`docs/human_fall/AI_PROMPT_*.md`（GL03 R3..R7、GL04 R1..R7、GL04 CODEX R5 CLOSEOUT、GLE02/GLE01、GLI01..GLI06、GLP01、PA01）、`docs/human_fall/{CLAUDE_STANDBY,CODEX_HANDOVER,GL04_ACCEPTANCE,GLE01_ACCEPTANCE,GLE02_ACCEPTANCE,GLI01_ACCEPTANCE,GLI01_INPUT_CONTRACT,GLI02_ACCEPTANCE,GLI02_CANDIDATE_PLAN,GLI03_ACCEPTANCE,GLI04_ACCEPTANCE,GLI04_TASK,GLI05_ACCEPTANCE,GLI05_TASK,GLI06_ACCEPTANCE,GLP01_ACCEPTANCE,GLP01_MESSAGE_CONTRACT,GROUND_LEVELING_ALGORITHM_DESIGN,GROUND_LEVELING_NEXT_STAGE_PLAN}.md`、`docs/human_fall/evidence/*` 历史 run_root 等。
- 上述基线全部来自既有历史工作，非本轮所改；本轮新增的 7 个文件（本目录 6 个 + 本文件）尚未被 git 追踪（`??` 状态将随本文件落盘后新增）。

## 本轮新增文件 SHA256（本目录内，UTF-8 落盘即算）

| 文件 | SHA256 |
|---|---|
| `00_diag.md` | `16b412d79288ba858c1995c160645b081796d9933d32bc74277eb8b8cee54b84` |
| `00_SCOPE.md` | `fb68ae496290073efa7936b71e9e28f93faa7dd1dbd9ac28a92d1f632b50acd2` |
| `README.md` | `ec442e93a4f7a8ea426c0db9a89113a596962a7504dddfb6bfd0a3e3ec095ea1` |
| `planning/variant_naming.md` | `beb74e83190600eec6dcb2fd83d6ecafce52c11b48abdf065602c06656760b6b` |
| `planning/rejection_ledger_schema.md` | `adfece8e0e295c67a4a0f44a23957ff0f8bf5b9f0678244f6b4a8783081aeaac` |
| `planning/oracle_design.md` | `955a146cbb1b4a5cefd5644c9232b048b6fd98a9632e7d1719c6563b3914834a` |
| `99_STOP_WRITE.md` | 本文件（写后 SHA 冷启动不在此自引用，可由复核方现算） |

## 声明

- **未运行**：本轮未运行任何算法实验、未运行任何测试、未执行任何 Python；只写 Markdown / JSON schema 草案。
- **未实现算法**：本轮未创建任何 Python 源码或测试，未在新 run_root 下复制/重写 `core/` 任何函数；`src/human_fall_detection/core/ground.py` 未被读取其实现体。
- **未启动 probe**：本轮未调用任何 OpenCode CLI、未发起 probe / 二审 / 独审 / 会话；S01 与 Q06 的 probe、独审部分在本骨架保持 RESERVED / NOT_RUN。
- **不冒状态**：本轮不预填、不声称任何 GLI06 v1 条目的 PASS / FAIL；所有 PLANNED / RESERVED 仅是计划映射，真实状态以 GLI06_ACCEPTANCE.md 及 `docs/human_fall/returns/GL-I06.md` 为准。
- **不 commit / 不 push**：本目录新文件保持 untracked；工作树其余既有修改（30 M / 4 D / 110 ??）为历史基线，本轮不动。

## 下一步等待

本骨架完成后停止，等用户 / Codex 决定：(a) 是否承认 R1 主线已由既有 R1 提交+独审覆盖，本骨架 R0/R1 计划作废或收窄为R0 账本环补充；(b) 是否把条件分支（irls_huber / full_fit_refine / 更后 ring）作为真正的下一轮并另开实施提示；(c) 是否恢复 ponytail + probe 流程另派独审。以上任何一项不在本轮。
