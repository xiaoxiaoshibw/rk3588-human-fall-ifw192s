# HFUS-TCMS-02-ADAPTIVE-LEVELING-PLAN 回传（仅设计与计划）

## 本轮信息

- 工单 / 轮次 / 执行者 / 时间：HFUS-TCMS-02-ADAPTIVE-LEVELING-PLAN / r1 / 本会话 OpenCode（唯一文档 writer）/ 2026-10-18。
- 验收表路径 / 版本 / SHA：`docs/human_fall/evidence/2026-10-18_hfus_tcms_02_adaptive_leveling_plan_r1/PLAN_ACCEPTANCE_V1.md` v1（AL-P01–AL-P13），SHA256 `9d874376cc7c345a743d9a2c6f9d970bc91a2a1fe4c09f9622eac1545802e135`。
- 执行方式 / 实际会话与模型：本机离线单会话；未跑数据、未切模型；无网络/训练/设备/采集/部署。
- 状态：SUBMITTED（仅设计与计划文档）；实施 L0–L5 与实施验收 NOT_RUN；Codex 正式复审 NOT_RUN；非 ACCEPTED。
- 起始 branch/HEAD：`master` / `c9c4ee421cb0c8a3e4590b8f5730828b093c759a`；工作树起始已脏；未做 reset/checkout/clean/commit/push。
- ponytail SKILL.md 实际读取路径：`C:/Users/30680/.config/opencode/skills/ponytail/SKILL.md`（本会话实际读取，full 强度）；策略：RESEARCH（未知能力设计）+ 规划；不实施。
- 输入基线：同目录 `INPUT_BASELINE.json`（14 件引用文件 SHA-256，本会话重算；JSON 已解析校验通过）。

## 集中诊断与根因覆盖

| 缺口 | 事实来源（本会话核对） | 设计中的处置 |
|---|---|---|
| 一次性配平无自动重建路径 | S3 REPORT：`S3_LOCAL` 由 C3D_03 一次性构造；二次配平被拒 | T1 新会话 bootstrap + M0 v(n)/T(n) 版本化 |
| `MAP_UNCERTAIN` 无恢复路径 | TCMS-02-PLAN §1：失配只暂停、不恢复 | T2 受控 REACQUIRE + AnchorSet 锚层 |
| 距离图易被误用为约束 | E0 §2（0.17 锁定率/0.02° 近连续）；S2 对照（DIMG_01 3/4 < C3D_03 4/4） | P2：可选提案、默认关闭、预登记对照门 |
| 逐帧重配平漂移风险 | GROUND_LEVELING_PLAN 原句 | P4：epoch 化、慢更新、只对新帧生效、可回退 |
| 人体污染对齐 | TCMS-02-PLAN §1（不许人体进全局 ICP） | P5：估计层只吃 bg_match 行；锚与前景零关联 |

## 实际变更

| 文件 | 用途 | SHA256 |
|---|---|---|
| `…/2026-10-18_hfus_tcms_02_adaptive_leveling_plan_r1/DESIGN_V1.md` | 设计正文 | `d11ea7685bc520a99d70039157d8dd32c2943b90d6488efdd43a78bb75928eeb` |
| `…/PLAN_V1.md` | 计划正文 | `48796a1e8f8f0573ebb6a1ff2166d34d0d06781c689b2d5e7822dd245fadb6bb` |
| `…/PLAN_ACCEPTANCE_V1.md` | 唯一验收 | `9d874376cc7c345a743d9a2c6f9d970bc91a2a1fe4c09f9622eac1545802e135` |
| `…/PLAN_CHECK.md` | 逐 ID 自检 | `cd8657ddc351da4178e8002d21eb74bb1e3945f1e491db78cffb31d829f6bb8d` |
| `…/INPUT_BASELINE.json` | 引用基线（14 件重算） | `0c7f603be45df13f754a12f9b295dbc015e371d8c220d97b6d9f6bdcfb2e8383` |
| `docs/human_fall/returns/HFUS-TCMS-02-ADAPTIVE-LEVELING-PLAN.md` | 本回传 | 新建 |
| `docs/human_fall/WORKFLOW.md` | 顶部条目追加 | 只追加，旧字节保留 |
| `docs/human_fall/REVIEW_LOG.md` | 末尾记录追加 | 只追加，旧字节保留 |

未改 data/、旧证据、源码、配置、模型、GT；无 Git 写。

## 逐条验收

| ID | 自验 | 说明 |
|---|---|---|
| AL-P01 交付物齐备 | PASS | 五件证据 + 回传 + WORKFLOW/REVIEW_LOG 条目 |
| AL-P02 三触发与非目标 | PASS | DESIGN_V1 §1 |
| AL-P03 原则可回溯 | PASS | DESIGN_V1 §2；来源 SHA 见基线 |
| AL-P04 架构三层 | PASS | DESIGN_V1 §3.1–§3.4（含「只吃 bg_match 行」） |
| AL-P05 状态机/版本/回退 | PASS | DESIGN_V1 §3.3（六态 + 转移表 + last_good） |
| AL-P06 距离图角色 | PASS | DESIGN_V1 §2-P2/§4/§7-D2 |
| AL-P07 验证设计 | PASS | DESIGN_V1 §6（设备/物理保持 NOT_RUN/BLOCKED） |
| AL-P08 边界与不重叠 | PASS | DESIGN_V1 §5；PLAN_V1 §10 |
| AL-P09 开放决策 | PASS | DESIGN_V1 §7 D1–D5（含默认建议） |
| AL-P10 实施 NOT_RUN | PASS | PLAN_V1 §6 全行 NOT_RUN |
| AL-P11 只写文档 | PASS | 见上表；WORKFLOW/REVIEW_LOG 仅顶部/末尾追加 |
| AL-P12 回传与 ponytail | PASS | 本文件与「本轮信息」 |
| AL-P13 独立复审如实 | PASS | 全文登记 Codex 正式复审 NOT_RUN、非 ACCEPTED |

## 未闭合与限制

- 实施 L0–L5 全部 NOT_RUN，须用户另行派发并另立唯一验收；本计划不自动开工、不自动进入 S07/S08。
- 开放决策 D1–D5 待用户输入（会话内慢更新默认关闭、距离图默认关闭、锚层范围、变换自由度、REACQUIRE 启动方式）。
- 设计中的门为方向性拟案，实施派发时预登记冻结；不得先跑后调。
- 地面身份/物理高度/人体身份/效果/独立 D 保持 UNKNOWN/BLOCKED；设备/采集/部署/训练/网络 NOT_RUN。
- 与 AGLF（主线）只引用不合并；GL-A～I 维持自身 PLAN_READY/NOT_RUN；四 ROI/1.14m 口径不动。

## 交给 Codex 独立复审

- 设计入口：`docs/human_fall/evidence/2026-10-18_hfus_tcms_02_adaptive_leveling_plan_r1/DESIGN_V1.md`；计划与验收同目录；基线 `INPUT_BASELINE.json`。
- 复审重点：P1–P6 是否都有真实出处且无过度外推；六态状态机与「只对新帧生效/可回退」是否自洽；距离图「默认关闭 + 预登记对照门」是否足以防止误用；与 AGLF/S07 的边界是否清晰；开放决策的默认建议是否安全（HOLD 优先）。
- 下一步：若复审认可，再由用户决定是否派发 L0；本项不自动进入 S07/S08 或任何主线节点。
