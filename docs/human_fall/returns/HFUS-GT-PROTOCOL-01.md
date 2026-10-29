# HFUS-GT-PROTOCOL-01 回传（AI-GT 正式证据类别，仅协议文档）

## 本轮信息

- 工单 / 轮次 / 执行者 / 时间：HFUS-GT-PROTOCOL-01 / r1 / 本会话（OpenCode 客户端；声明模型 opencode-go/deepseek-v4.1-flash，未独立审计）/ 2026-10-18。
- 验收表路径 / 版本 / SHA：`docs/human_fall/evidence/2026-10-18_hfus_gt_protocol_01_r1/ACCEPTANCE_V1.md` v1（GP01–GP12）/ SHA256 `094a453973f93b63aef4f4add744a9626824c017c303f7675a5d50b9bb941c4f`。
- 执行方式 / 实际会话与模型：本机离线单会话、仅文档写入；未跑数据、未切模型、无网络/训练/设备/采集/部署。
- 状态：SUBMITTED（仅协议文档）；工具实施与首批应用 NOT_RUN；独立复审 NOT_RUN；非 ACCEPTED。
- 起始 branch/HEAD：`master` / `c9c4ee421cb0c8a3e4590b8f5730828b093c759a`；工作树起始已脏；未做 reset/checkout/clean/commit/push。
- ponytail SKILL.md 实际读取路径：`C:/Users/30680/.config/opencode/skills/ponytail/SKILL.md`（本会话经 skill 工具加载，full 强度）；策略：ENGINEERING（治理/文档，复用既有 GT 工具契约，不新造实现）。
- 决定依据：用户本聊天明确决定「`AI_GT_FROZEN`（盲标 + 交叉验证 + 协议约束下的模型标注）定为正式证据类别」（2026-10-18）。

## 集中诊断与根因覆盖

| 缺口 | 事实来源（本会话核对） | 协议处置 |
|---|---|---|
| 既有 AI 标注（`AI_VISUAL_REVIEW`、gt_store draft）不可入指标，UNKNOWN 长期无法解 | S07/S07F 回传、REPLAY-FRESH fix3、TRAIN-AI01 记录 | 新增 `AI_GT_FROZEN` 类别与准入条件（协议 §2/§3） |
| 标注者与被评系统相关误差（同一盲区自证） | POSE-JITTER-01（OUTER_A/骨盆 CONFLICTING_SPATIAL_SUPPORT、std 300mm）、SKELETON-01 BLOCKED | 交叉模型验证 + 标注器合成自检包络 + 自动一致性审查（§3.3/§3.4） |
| "AI 标世界坐标"不能证明坐标系本身正确 | S03 坐标链（C3D_03→S3_LOCAL）与物理未验证边界 | 物理锚点清单 + 坐标类真值禁用 AI-GT（§4、附录 A） |
| 人审瓶颈（成本/拖延） | 超级计划风险行 | 分层复标 + 仅争议仲裁，替代全量人审（§3.3） |
| 旧记录污染风险 | WORKFLOW/RETURN 不得回填的历史纪律 | 明确不升格、不回填、不互写（§2 红线） |

## 实际变更

| 文件 | 本轮用途与修改 | 与用户原差异的区分 | 提交源码SHA |
|---|---|---|---|
| `…/2026-10-18_hfus_gt_protocol_01_r1/AI_GT_PROTOCOL_V1.md` | 协议正文（唯一当前版本） | 新增 | `cc7f959b…5be7f`（见 CHECK.md） |
| `…/ACCEPTANCE_V1.md` | 唯一验收 GP01–GP12 | 新增 | `094a4539…41c4f` |
| `…/INPUT_BASELINE.json` | 四个引用文件 SHA 基线（本会话重算） | 新增 | `d509ad30…705dce` |
| `…/CHECK.md` | 自检与交付物 SHA | 新增 | `f297944d…ea5bd` |
| `docs/human_fall/returns/HFUS-GT-PROTOCOL-01.md` | 本回传 | 新建 | 新建 |
| `docs/human_fall/WORKFLOW.md` | 顶部条目前置 | 只前置，旧字节保留 | 追加记录 |
| `docs/human_fall/REVIEW_LOG.md` | 末尾记录追加 | 只追加，旧字节保留 | 追加记录 |

未改 data/、旧证据、源码、配置、模型、GT、`docs/AI_DEVELOPMENT_POLICY.md` 正文；无 Git 写、无网络/训练/采集/部署。

## 逐条验收

| 验收ID | 类别 | 状态 | 证据 |
|---|---|---|---|
| GP01 交付物齐备 | 交付 | PASS | 本目录五件 + 回传 + WORKFLOW/REVIEW_LOG |
| GP02 证据类别阶梯 | 定义 | PASS | 协议 §2 |
| GP03 盲标 | 准入 | PASS | 协议 §3.1 |
| GP04 冻结溯源 | 准入 | PASS | 协议 §3.2 |
| GP05 交叉验证 | 准入 | PASS | 协议 §3.3 |
| GP06 标注器自检 | 准入 | PASS | 协议 §3.3、§7 selfcheck |
| GP07 自动一致性审查 | 准入 | PASS | 协议 §3.4 |
| GP08 物理锚点 | 边界 | PASS | 协议 §4、附录 A |
| GP09 允许声明矩阵 | 口径 | PASS | 协议 §5 |
| GP10 既有体系对接 | 口径 | PASS | 协议 §6 |
| GP11 边界如实 | 边界 | PASS | 协议 §7/§8、CHECK.md |
| GP12 状态如实 | 状态 | PASS | 本回传、CHECK.md |

以上为作者自验结果，不等于 Codex 验收；本工单非 ACCEPTED。

## 未闭合与限制

- 工具（`tools/ai_gt/` 四模式：label/selfcheck/crosscheck/audit）实施 NOT_RUN；标注器自检包络尚不存在，首次使用前必须先跑 selfcheck。
- 首批应用（TCMS-02 主会话+空场 purity/recall 首测、REPLAY-FRESH dev_r2 升级选项）NOT_RUN，须另行派发并另立验收。
- `docs/AI_DEVELOPMENT_POLICY.md` 正文未并入本类别（如需并入属另一次决定与另立工单）。
- 独立复审 NOT_RUN；本会话未重算全树基线（仅四件引用文件 SHA），如实声明。
- 物理锚点清单为采集建议，未执行；无设备/采集/部署授权。

## 交给 Codex 独立复审

- 现行验收表与本轮变更记录：ACCEPTANCE_V1.md + 本回传。
- 协议正文与依据：AI_GT_PROTOCOL_V1.md（§2–§5 为实质条款）；基线 INPUT_BASELINE.json。
- 自检与 SHA：CHECK.md；交付物 SHA 见表。
- 原始记录索引：WORKFLOW.md 顶部条目、REVIEW_LOG.md 末尾条目。
- 当前工单下一步：复审通过后，由用户决定是否派发"工具实施 + 首批应用"；本项不自动启动下一单。

## 2026-10-18 协议落盘与索引

- HFUS-GT-PROTOCOL-01，本会话唯一文档 writer，SUBMITTED，非 ACCEPTED。
- `AI_GT_FROZEN`（盲标 + 交叉验证 + 协议约束下的模型标注）定为正式证据类别，与 `HUMAN_CONFIRMATION` 并列；四道保障 + 物理锚点 + 允许声明矩阵；旧记录不升格不回填。
- 逐 ID：GP01–GP12 全部 PASS（作者自验）；工具/首批应用/独立复审 NOT_RUN。
- 交付入口：本目录 AI_GT_PROTOCOL_V1.md / ACCEPTANCE_V1.md / CHECK.md / INPUT_BASELINE.json；协议 SHA `cc7f959b…5be7f`。
