# GL-I03 R1 阶段一集中诊断 / 2026-10-03

状态：`DIAG_SUBMITTED; STOPPED_WITHOUT_PRODUCTION_WRITES`。阶段一只新增本文件与只读脚本/日志/JSON（`00_diag_probe.py`、`00_diag_probe.json`、`00_diag_config.py`、`00_diag_config.json`）；wrapper/config/tests/return/状态/WORKFLOW 未写。唯一判据 [GLI03_ACCEPTANCE.md](../../GLI03_ACCEPTANCE.md) v1。

## 0. 基线与冻结 SHA（诊断前后一致，未变）

- branch `master` / HEAD `cbd0be1c86a1051a9a5800dfb7263f842896e1e6`；基线 `02_before_diag_manifest.json`（2248 文件，含 tracked+untracked 与 capture）。
- `evaluate_gli02_candidate.py` = `4a4fd0c733cdd608b42c3a11ef926b8c2041a795b1dbdfde3ef826542cad9a3a`（size 11951）。
- `config/geometry_constrained.yaml` = `1c42c1534cb4ee1a110db44140a59df40f31f985028be4015828495f57267880`（size 1237）。
- `tests/test_gli02_candidate.py` = `0dad5771f1ac68a175c2075ffe8f8a49e64b50dfce104fc62adf6d499206a9b0`。
- 冻结 core：`ground.py` = `2d25ccfd9b41b4e16b36c07eec5b243ac50a63bf15230445d942e0f1bcebc4d3`、`capture_input.py` = `56355e9594433d91c871685f58c6ae9f8fe0e47d2b3ad7d07f9b5b8050b85f16`、`calibration.py` = `d29519a1cdb5e495d23115bc89886e9071e4f2055ff529285e933cebdb7c58a3`、`calibrate_sensors.py` = `3f30cf945d70b06f0fce22bdec9ba738f774f98dde2f9a33ce466eeaf9c6c785`。
- 本轮三个生产文件仍为 `??` untracked（`src/human_fall_detection/` 整棵未跟踪）；未 reset/checkout/clean/commit。
- 已读并回传实际路径：`docs/human_fall/WORKFLOW.md`、`docs/human_fall/GLI03_ACCEPTANCE.md`、`docs/human_fall/RETURN_TEMPLATE.md`、`docs/human_fall/AI_PROMPT_GLI03_OPENCODE_R1.md`、`docs/human_fall/evidence/2026-10-03_gl_i03_r1/00_PLAN_REVIEW.md`、`C:/Users/30680/.codex/skills/ponytail/SKILL.md`（本会话实际加载的同一 skill 源为 `C:\Users\30680\.config\opencode\skills\ponytail\SKILL.md`）。

## 1. 头号根因：`ground_degenerate` 的具体判定（阶段一重点）

`00_diag_probe.json` 在同审定 NPZ/draft 单组上复现并分解：

- 审定单组：`fit_index_count=1214`、`fit_frame_group=frame:3d854c4e9c848ce08fb1e058`、validation `2064/119/542`，up_axis `[0.438371,0,0.898794]`、height `[1.2,1.7]` 不变。
- **fit ROI 主平面与 up_axis 夹角 52.28°**：对 1214 点做 SVD，主平面法向 `[-0.4428,-0.0025,0.8966]`，`angle_to_up=52.28°`，`max_angle_rad=0.2618`（15°）；`offset=1.34 m`（在 [1.2,1.7] 内，height 不是拒绝主因）。
- 变体采样 1193 点的 RANSAC 精确分解（同 seed/同 draw 顺序）：861 次三元组中 `degenerate=31`、`angle_reject=828`、`height_reject=2`、**`evaluated=0`、`raw_candidates=0`**。
- 因此命中 `core/ground.py:819-827`：`not candidates and evaluated == 0 and degenerate > 0 → REASON_DEGENERATE`（`ground_degenerate`）。**不是** `orientation_unverified`/ambiguity。
- 关键判定证明该退化与“两个采样值”不是因果：任意使采样 ≥ `min_inliers=100` 的配置都退化——`00_diag_probe.json.sweep`：`0.20/8→160`、`0.10/8→548`、`0.05/4→933`、`0.05/8→1193`，全部 `reason=ground_degenerate`、`raw_candidates=0`。默认 `0.20/4→80` 未达 100，先在 `ground.py:708` 返回 `ground_points_insufficient`，**根本没进入 RANSAC**。
- 结论（冻结算法/数据限制，非接线 bug）：审定 fit ROI 的几何主平面与用户审定的 up_axis 先验相差 52.28°，远超 15° 角度门（`ground.py:738-741`）。两采样值只让 RANSAC 得以运行，随后暴露该不一致。`00_diag_probe.json.fit_roi_dominant_plane` 还显示该主平面法向 x 分量 `-0.4428` 与 up_axis x 分量 `+0.4384` 近乎反号（offset 1.34 m 在区间内）；这提示 up_axis 的 x 朝向可能与该 capture 的 ROI 不符，但**阶段一不修改先验/ROI/数学，只如实记录**，交设计门/用户裁定。
- K04 目标：真实变体产 candidate 目标保留但 `REAL BLOCKED`（退化无 candidate，exit 2 无 artifact）。不得降门槛/换 ROI 先验/池化/改第三参数/mask 为 PASS。

## 2. P01–P06 子情形映射（实际函数 / 配置读取 / 异常传播 / 输出顺序）

### P01 默认 + 审定真实 NPZ/draft
- 顺序：`_load_points`(`evaluate_gli02_candidate.py:83`) → `classify_npz`(`capture_input.py:107`)/`load_adapted`(`:466`) → `_load_draft`/`_draft_region`(`:131/:142`) → `check_declared_frame`(`capture_input.py:503`) → `gate_selection`(`:620`) → `resolve_constrained_settings(None)`(`ground.py:380`) → `fit_ground_plane_constrained`(`:192`) → `validate_constrained_ground`(`:197`) → `ground_is_valid`(`:201`)。
- 实测：`EXIT=2`，`ARTIFACT_EXISTS=False`，stderr `candidate ground was not produced: ground_points_insufficient`；冻结源 SHA 未变。默认真实路径全覆盖、无缺检查。

### P02 默认 synthetic / 显式冻结 config / 重复 CLI / 独占输出 / emit-draft
- 默认 synthetic：`tests/test_gli02_candidate.py` 8/8 OK（T1 candidate、T2 缺先验拒、T3 独占拒、T4 source 标注、T5 legacy/损坏拒、T6 emit-draft 独占、T7 capture-dir 只读、T8 public-API-only）。
- 显式冻结 config：`00_diag_config.json.frozen_config` 证明 `load_config(frozen)→{'ground_constrained':{...}}`，`resolve_constrained_settings` 结果 **完全等于** `CONSTRAINED_DEFAULT_SETTINGS`（`frozen_config.resolved_equals_default=true`）。故显式传冻结 config 与 `None` 同结果/同 settings。
- 重复新 CLI：`main`(`:228`) 每次全新 `argparse` + 全新 `load_config`；无模块级可变缓存，不存在跨调用状态。`resolve_constrained_settings` 每次 `dict(CONSTRAINED_DEFAULT_SETTINGS)` 起新对象。
- 同/新 calibration ID：`save_exclusive_json`(`calibrate_sensors.py:46`) 用 `os.link` 原子独占创建；已存在→`GeometryCalibrationError`→exit 2 且目标字节不变（T3 已覆盖）。
- emit-draft：`main:243-255` 在“需要 `--draft`”与 candidate 之前处理，`_blank_draft` 只读 manifest；阶段二**不得**为 emit-draft 增加 config 消费。
- 缺检查：无 `--constrained-config` 入口（阶段二加）。

### P03 显式变体 synthetic 成功 / 解析负例 / 同路径改内容 / 对象不污染 / 已有 output 不变
- 入口缺口（最小位置）：`parse_args`(`:54-80`) 现无 `--constrained-config`；`_run_candidate:190` 硬编码 `resolve_constrained_settings(None)`。阶段二最小改动 = 新增 helper `_load_constrained_settings(path)`（`load_config` + 结构检查 + `resolve_constrained_settings`），在 `main` 解析后调用并传入 `_run_candidate`；不新增其它消费点。
- 配置边界异常实测（`00_diag_config.json`）：
  - 坏路径 → `FileNotFoundError`（OSError，**已被** wrapper `except` 捕获 → exit 2）。
  - YAML 语法错 → `yaml.parser.ParserError`（YAMLError 子类）→ **当前不被** `(ValueError,OSError,...)` 捕获 → 会 exit 1/回溯。**缺检查**：阶段二须在边界转为既有错误类型（如 `CaptureInputError`/`ValueError`），不吞编程错误。
  - 空文件 → `safe_load` 返回 `None`→`or {}`→空 dict，**缺 ground_constrained section**；若不过滤会静默 fallback 默认。**缺检查**：阶段二须显式拒绝缺 section。
  - 顶层 list → 返回 list，`.get` 不可用；**缺检查**：阶段二须拒绝非 mapping 顶层。
  - section 非 mapping（如 `5`）→ `resolve_constrained_settings(5)` 抛 `AttributeError`（“'int' object has no attribute 'items'”）→ **当前不被**捕获。**缺检查**：阶段二须先判 section 为 mapping。
  - unknown key → `ValueError`（已捕获）；bool/NaN/负数/floor（`min_inliers=99`）→ `ValueError`（已捕获）。
  - 两值变体 → 正常解析、与默认不同（`resolved_equal_default=false`）。
- 同路径改内容：无缓存，下次新 CLI 读取新内容生效（`load_config` 每次实读文件）。
- 对象隔离：`resolve_constrained_settings` 只读输入 mapping、返回新 dict，caller 原地改不污染默认。
- 已有 output 字节不变：`save_exclusive_json` 独占（见 P02）。
- synthetic 变体成功：阶段二新 tests 覆盖（synthetic 平面对 `0.05/8` 增采样仍可产 candidate）；阶段一未写 tests。

### P04 显式变体 + 真实审定单组 / 各类拒绝 / capture-dir 语义
- 变体真实：CLI 入口阶段一不存在；以只读 preflight/`00_diag_probe` 等价复现：`sampled=1193`、`degenerate_samples=31`、`reason=ground_degenerate`、`raw_candidates=0`→exit 2 无 candidate。根因见 §1。
- 无 `--draft` → `main:257` exit 2；缺先验 `up_axis=None` → `_unit_vector`(`ground.py:459`) ValueError（T2）；frame 不符 → `check_declared_frame` CaptureInputError；坏 manifest/不支持版本 → `load_adapted`(`:466`)/`read_source_meta`(`:164`) 严格拒；跨组泄漏/重叠 → `gate_selection`(`:620`) 与 `fit_ground_plane_constrained` 的 leakage/overlap 门（`ground.py:677-695`）；capture-dir 只读 + `.adapted.npz` 中间产物 → `_load_points:93-94` + `prepare_npz`（T7 证明 capture 目录字节/列表不变）。
- source/physical：`build_input_info`(`:682`) 设 `source/synthetic`；`build_geometry_calibration` 后 `validate_geometry_calibration`(`calibration.py:1040`) 保证 `status.ground=candidate`、physical=false、无 `ground_derived`；`ground.settings` 记录 resolved（`ground.py:168`）。阶段二须保持。

### P05 新旧 YAML 唯一值差两采样参数
- 冻结 `ground_constrained` 全 29 键与 `CONSTRAINED_DEFAULT_SETTINGS` 相等（`00_diag_config.json`）。新文件须为冻结文件整份复制，仅 `spatial_cell_m=0.05`、`max_points_per_cell=8`；`ground.settings` 记录 resolved。其余阈值/预算/键与冻结文件 SHA 均须保持；阶段二 HTTPS/verify 用完整 dict 比对。

### P06 范围/manifest/AST
- 白名单仅 3 文件；基线 `02_before_diag_manifest.json` 含全部 tracked+untracked 与 capture；`captureSHA`、Windows `src/CMakeLists.txt` 软链表示保留（`snapshot.py` 用 `lstat` 记录 WinError1920，不修复）。
- 阶段二记 wrapper 新 SHA + 冻结 SHA 对照；Python3.8 AST 用 `ast.parse` 做语法级检查，本机 `Python 3.12.10 / NumPy 1.26.4 / PyYAML 6.0.3` **不冒充**设备运行（D01 NOT_RUN）。

## 3. CLI 生命周期操作矩阵（WF-CODEX-R1/R1）

| 情形 | 本 wrapper 映射 | 覆盖/缺检查 |
|---|---|---|
| startup | 每次进程启动 = `parse_args`+`load_config`，无持久状态 | 已有 |
| 同内容 reload | 重复新 CLI 读同 config → 同 resolved | 已有 |
| 同 ID 异内容 | 同 config 路径改内容 → 下次新 CLI 生效（无缓存） | 已有；阶段二设计须避免模块级缓存 |
| 新 ID reload | 新 config 路径逐次运行 | 已有 |
| caller 原地修改 | `resolve_constrained_settings` 返回新 dict，不污染默认 | 已有 |
| 外来 frame | `check_declared_frame`/`load_adapted` 严格拒 | 已有 |
| 损坏 manifest | `_read_manifest`/`load_adapted` 拒 | 已有 |
| 不支持版本 | `read_source_meta` `format_version` 拒 | 已有 |
| GL02/ROS lifecycle | 裁剪：本 wrapper 为一次性离线 CLI，无 daemon/ROS 节点/订阅/latch/版本热切换 | 裁剪理由：不在本文件调用链内 |

## 4. 默认 / 显式 / emit-draft / 负例 / source-physical 方案（阶段二实施边界）

- 默认 `None`：完全保持 GL-I02 R1 语义（`resolve_constrained_settings(None)` 不变）。
- 显式 `--constrained-config`：复用 `load_config`+`resolve_constrained_settings`；边界异常转既有错误类型；坏路径/语法/结构/缺 section/unknown key/bool/NaN/负数/floor 一律 exit 2 无 candidate、不 fallback。
- emit-draft：保持原模板行为，不新增 config 消费；输出顺序不变（先 `_load_points`，再 emit-draft）。
- source/physical：synthetic 与 capture_export 分目录分层；`source-kind` 标注不变。
- 不修冻结算法/先验/ROI/数学；真实 candidate 仍 BLOCKED（§1）。

## 5. 阶段一自验记录

- `python -B docs/.../00_diag_probe.py` exit 0；`python -B docs/.../00_diag_config.py` exit 0。
- 真实默认 CLI：`--prepared-npz 08_real/real_candidate.adapted.npz --draft codex_review_01/work/filled_real_draft.json --output <%TEMP%>/gli03_default_candidate.json --source-kind capture_export` → `EXIT=2`、`ARTIFACT_EXISTS=False`、`ground_points_insufficient`。
- 回归：`test_gli02_candidate` 8/8 OK（exit 0）；`test_gl01_constrained_ground` 33/33 OK（exit 0）。
- 冻结/生产 SHA 与基线一致，未写生产文件。

`DIAG_SUBMITTED; STOPPED_WITHOUT_PRODUCTION_WRITES`
