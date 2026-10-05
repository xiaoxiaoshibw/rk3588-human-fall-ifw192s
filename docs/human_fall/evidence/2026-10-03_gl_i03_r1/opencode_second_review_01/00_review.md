# GL-I03 R1 OpenCode 独立二审报告 / 2026-10-03

角色：Opencode CLI 指定**独立二审（只审核，不写生产源码/tests/config/状态文档）**。
本次结论：**不发现范围内软件缺陷；K04 REAL / B01 仍 BLOCKED，D01/D02 NOT_RUN，整单不 ACCEPTED。**

## 0. 真实 session / model / DB / ponytail 路径

- session：`ses_efe2d04ceffea7iUqS4WOjUxvE`（`27_probe_actual_model.json` 的探针 session 为 `ses_efe306333ffeApQq6bORmJ4vrz`）
- model：`opencode-go/deepseek-v4.1-flash`（default）
- DB：`default`（未使用 `OPENCODE_DB` 隔离库）
- 原生 ponytail skill 实际路径：`C:\Users\30680\.config\opencode\skills\ponytail\SKILL.md`（用 `skill(name=ponytail)` 完整加载；未 read 仓库外 `.codex` 技能）
- 只读约束：未写生产源码/tests/config，未更新表/WORKFLOW/README/DISPATCH/REVIEW_LOG/ACCEPTED，未切 model/DB/auth/权限，未设备/部署/采集/网络。
- 本报告与脚本只新增在本目录 `opencode_second_review_01/` 与 `%TEMP%`。

## 1. 范围与 SHA（首尾一致）

| 文件 | 提交 SHA | 审前 | 审后 |
|---|---|---|---|
| `src/human_fall_detection/scripts/evaluate_gli02_candidate.py` | `fddeeee0b4c6e014b608b64d8805b90997977b0e6eee357d6cc28f02726322c8` | 同 | 同 |
| `src/human_fall_detection/config/geometry_constrained_gli03_r1.yaml` | `16c9d983c0202bb122be300db6faf70e7415300756392569acafa7d444cd49aa` | 同 | 同 |
| `src/human_fall_detection/tests/test_gli03_candidate_override.py` | `6433fa21200d1cbae0236c3701e31a5ec7b96d6d34549279909cacb6d948eccb` | 同 | 同 |

命令：`certutil -hashfile <file> SHA256`（见运行记录）。三 SHA 与派单一致，二审期间无漂移。

范围独立核对（`04_scope_diff.py`，比较 `18_codex_before_manifest.json` → `26_codex_after_manifest.json`）：

- 生产改动仅 `scripts/evaluate_gli02_candidate.py`（changed）；
- 生产新增恰为 `config/geometry_constrained_gli03_r1.yaml`、`tests/test_gli03_candidate_override.py`；
- 冻结 `core/`、原 `config/geometry_constrained.yaml`、原 `test_gli02_candidate.py`/GL-I01 四文件、数据/driver/UI/旧证据均**无 sha 变化**；
- `external` 差异仅 `pc_apps/human_limb/*`、`.mirasim/limb_server.log`（支线，非本单生产范围）；
- `current_vs_28_drift` 仅同上外部文件 + `src/CMakeLists.txt`（Windows 软链统计不可读，符合 AGENTS.md 预期）；`src/human_fall_detection/**` 零漂移。
- 后台外部文件在二审期间被其它进程改动（`.mirasim/limb_server.log`、`pc_apps/human_limb/limb_lib.py`），均在被审范围之外，不构成本单缺陷。

HEAD/branch：`cbd0be1c86a1051a9a5800dfb7263f842896e1e6` / `master`（`28_before_second_review_manifest.json`）。

## 2. 原始命令与 exit

| # | 命令 | 结果 |
|---|---|---|
| A | `python -B -W error -m unittest discover -s src/human_fall_detection/tests -v` | Ran 415 / OK / **exit 0**（`01_full_regression.txt`） |
| B | `python -B -W error -m unittest discover -s src/human_follow_calibration/tests -v` | Ran 2 / OK / **exit 0**（`02_follow_regression.txt`） |
| C | `python -B -W error -m unittest -v test_gli03_candidate_override` | Ran 8 / OK / **exit 0** |
| D | 对抗负例 `03_adversarial_probe.py` | 见 §4 矩阵（`03_adversarial_probe.json`） |
| E | 真实 CLI 默认 | `gli02 candidate refused: ... ground_points_insufficient` / **exit 2** / 无 candidate |
| F | 真实 CLI 变体 | `gli02 candidate refused: ... ground_degenerate` / **exit 2** / 无 candidate |
| G | 真实单组 fit 直测 `05_real_fit_probe.py` | default `1214/80/insufficient`；variant `1214/1193/31 degenerate`（`05_real_fit_probe.json`） |
| H | 范围 diff `04_scope_diff.py` | 见 §1（`04_scope_diff.json`） |
| I | YAML 键比较 | `nkeys 25 25`；`diff ['max_points_per_cell','spatial_cell_m']`；`frozen==defaults True`；`defaults 0.2/4`；`variant 0.05/8` |

环境：`Python 3.12.10`，`PyYAML 6.0.3`（本机自验；非 board 3.8 真机，已用 3.8 AST 单独核对）。

## 3. 逐 ID 结果

| ID | 结果 | 证据 |
|---|---|---|
| K01 | **PASS** | 默认 None 走 `resolve_constrained_settings(None)`（wrapper:176-179）；显式路径复用 `load_config`+`resolve`（wrapper:184-189）；空串不进 fallback（wrapper:178）；坏 YAML/结构/unknown/非法值 exit2 无 artifact（C+D）。 |
| K02 | **PASS** | 变体 YAML 解析 25 键，`spatial_cell_m=0.05`/`max_points_per_cell=8`，SHA=`16c9…49aa`。 |
| K03 | **PASS** | 默认 synthetic candidate exit0；真实默认 `1214→80 insufficient exit2 无 candidate`（E/G）；415+2 回归 exit0（A/B）。 |
| K04 | **SYNTH PASS / REAL BLOCKED** | 变体 synthetic candidate 且 `status.ground=candidate`/`physical=false`/无 `ground_derived`/source 正确/输出独占（C）；真实变体 `1193 degenerate` 无 candidate（F/G）。REAL 目标未闭合。 |
| K05 | **PASS** | 变体与冻结仅两值差，其余全同；冻结默认仍 0.2/4（I）。 |
| K06 | **PASS** | 生产改动仅 wrapper + 两新文件；冻结/旧证据/原 tests 无变化；首尾三 SHA 一致（§1）。 |
| P01 | **PASS** | 真实默认单组 fit 1214 / 采样 80 / insufficient / exit2 无 candidate（E/G），冻结来源 SHA 不变。 |
| P02 | **PASS** | 默认与显式冻结同 `ground`/`status`/`verification`；重复调用不串配置；emit-draft 原义（C）。 |
| P03 | **PASS** | 显式变体 synthetic 成功；15 类负例 + 缺文件/空路径/目录/坏 UTF-8 全 exit2 无 candidate；同路径改内容下次生效；对象不污染默认；已有 output 字节不变（C+D）。 |
| P04 | **SOFTWARE PASS / REAL BLOCKED** | 变体+真实单组无 candidate 留档；无先验/frame 不符拒；capture-dir 只读语义由原 t7 覆盖（A/C/F）。REAL candidate 未产生。 |
| P05 | **PASS** | 变体 `ground.settings` 为 resolved；默认仍 0.2/4；全字典仅两值变（I）。 |
| P06 | **PASS** | 全文件 manifest 含 untracked；软链表示保留；wrapper 最小 diff；原 tests/旧证据不改；3.8 AST 与本机分离（§1）。 |
| B01 | **BLOCKED** | 原 bag width/height/original_count 源证据仍缺；本次未做物理验证，不将 export 升为物理。 |
| D01 | **NOT_RUN** | 设备/物理/性能/GL05/部署/采集/网络未授权；本机 AST/fit 不替代。 |
| D02 | **NOT_RUN** | GL04 真实 DPR 不属本单。 |

## 4. 负例矩阵（`03_adversarial_probe.py`，均 CLI 真跑）

| 用例 | 期望 | 实际 exit | candidate | stderr 尾 |
|---|---|---|---|---|
| 空缺省（None） | 0 | 0 | 是 | — |
| 显式冻结 | 0 同 ground | 0 | 是 | — |
| 空文件 | 2 | 2 | 否 | `needs a ground_constrained mapping` |
| YAML 语法 `[` | 2 | 2 | 否 | `while parsing a flow node…` |
| top 非 mapping `[1,2]` | 2 | 2 | 否 | `needs a ground_constrained mapping` |
| 缺 section | 2 | 2 | 否 | `needs a ground_constrained mapping` |
| `ground_constrained: null`/list/bool | 2 | 2 | 否 | 同上 |
| unknown key | 2 | 2 | 否 | `unknown constrained ground setting: unknown` |
| bool `spatial_cell_m: true` | 2 | 2 | 否 | `must be a finite number` |
| NaN / Inf | 2 | 2 | 否 | `must be finite` |
| negative | 2 | 2 | 否 | `must be a positive number` |
| `max_points_per_cell: 8.0` | 2 | 2 | 否 | `must be an integer` |
| floor `min_inliers: 99` | 2 | 2 | 否 | `min_inliers must be >= 100` |
| **400 位整数 float 键** `spatial_cell_m` | 2 | **2** | 否 | `int too large to convert to float` |
| 缺文件 / 空路径 `""` / 目录 | 2 | 2 | 否 | `Errno 2`/`Errno 2 ''`/`Errno 13` |
| 坏 UTF-8 | 2 | 2 | 否 | `'utf-8' codec can't decode…`（`UnicodeDecodeError`⊂`ValueError`） |
| 缺 PyYAML（显式） | 2 | 2 | 否 | `requires PyYAML` |
| 缺 PyYAML（默认） | 0 | 0 | 是 | — |
| loader `RuntimeError` | 2 | 2 | 否 | `PyYAML is required` |
| `max_angle_rad≥π/2` | 2 | 2 | 否 | `must be less than pi/2` |
| 单键改 `min_inliers:200` | 0 | 0 | 是 | —（与默认合并语义） |
| 额外顶层键 `other:1` | 0 | 0 | 是 | —（仅消费 `ground_constrained`） |

对抗补充（int 键 400 位整数）：`max_points_per_cell`/`seed`/`fit_point_cap`/`holdout_point_cap` = 10⁴⁰⁰ 被接受并产 candidate（exit0）；`min_inliers` 因 `fit_point_cap<min_inliers` 被拒。判读：Python 大整数不 overflow，core 契约未设该上界，且这些值被 `fit_point_cap`/`min_inliers` 约束，**不改变真实路径行为，不构成 wrapper 接线漏洞**（见 §6 观察）。

## 5. 失败/BLOCKED 条目来源、触发、实际、预期、根因、最小返工

- **K04 REAL / P04 REAL — BLOCKED（非实现缺陷）**
  - 来源：GLI03_ACCEPTANCE K04「真实审定单组采样≥min_inliers 且 `ground.status=valid` 产 candidate 才 REAL PASS」。
  - 触发：真实 `real_candidate.adapted.npz` + `filled_real_draft.json`，默认/变体两路。
  - 实际：默认 `fit=1214`→`sampled=80(<100)`→`ground_points_insufficient`；变体 `sampled=1193` 但 `degenerate=31`→`ground_degenerate`，均 exit2 无 artifact（E/F/G，独立复现与自验一致）。
  - 预期：真实单组产本地 candidate。虽有独立实测复制，未产真实 candidate，目标未闭合。
  - 根因：真实 ROI 与既定 `up_axis` 夹角约 52.28°（WHAT_IF 研究 `25_prior_hypotheses_results.json`：负 X 或数据法向虽角度合格，仍在 `competition_unresolved` 且三处 holdout 诊断不达门）。属已批准先验/数据物理限制，**不是 config 接线漏洞**。
  - 最小返工：本单不做；不修/不调先验、ROI、冻结算法去凑通过。后续按研究结论核 source 坐标约定/录制 extrinsic、ROI 局部几何一致性、受控搜索完整性，属新里程碑需用户授权。
- **B01 — BLOCKED**：原 bag 源证据仍缺；不将 export 升为物理验证。
- **D01/D02 — NOT_RUN**：设备/物理/GL05/部署/采集/网络/GL04 DPR 未授权。

软件范围内**无 FAIL**。

## 6. 观察（非缺陷，供后续追踪）

1. int 键无上界：10⁴⁰⁰ 的 `max_points_per_cell`/`seed`/`fit_point_cap`/`holdout_point_cap` 被 core 接受。`resolve_constrained_settings` 对 float 键做 `int→float` overflow 捕获，对 int 键无 upper bound（core 冻结语义）。当前不改变真实路径行为；若未来要求强上界，应改 core（需授权），不应在本单 wrapper 里加。
2. `_load_constrained_settings` 捕获 `RuntimeError` 以映射 `load_config` 的“缺 PyYAML”错误；若别处抛编程性 `RuntimeError` 会被转 exit2。范围小、属设计取舍，未越界捕获 `Exception`/`BaseException`，不判 FAIL。
3. 新增 tests 从 `test_gli02_candidate` 复用 `BaseCase` 是测试间依赖，属可接受复用。

## 7. 结论

- 三文件 SHA 首尾一致，与派单一致；范围仅 wrapper + 两新生产文件；冻结/旧证据/原 tests 零变化。
- K01/K02/K03/K05/K06/P01/P02/P03/P05/P06 = **PASS**；K04/P04 = **SYNTH/SOFTWARE PASS，REAL BLOCKED**；B01 = **BLOCKED**；D01/D02 = **NOT_RUN**。
- 无范围内软件 FAIL，无需返工；真实 candidate 目标与整单未闭合、未 ACCEPTED，未自行更新任何表/状态文档。
- 生产写入为零。

SECOND_REVIEW_SUBMITTED / STOPPED
