# P03 R1 Codex 独立终审提示（最终判断 / 复查 / 提交）

2026-10-05。P03 回放自动配平 R1 已由作者 Claude Code 实施并自验 SUBMITTED（作者对抗性自审已修 2 缺陷 + 1 披露，详见报告 §复审记录）。本提示词派发 **Codex 独立终审**：核对范围、逐 ID 复现核心行为、判定是否 ACCEPTED / REWORK / BLOCKED，并写正式复审报告 + 更新验收表状态。**Codex 是编排者/复审者，不是第二 writer；不写生产代码。**

## 0. 前置读取（按顺序，不要跳）

1. `docs/human_fall/WORKFLOW.md` v2 —— 第 4 节「对全表集中独立复审」、第 5 节「缺陷与新需求分开」
2. `docs/human_fall/DISPATCH.md` —— 当前活动覆盖、ponytail 强制要求、修改与运行边界
3. `docs/human_fall/tickets/P03_replay_auto_leveling.md` —— 工单背景与范围
4. `docs/human_fall/P03_ACCEPTANCE.md` —— **唯一验收 v1**，固定 ID P03-A/B/C/D/E + S01 + D01
5. `docs/human_fall/evidence/2026-10-05_p03_auto_leveling_r1/00_diag.md` —— 作者诊断
6. `docs/human_fall/evidence/2026-10-05_p03_auto_leveling_r1/12_REPORT.md` —— 作者自验 + 对抗性自审修复记录
7. `docs/human_fall/evidence/2026-10-05_p03_auto_leveling_r1/14_MANIFEST.json` 与 `13_SHA.txt` —— 提交基线 SHA
8. `docs/human_fall/GLW01_ACCEPTANCE.md` —— GL-W01 基线（auto 不应破坏手动路径）
9. `docs/human_fall/evidence/2026-10-04_p02_four_roi_r1/08_REPORT.md` —— R2 联合 TLS 锚点（pitch 26.623°）

**不注入所有历轮配平对话**；上下文只读本单与直接前置。

## 1. 审查基线与范围核验

### 1.1 基线
- 起始 HEAD：`3fc1338`（作者声明）
- 提交范围：`pc_apps/human_replay/` 内
  - 改：`leveling.py`、`leveling.js`、`leveling.html`、`replay.js`、`leveling_test.py`、`LEVELING_README.md`
  - 新：`leveling_lib.py`、`leveling_auto_test.py`
  - 证：`evidence/2026-10-05_p03_auto_leveling_r1/`
  - 文档：`P03_ACCEPTANCE.md`、`tickets/P03_replay_auto_leveling.md`、`tickets/INDEX.md` 增量行、`AI_PROMPT_P03_CLAUDE_R1.md`、本提示词

### 1.2 范围越界检查（硬不通过项）
- **不得改**：`driver/`、`src/human_fall_detection/`、`webui/human_fall/`、`annotator/`、`captures/`、生产外参字段
- **不得做**：commit/push/reset、console exe 重打包、设备/采集/部署/网络操作
- **若越界**：直接 REWORK，写明越界文件，不继续逐 ID

### 1.3 SHA 首尾核对
- 审查开始前读一次实际文件 SHA（`sha256` 对清单里每个源码文件），与 `13_SHA.txt`/`14_MANIFEST.json` 对照
- 审查结束再核一次；若中途变了（外部写入），受影响证据失效，重新验证后再出结论

## 2. 逐 ID 独立审查（必须全部跑完，不得第一项 FAIL 就停）

### P03-A · 自动域检测
**独立复现要求**：
- 跑 `python -B -W error -m unittest leveling_auto_test -v`，必须 5/5 PASS
- 额外独立核验：对 `cap_20261004_202456` 与 `cap_20261004_203349` 真实 session，直接调用 `detect_ground_domain` 取候选平面 pitch，与 R2 26.623° 差值是否 <1.5°
- 对抗性检查：
  - 给一个主面 n_z 接近 0.84（门下方）的点云 → 必须 `ground_auto_candidate_invalid` 或同类 reason，不得静默 fallback
  - 给一个 d=0.5m（明显不在 [.8,1.8] 区间）的平面 → 必须拒绝
  - ROI 数量：必须 ∈[3,8]，每边 ≥5cm，互不重叠（检查 rects 交叉）
- **关键反模式**：作者自审修过 DEFECT-1「ROI 算在估计系而非名义系」—— 独立验证 `detect_ground_domain` 返回的 regions 坐标语义是否与 `freeze_domain` 的名义 display 系一致（可通过：构造已知名义系点云 → detect → 看 regions 的 XY 是否在名义系预期位置）

### P03-B · 负路径显式
- 独立构造三个负例（n_z 不足 / d 越界 / 连通域不足 3 块），检查每个都抛或返回带明确 reason 的 invalid，而非空列表/None/静默
- 前端 `leveling.js` 对 auto 失败响应的渲染分支：读源码确认失败态不阻塞手动路径切换
- **不允许**：为 PASS 降阈、裁尾、调 RANSAC 阈值

### P03-C · 回放消费
- 读 `replay.js` 源码，定位 `__load_session_sid` 里 fetch leveled_latest + 应用 transform 的注入点，核对：
  - 注入点在 `build_geometry` **之前**（否则几何不生效）
  - transform 应用是一次性改 `S.buf_f32`，不逐帧重算
  - **失败静默回落**：fetch 失败/404/无 transform 时，`S.buf_f32` 不变，回放照常渲染
  - 旧 session 无 transform 时行为与改动前一致
- 跑 `leveling_test.py` 的端到端 HTTP 子段（作者声明 `_replay_auto_e2e`），确认：
  - `POST /api/leveling/run` auto payload → job ready
  - `GET /api/leveling/leveled_latest?sid=<sid>` → 返回含 R/t 的 200
  - `GET /api/leveling/leveled_latest?sid=nonexistent` → 404
- **反模式**：作者自审修过 DEFECT-2「leveled_latest 不核 manifest SHA」—— 独立验证：手动篡改某 job 的 transform.json 一字节，leveled_latest 必须跳过该 job、返回 404 或下一合法 job（不得返回被篡改的 transform）

### P03-D · 一致性锚点
- 三法（TLS/SVD/RANSAC）在 auto 模式下是否与 GL-W01 手动路径使用同 seed 20261001 / 同 thr 0.05 / 同 861 迭代 —— 读 `run_job` 代码，确认 auto 分支没有偷偷改配置
- 对真实 session，auto job 三法结果与 R2 联合 TLS 的 pitch/roll/d 差值如实报告（不设新物理门）；在 report.json 里能找到这些数值

### P03-E · 既有回归不破
- 独立实跑：
  - `python -B -W error -m unittest leveling_test -v` —— 必须全过（作者说 4 tests）
  - `node pc_apps/human_replay/human_replay_lib.test.js` —— 必须全过（作者说 45 tests）
- 手动路径字节级保留：给一个 manual 请求（旧 6 字段 payload，regions 4 个），结果与 GL-W01 原行为一致（job 结构、report 字段、导出目录都不变）
- **不得**：auto 分支改动污染 manual 路径的默认值、检查顺序或导出文件名

### S01 · 范围/页面/逻辑自验
- ponytail SKILL 路径声明存在于报告
- Node+Python 检查器对非法请求显式拒绝：构造一个缺 `mode` 的 auto 请求、构造一个含自填域 `extra: "hacked"` 的请求、构造 SID 含路径穿越 `../` 的 leveled_latest —— 必须 400/404/拒绝，不得 silent accept
- 指定独审（本审）、真实 browser 都须在最终结论里单列 NOT_RUN 或实际执行情况，不得冒称

### D01 · 边界
- 核查无设备/采集/部署/网络/driver/commit/push/reset/生产外参写入
- console exe 未重打包
- D01 = NOT_RUN（预期，不扣分）

## 3. 重点对抗方向（作者自审已修，你再核一次）

1. **坐标语义身份混淆**：regions 到底在哪套 display 系（名义 vs 估计）？作者声称已修 DEFECT-1，**独立反证**：构造名义 pitch=45°、真实平面 pitch=30° 的点云，看 detect 返回的 regions 是 45°系还是 30°系。
2. **完整性降级**：leveled_latest 是否核 manifest SHA？作者声称已修 DEFECT-2，**独立反证**：把某 job 的 `tls/transform.json` 改一个字节，请求 leveled_latest，必须拿不到该 transform。
3. **静默失败变自动降级**：replay fetch leveled_latest 失败不阻塞是设计，但如果 fetch 返回了格式错误的 JSON（比如 500 页面），replay.js 会不会把 undefined 当 transform 用？读源码核错误处理分支。
4. **auto 改了 manual 的默认行为**：检查 `validate_request`、`run_job` 的分支条件，确保 manual 请求（无 `mode:"auto"`）走的代码路径与 GL-W01 版本逐行一致。

## 4. 交付物（全部落到 evidence 目录）

在 `docs/human_fall/evidence/2026-10-05_p03_auto_leveling_r1/codex_final_review_01/` 下：

- `00_review.md` —— 主报告，含：
  - 角色：`CODEX_FINAL_REVIEW` / `INDEPENDENT`
  - 状态：`SUBMITTED`（你只做审查，ACCEPTED/REWORK 由你判定但状态字段写 SUBMITTED 等用户确认）
  - 判定：**逐条 ID** 给 PASS / FAIL / NOT_RUN / BLOCKED，附：要求来源、触发方式、实际结果、预期、根因（若 FAIL）、最小返工建议（若 FAIL）
  - 范围越界检查结果
  - 首尾 SHA 核对结果
  - ponytail SKILL 实际读取路径
  - 独立执行的命令与退出码（Python tests、Node tests、独立核验脚本）
  - 真实 browser / 设备 / 部署 = NOT_RUN 声明
  - 最终整体建议：**ACCEPTED / REWORK / BLOCKED**（你给建议，不直接改验收表的"当前结果"列）

- `01_sha_before.txt` / `02_sha_after.txt` —— 首尾 SHA
- `03_python_tests.log` / `04_node_tests.log` —— 原始测试输出
- `05_independent_checks.py`（如有） —— 你写的独立核验脚本，不得改动源码树
- `06_scope_diff.txt` —— `git diff --stat` 范围快照

## 5. 硬规则

- **不复用作者测试作为独立证据**：作者测试通过是基线，你必须至少做 3 项独立检查（坐标语义、SHA 完整性、手动路径不变），不能只复跑作者的 test suite 就说 PASS
- **不得改任何生产/测试源码**：复审只读 + 写 evidence 目录
- **不得把作者结论当独立证据**：每条结论必须有你自己执行的命令或源码阅读支撑
- **发现 FAIL 不停止**：继续完成其余 ID 的审查，集中反馈
- **不新增需求**：发现的问题必须映射到已有验收 ID；超出 v1 范围的改进建议写在报告末尾"后续建议"节，不混入 PASS/FAIL 判定
- **不切模型/DB/auth**：用指定配置，失败就 BLOCKED 并写原因
- **ponytail 是硬要求**：开工前读 SKILL.md 并记录路径

## 6. 完成后

停写。在 `REVIEW_LOG.md` 追加一条 P03 R1 Codex 终审记录（一句话结论 + 报告路径），**不要**直接改 `P03_ACCEPTANCE.md` 的「当前结果」列（那需要用户确认）。等用户确认后再更新验收表状态与 DISPATCH 活动覆盖。
