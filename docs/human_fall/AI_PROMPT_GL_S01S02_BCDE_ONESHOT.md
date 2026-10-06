# GL-S01 / GL-S02 / GL-B～GL-E 独审 → 修复 → 提交（一条龙）提示词

> **用途**：把本文件整体发给执行 AI（建议全新独立会话）。本文档即提示词本体。
>
> **授权**：用户 2026-10-05 明确授权本批六单“按流程独审 → 范围内修复 → 提交（commit，不 push）”。除本授权外，一切照 `AGENTS.md` 与 `docs/human_fall/WORKFLOW.md` 执行。
>
> **基线**：分支 `master`，HEAD `b190834`（HF-12 已入库）；不得改写历史，禁止 `reset/checkout/clean`。
>
> **环境**：Windows（PowerShell），仓库根 `D:\Code\ldiar`。若经 OpenCode CLI 派发，先做一次 ≤1 分钟无工具 probe，记录 provider/model/exit。

---

## 0. 角色与任务

你是本批任务的**唯一执行者**（单 writer，串行处理六单，不并行）。任务分三段：

| 阶段 | 内容 | 是否写生产代码 |
|---|---|---|
| **A 独立复审** | 对六单逐条核对验收表，独立复跑测试与边界检查，出逐 ID 结论 | 否（只读） |
| **B 修复** | 仅对复审 FAIL 的条目做判据范围内最小修复 + 就地复验 | 是（最小改动） |
| **C 提交** | 全部通过后按三组提交到 git（只 commit，不 push） | 否（git 操作） |

---

## 1. 范围（六单）

| 单号 | 内容 | 唯一验收表 | 回传 | 证据目录 |
|---|---|---|---|---|
| GL-S01 | 地面身份层 v2（`lowest_floor_sheet_v2`） | `docs/human_fall/tickets/GL-S01_floor_sheet_v2.md` + `docs/human_fall/GLS01_ACCEPTANCE.md` | `docs/human_fall/returns/GL-S01.md` | `docs/human_fall/evidence/2026-10-05_gl_s01_r1/` |
| GL-S02 | 细粒度 ROI v3（`lowest_floor_sheet_v3_fine_roi`） | `docs/human_fall/tickets/GL-S02_fine_roi_selection.md` + `docs/human_fall/GLS02_ACCEPTANCE.md` | `docs/human_fall/returns/GL-S02.md` | `docs/human_fall/evidence/2026-10-05_gl_s02_r1/` |
| GL-B | 质量/可信度（AGL-B） | `docs/human_fall/tickets/GL-B_adaptive_quality.md`（即 v1 验收表） | `docs/human_fall/returns/GL-B.md` | `docs/human_fall/evidence/2026-10-05_agl_b_r1/` |
| GL-C | 三估计器一致性仲裁（AGL-C） | `docs/human_fall/tickets/GL-C_adaptive_consensus.md` | `docs/human_fall/returns/GL-C.md` | `docs/human_fall/evidence/2026-10-05_agl_c_r1/` |
| GL-D | 时间稳定/六状态/安全保持（AGL-D） | `docs/human_fall/tickets/GL-D_adaptive_temporal.md` | `docs/human_fall/returns/GL-D.md` | `docs/human_fall/evidence/2026-10-05_agl_d_r1/` |
| GL-E | transform / 只读离线应用（AGL-E） | `docs/human_fall/tickets/GL-E_adaptive_offline_leveling.md` | `docs/human_fall/returns/GL-E.md` | `docs/human_fall/evidence/2026-10-05_agl_e_r1/` |

**生产文件（本批涉及，未入库）**

- GL-S01：`pc_apps/human_replay/floor_sheet.py`、`floor_sheet_test.py`
- GL-S02：`pc_apps/human_replay/floor_roi.py`、`floor_roi_test.py`
- 两者共享集成：`pc_apps/human_replay/leveling.py`、`validation.py`、`LEVELING_README.md`
- GL-C：`src/human_fall_detection/core/adaptive_ground/consensus.py` + `tests/test_agl_c_consensus.py`
- GL-D：`src/human_fall_detection/core/adaptive_ground/controller.py`、`temporal.py` + `tests/test_agl_d_controller.py`
- GL-E：`src/human_fall_detection/core/adaptive_ground/transform.py` + `tests/test_agl_e_offline.py`
- 注：GL-A/GL-B 的代码（estimators/quality/selection/contracts 与两测试）已随 HEAD 入库；本批仍须复审 B 的回传与证据。

**已知状态**：六单作者自验均为 SUBMITTED；外部独立复审未做；设备/物理一律 NOT_RUN。GL-B 回传自述实现期修复过 1 处本单缺陷；GL-S02 回传含 223757 三法与打包验证证据。

---

## 2. 开工前必做

1. 读：根 `AGENTS.md`、`docs/human_fall/WORKFLOW.md`（顶部现行授权）、`docs/human_fall/RETURN_TEMPLATE.md`。
2. 加载 `ponytail` skill（**full**），并记录实际读取路径（复审与修复均要求）。
3. 逐单只读必要上下文（工单/验收表/回传/证据），不做全量历史重读。
4. 记录基线：`git rev-parse HEAD`、`git status --short`、本批相关文件 SHA256。
5. 确认无并发写者：GL-S02 等条目曾标“实施中”，若发现范围文件在复审期间被外部修改，停止相关单并如实记录，**不覆盖**。

---

## 3. Phase A：独立复审（只读）

### 3.1 通用要求

- 判定**只认本会话复跑结果**；作者日志仅作对照，不得只凭回传文字判 PASS。
- 每条验收 ID 给：**PASS / FAIL / NOT_RUN / BLOCKED**，附命令、退出码、日志路径。
- 设备/实机/物理条目一律 NOT_RUN/BLOCKED，不得用合成结果顶替。
- 只读：不改生产代码/测试/验收表/旧证据；复审产物只写复审目录与 `REVIEW_LOG.md`。
- **独立性如实声明**：若你与写者同模型/提供方或曾参与实现，必须在报告头部写明（如“同族独立会话”），不得冒称完全独立。

### 3.2 每单必查清单

- [ ] 验收表版本与判据未被改动（对照回传记录的 SHA）
- [ ] 实现文件 SHA 与回传一致；范围 diff 无越界（工作树本就有其它在办脏文件，只核对本单范围）
- [ ] 专项测试 + 全量回归**独立复跑**（条数、退出码）
- [ ] 契约层：分层返回（v1/v2/v3；A→B→C→D→E 链）、失败语义、只读性、additive 字段、旧行为逐字兼容
- [ ] 自写最小反例/边界探针（不要照抄作者断言）
- [ ] 结论与旧证据不冲突；旧记录零覆盖

### 3.3 输出

- 每单：`docs/human_fall/evidence/<该单证据目录>/review_01/00_review.md` + 日志（命令原文、stdout、exit code）。
- 格式模板：`docs/human_fall/evidence/2026-10-05_hf12_r1/opencode_review_01/00_review.md`（HF-12 独立复审，含逐 ID 表/观察/限制）。
- 汇总：`docs/human_fall/REVIEW_LOG.md` 按现有格式追加。

### 3.4 参考命令（先核回传/证据里的实际命令，再复跑）

```powershell
# GL-S01
python -B -W error -m unittest discover -s pc_apps/human_replay -p floor_sheet_test.py -v
python -B -W error -m unittest discover -s pc_apps/human_replay -p "*_test.py" -v

# GL-S02
python -B -W error -m unittest discover -s pc_apps/human_replay -p floor_roi_test.py -v
python -B -W error docs/human_fall/evidence/2026-10-05_gl_s02_r1/12_packaged_verify.py
# 223757 golden 脚本（04_golden_223757.py / 06_run_job_223757.py）：只读复跑，以证据里的实际入口为准

# GL-B～E（core）
python -B -W error -m unittest discover -s src/human_fall_detection/tests -p "test_agl_*.py" -v
python -B -W error -m unittest discover -s src/human_fall_detection/tests
```

---

## 4. Phase B：修复（仅对 FAIL）

- 只修 FAIL 对应的**既有判据内**缺陷；不新增需求、不改判据/阈值/验收表版本。
- 修复前先写诊断：根因、受影响入口/消费者/状态转换（按 WORKFLOW v2 要求）。
- 新证据放 `docs/human_fall/evidence/2026-10-05_<单>_r2/`（或该单既有轮次命名）；**绝不覆盖 r1 旧证据**。
- 回传按 `RETURN_TEMPLATE.md` 追加 R2 段（根因/修复/复验/限制）。
- 修复后就地复验（专项 + 全量），记录中写“**就地复验（同会话）**”，不得称“二次独立独审”。
- 一轮修复后仍 FAIL：停该单，如实标 REWORK/BLOCKED，继续其它单，不无限循环。
- 修复期间不得触碰：HR-W03（`human_pipe_lib*`、`human_detect.*`、`human_replay_lib.py`）、HF-12 文件、GL-V01/P03、`.mirasim/`、`ML/`、`文档收集（人工）/`、`src/CMakeLists.txt`。

---

## 5. Phase C：提交（已授权；只 commit，不 push）

先逐文件核对改动归属；**禁止 `git add -A` / `git add .`**；提交信息用短中文；每次 add 后先 `git diff --cached --stat` 核对。

### 提交 1：GL-S01 + GL-S02

```powershell
git add pc_apps/human_replay/floor_sheet.py pc_apps/human_replay/floor_sheet_test.py `
  pc_apps/human_replay/floor_roi.py pc_apps/human_replay/floor_roi_test.py `
  pc_apps/human_replay/leveling.py pc_apps/human_replay/validation.py `
  pc_apps/human_replay/LEVELING_README.md `
  docs/human_fall/tickets/GL-S01_floor_sheet_v2.md `
  docs/human_fall/tickets/GL-S02_fine_roi_selection.md `
  docs/human_fall/GLS01_ACCEPTANCE.md docs/human_fall/GLS02_ACCEPTANCE.md `
  docs/human_fall/returns/GL-S01.md docs/human_fall/returns/GL-S02.md `
  docs/human_fall/evidence/2026-10-05_gl_s01_r1 `
  docs/human_fall/evidence/2026-10-05_gl_s02_r1 `
  docs/human_fall/evidence/2026-10-05_gl_floor_diag_r1
```

建议信息：`GL-S01/S02：地面身份层 v2 与细粒度 ROI v3（含独审/修复记录）`

### 提交 2：GL-B～E

```powershell
git add src/human_fall_detection/core/adaptive_ground/consensus.py `
  src/human_fall_detection/core/adaptive_ground/controller.py `
  src/human_fall_detection/core/adaptive_ground/temporal.py `
  src/human_fall_detection/core/adaptive_ground/transform.py `
  src/human_fall_detection/tests/test_agl_c_consensus.py `
  src/human_fall_detection/tests/test_agl_d_controller.py `
  src/human_fall_detection/tests/test_agl_e_offline.py `
  docs/human_fall/returns/GL-B.md docs/human_fall/returns/GL-C.md `
  docs/human_fall/returns/GL-D.md docs/human_fall/returns/GL-E.md `
  docs/human_fall/evidence/2026-10-05_agl_b_r1 `
  docs/human_fall/evidence/2026-10-05_agl_c_r1 `
  docs/human_fall/evidence/2026-10-05_agl_d_r1 `
  docs/human_fall/evidence/2026-10-05_agl_e_r1
```

建议信息：`AGL GL-B～E：质量/一致性/时序控制器/离线变换（含独审/修复记录）`

### 提交 3：登记与复审记录

```powershell
git add docs/human_fall/WORKFLOW.md docs/human_fall/tickets/INDEX.md docs/human_fall/REVIEW_LOG.md
```

建议信息：`GL 登记：WORKFLOW/INDEX/REVIEW_LOG 同步`
（WORKFLOW 顶部追加本批授权与结果一行；旧条目不动。）

### 提交纪律

- 提交后 `git show --name-only --format="" HEAD` 核对；工作树其余脏文件原样保留。
- **不 push、不 reset/checkout/clean、不部署、不采集、不换模型/DB/auth。**
- 若某文件混有范围外改动（如 HR-W03），停下报告，不整文件带入。

---

## 6. 结束汇报（必须）

1. 逐单结论表：ID 汇总、PASS/FAIL、修复项、就地复验结果。
2. 命令与退出码、新增证据路径。
3. 三个提交的哈希与文件数。
4. 未闭合清单：设备/物理 NOT_RUN、REWORK/BLOCKED 项。
5. 未做事项：未 push、未部署、未采集、未改判据。

---

## 7. 停止条件（发现即停并报告）

- 需要改判据 / 新增需求 / 跨单设计决策；
- 无法最小修复，或一轮修复后仍 FAIL；
- 本单范围文件被外部并发修改；
- 服务/权限/环境故障（区分代码失败与服务失败，不伪报）。
