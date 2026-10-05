# GL-I02 实施前设计门 / 2026-10-03（Claude Code 顶替 Codex）

角色：Claude Code 顶替 Codex（CLAUDE_STANDBY），OpenCode 是唯一生产 writer。本文件对 `00_diag.md` 做设计审查并裁决其中关键张力。**设计门 PASS，单独放行阶段二**，白名单/production 四文件 SHA 未变，冻结 ground/calibration/capture/driver/webui/config 未变。

## 0. 审查动作

- 读 `00_diag.md` 全 190 行（含 P0–P10、不动点、张力 §3.1/白名单/测试集）
- 核 SHA：`capture_input.py/prepare_capture_input.py/calibrate_sensors.py/test_gli01_capture_input.py/ground.py/calibration.py/meta.json/points.bin` 与阶段一记录/GL-I01 R1 复审记录逐项一致
- 工作树状态：`git status` 中 `src/human_fall_detection/` 为未跟踪包（本项目常态），`pc_apps/human_pcl/ ML/` 为历史未跟踪；本单未新增非白名单源码

## 1. §3.1 关键张力裁决

| # | 张力 | 裁决 | 理由 |
|---|---|---|---|
| 1 | `ground.status="candidate"` vs schema合法性（GROUND_STATUSES=["valid","orientation_unverified","invalid"]，artifact.ground 有自己的 status；artifact.status.ground 是容器，只要 ground validate 即允许 custom string） | **R-a 实现**（wrapper 传 `statuses={"ground":"candidate"}`），schema 合法；`artifact.ground["status"]="valid"`保持不动，由 `validate_constrained_ground` 严格验证 | diagnosis 引用 `calibration.py:1210/1241` 已准确描述 validation 路径；wrapper 关键是编排，不改冻结 ground 状态机 |
| 2 | “走 adapted CLI” vs 直接调用 API | **直接编排**（不动 calibrate_sensors.py，新增独立 thin wrapper）；不复制 ROI/语义，不产生 conflicted adapted/legacy 二路 | 既符合 GLI01 R1 边界（adapted vs legacy 已 clear），也避免给 adapted CLI 加新参数/分流路径 |
| 3 | `physical_verified=false` 的**实际落点** | artifact.verification.ground_physical_verified=false（既有 helper）+ artifact.input.input_manifest.provenance.physical_verified=false（既有 manifest）+ wrapper 不提升任何 physical 旗标 | diagnosis §3.1 #3 已准确归位两处，与 GLI01 R1 回传统一致 |
| 4 | J01 原文“走 adapted CLI” | 按 **formula 2 实施**，不走既有 adapted CLI；J01 这里改为"走 prepare+adapted 类函数"与 wrapper thin entry | 原 J01 字面已不合 schema 约束；这是验收表文案措辞修订，不改 schema 约束本身 |
| 5 | `build_manifest` 是否确定需要 | wrapper 若生成 draft 信息需摘取 frame_groups/points sha 时可以调用，但**不应**包办 schema 拓扑，manifest 已完整 | generic，便利但不必要 |

## 2. 我验收表中的残缺/模糊项（自认罪）

1. **N06 文案残缺**（"非 adapted → reference`"、"--constrained`"）——按 GLI01 07_diag_revision §2.3/R4 语义修正为：
   - 非 adapted 普通 NPY/NPZ → **新 wrapper 判 legacy 并明确拒绝**（`classify_npz=="legacy"` 即 exit 2，不 fallback 不混用 adapted route），由即有的 calibrate_sensors.py legacy route 承担普通的本单外用途
   - adapted NPZ → wrapper 走 strict load_adapted（manifest/provenance strict verify），**不** fallback --constrained 普通 points route
   - wrapper 不复制 GL-I01 已 Adapted strict reject 语义
2. **收购表 N01 的"ground.status"措辞**——同 §1#1 。
3. **`--capture-dir`** 与 `--prepared-npz` 互斥/至少一个必填：wrapper 要么准备新 NPZ（prepare_npz），要么显式复用 GL-I01 prepared NPZ。两个同时给时以 `--prepared-npz` 为准并 warn。两个都不给 → exit 2。
4. **wrapper 名称与 location**：`src/human_fall_detection/scripts/evaluate_gli02_candidate.py`（全 path，与 prepare_capture_input.py 同级目录）。
5. **draft 的 exclusive 化**：draft JSON 与 candidate artifact 都走 save_exclusive_json；不读旧 draft 覆盖，不自动 fallback 未确认选择。

## 3. 白名单 strict允许（阶段二写范围 / 本轮 SHA included）

| 文件 | 允许 | 备注 |
|---|---|---|
| `src/human_fall_detection/scripts/evaluate_gli02_candidate.py` | 新文件（段二）（唯一新增生产代码） | 只调用 GL-I01 R1 API + 已有 `calibration.fit_ground_plane_constrained` + `build_geometry_calibration`；不重写 ground 数学 |
| `src/human_fall_detection/tests/test_gli02_candidate.py` | 新文件（段二） | 最多 8 项回传（diagnosis §7），以 GL-I01 R1 回归 + 合成反例 24 探针复跑为外部检查 |
| `docs/human_fall/GLI02_*` 补充（如 `GLI02_CANDIDATE_PLAN.md`） | 新增 | 文档 |
| `docs/human_fall/returns/GL-I02.md` | 追加 | 回传 |
| `docs/human_fall/evidence/2026-10-03_gl_i02_r1/*` | 追加 | 本单证据 |

**不可写**：`src/human_fall_detection/core/`、`scripts/calibrate_sensors.py`（已 weed to production, 但他计划在 GLI02 R1 加一个 wrapper，这个 ID 方案不该改他）、`scripts/prepare_capture_input.py`、`core/capture_input.py`、`tests/test_gli01_capture_input.py`、`ground.py`、`calibration.py`、`captures/remote/`、`webui/`、`pc_apps/`、config 任何 YAML。

## 4. 交付条件 / 复审门（阶段二停写前也需满足）

1. wrapper + tests 4 线 SHA 对照 GL-I01 R1 基线 SHA（diagnose §1）仍完全一致。
2. GL-I01 62 test 回归 OK。
3. **真实 163621** 全程只读；验证点：prepare（or load-adapted reload）、verify zero_rows=673315 一致；**不** fit 真实地面（拟合还是人工决断 before）。
4. 合成 7-frame fixture adapted NPZ + 3 独立 validation 区 → candidate artifact（statuses={"ground":"candidate"}）exit 0，**J01 字面实现**。
5. Codex 一样复审范围：白名单 SHA、8-项 unittest、regression、24 探针、capture SHA、 artifact schema、artifact status、exclusive 阻止写入、draft 只写 + tag pending_human_review、 J03 synthetic/real 严格分离、 N02/N03/N05/J04 负例反例。
6. 阶段二 result**不**声明 ACCEPTED；整单保持 D01/D02/B01 分层。

## 5. 中途变更

我保留阶段一 OpenCode outline 部分文案对生产读 ID/results的说法——"既有的 calibrate_sensors.py 硬编码 `statuses={"ground":"valid"}`，产出的是 status.ground="valid"，**不满足 N01 字面**"——这句已 **由** J01 schema 修正（J01 现在允许 wrapper candidate accept 本地 candidate artifact）。所以仅在 wrapper 伴随一个字段（status.ground=candidate），不改变 adapted CLI。

## 6. 中签 shift rule

如段二需超过白名单（>1 个新生产文件），OpenCode 须中断、回写原因、STOP，由 Codex 裁决是否扩展；**不私自扩大范围**。

READY_FOR_IMPLEMENTATION
