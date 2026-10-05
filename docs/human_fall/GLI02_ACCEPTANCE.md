# GL-I02 真实离线候选标定可行性验收 v1

建立 2026-10-03。依据计划C（`evidence/2026-10-03_next_stage_plan_r1/PLAN_REVIEW.md` §C）：“适配器必须先于真实标定生成”。GL-I01 R1 软件已 PASS（REVIEW_LOG 2026-10-03）。主线推进：**用已适配的真实 163621 NPZ 在本地离线产出 candidate ground-plane calibration artifact（schema v1），并把现场协议 freeze 前需要人工决断的地面选择以 draft 形式落地**——全程本地、不连板、不采集、不部署、不切 config、不启 GL05、不动 GL02 生命周期。

派工/独审：Claude Code（CLAUDE_STANDBY 顶替）。生产写者：唯一 OpenCode `opencode-go/deepseek-v4.1-flash` default DB。两阶段派工：阶段一仅诊断并 stop（00_diag.md），阶段二实施（提交 + 回传统代码 SHA）；未 ACCEPTED。

## 范围冻结

- 不改 `core/ground.py`、`core/calibration.py`、`core/capture_input.py`、`scripts/prepare_capture_input.py`、constrained 命令语义、GL02 calibration 生命周期、calibration schema v1
- 不改 driver / webui / 正式页 / `config/` / capture 采集 / `captures/remote/`
- 不部署、不切页面、不启动新 ROS 节点、不启用 IMU 融合 / confirmed
- 维持现有 GL-I01 R1 SHA

## 验收条目（J = 新增软件 + 文档，B = source证据，D = 设备/物理）

| ID | 要求/可观察预期 | 检查入口/层级 | 结果 |
|---|---|---|---|
| J01 | 在本地离线对真实 `captures/remote/cap_20261002_163621` 走 prepare+adapted CLI，得到 candidate geometry calibration artifact（schema v1）。artifact 中 ground.status = "candidate"、physical_verified=false、所有 provenance 与 GL-I01 R1 兼容。**绝不**写入 GL02 生命周期或改 ground_local 派生状态机 | 真实命令 0 / 复核 artifact JSON | **SYNTHETIC PASS / REAL NOT_RUN**（R1 路线3：协议-场景矛盾冻结真实 fit；synthetic adapted NPZ→candidate 已 PASS；详见 `evidence/2026-10-03_gl_i02_r1/codex_review_01/13_route3_closeout.md`） |
| J02 | 真实运行完全只读 + 不动 `captures/remote/`；评估/选择过程中的中间产物（评估 JSON、ROI draft、extraction audit）都是**本单独有命名空间**，不能覆盖他人产物、不能写进 capture 目录 | 操作后 `captures/remote/...SHA` 仍基线 | **PASS**（R1） |
| J03 | synthetic fixture 与真实数据严格分开：synthetic cal artifact 全程标注 `synthetic=true`、`source=synthetic_fixture`；真实 candidate artifact 不混用 synthetic fixture 数据 | 两产物并存且来源字段合规 | **PASS**（R1） |
| J04 | 现场协议冻结前的 ROI/拟合区/3 个 validation 区域分布/up_axis/sensor_height_interval 一律以 draft JSON 形式记录（`capture_selection_draft.json` 或等效），供 Codex/用户决断；缺选择/区/先验时**不自动** fallback 选地面 | draft 文件与审查对照 | **PASS**（R1） |
| J05 | 新增 wrapper/evaluation entry 只调用 GL-I01 R1 公开 API（prepare_npz / load_adapted / gate_selection / build_manifest），不得新增 ROI 语义；遇到 frame/units/adapter/manifest/support 与本单不兼容的输入一律非零 + 无 artifact，所有 GL-I01 R1 严格拒绝语义保持 | 走 GL-I01 边界组、probes 复跑仍 24/24 | **PASS**（R1） |
| J06 | 白名单：新增/修改只限于 (a) 一个 thin evaluation script（新文件、调用既有 API）、(b) `tests/`、(c) `docs/human_fall/GLI02_*`、(d) `returns/GL-I02.md`；GL-I01 四文件 SHA 不变 | diff + SHA 对照、本轮范围审计 | **PASS**（R1） |
| B01 | 原袋 width/height/original_count 仍缺，不生成 cited 原袋 row 索引 | source 层 | BLOCKED（维持） |
| D01 | 真实物理、设备、板端、性能、GL05、部署、采集、网络 | 未启动、未授权 | NOT_RUN |
| D02 | GL04 真实 DPR / 正式页 / GL-I02 相关浏览器验证 | 不属本单 | NOT_RUN |

## 操作/消费者矩阵（诊断逐行映射到实际函数/赋值顺序，实施前点对点证明）

| 行 | 输入×消费者 | 关联 ID | 结果 |
|---|---|---|---|
| N01 | 163621 → prepare_npz → load_adapted → draft 选择 → adapted CLI `--constrained …` → exclusive 输出 | J01/J02/J04 | **SYNTHETIC PASS / REAL NOT_RUN（R1 路线3）** |
| N02 | 163621 缺 fit/validation 选择 → adapted CLI | J04/J05 | **PASS (R1)** |
| N03 | 同名候选 artifact 已存在 | J01 | **PASS (R1)** |
| N04 | synthetic fixture → adapted CLI | J03 | **PASS (R1)** |
| N05 | 与 GL-I01 R1 回归（62）+ Codex 合成探针（24）共跑 | J05/J06 | **PASS (R1)** |
| N06 | `--capture-dir`、`--validate-region-*` 等本单 entry 与非 adapted 输入 | J05/J06 | **PASS (R1)** |
| N07 | ROI/validation 分布/高度间隔 draft（人工决断表） | J04 | **PASS (R1)** |

## 阶段一诊断停写约束（同 GL-I01 R1，防止先写后诊断）

实现者在此单开工前先读：`docs/human_fall/GLI02_ACCEPTANCE.md` v1（本表）、`docs/human_fall/GLI01_INPUT_CONTRACT.md`、`evidence/2026-10-03_gl_i01_r1/07_diag_revision.md` §2/§4、`PLAN_REVIEW.md` §C；写 `docs/human_fall/evidence/<date>_gl_i02_r1/00_diag.md`：**只**逐行映射验收表 + 矩阵到实际现有函数/调用点/赋值顺序、列写生产差异最小化列表、狮子山 ponytail 读者路径。**不准**写生产 / tests、**不准** commit、`STOP`。

Codex 读 00_diag 并核 SHA 与范围未动，才发阶段二实施工单。否则 REWORK_DESIGN。

## 阶段二实施约束

- 唯一生产 writer，先新 probe；同 session 继接；ponytail 实际读取（full/lite 报）；白名单动其它文件即停
- 每验收条目跑本单 test + GL-I01 R1 回归 + Codex 前 24 探针 + constrained 自验 fit 命令
- 回传统 `returns/GL-I02.md`：实际 SHA、命令、退出码、PASS/FAIL/NOT_RUN、延时/draft 文件路径；闭 B01/D01/D02
- 完成后 Codex 独立复审（不动产代码，只 R 复现 + 命令重跑 + 独审计），结论进 REVIEW_LOG

## 边界

依据：计划C §C + WORKFLOW v2 / CLAUDE_STANDBY 顶替。GL04 DPR、GL05、正式页合并、设备/采集/部署是另一个工作流，本单不授权、不暗示、不衔接。
