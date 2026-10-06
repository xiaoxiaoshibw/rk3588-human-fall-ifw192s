# GL-B 独审（复审 r1）

## 独立性声明

- 复审者：Claude（claude-fable-5）。与作者 OpenCode（opencode-go/deepseek-v4.1-flash）**不同提供方、不同模型**，2026-10-05 ONESHOT 授权下的同一会话独立复审。**未参与实现**。
- ponytail：`C:\Users\30680\.claude\skills\ponytail\SKILL.md`（skill 工具加载，full）。
- 基线：`master @ b190834edd3b5ec4f74d2a662ee65fd0e88460f4`。

## 复审对象

- 工单：`docs/human_fall/tickets/GL-B_adaptive_quality.md` v1（作者 SUBMITTED）
- 回传：`docs/human_fall/returns/GL-B.md`
- 证据源目录：`docs/human_fall/evidence/2026-10-05_agl_b_r1/`
- 复审产物目录：`docs/human_fall/evidence/2026-10-05_agl_b_r1/review_01/`

## 范围核对（四文件 SHA 三向一致）

| 文件 | 回传 SHA（前 8） | 实测 SHA（前 8） | 一致？ |
|---|---|---|---|
| `core/adaptive_ground/selection.py` | `c3608752…` | `c3608752…` | ✅ |
| `core/adaptive_ground/contracts.py` | `bc862be4…` | `bc862be4…` | ✅ |
| `core/adaptive_ground/quality.py` | `965faa8a…` | `965faa8a…` | ✅ |
| `tests/test_agl_b_quality.py` | `850f3a79…` | `850f3a79…` | ✅ |

前置闭合两项（A 独审登记的两项非阻断观察）已落地为两段 additive：
- `selection.py`：`region_codes_sha256` / 并入 `domain_id` / 引用摘要
- `contracts.py`：`validate_plane_estimate` 在传入 domain 时要求 `estimate.sign_anchor == domain.spatial_basis.up_axis`

A 专项回归（GL-B 复审 `02_full_regression.log` 头部）仍全过 → 前置没破坏 A 层。

## 逐条验收

复跑日志：`review_01/01_rerun_tests.log`（GL-B 专项 6/6 OK）、`02_full_regression.log`（agl_* 30/30 OK；human_fall_detection 全量 504/504 OK）。

| 验收 ID | 判据字面 | 复跑证据 | 结论 |
|---|---|---|---|
| AGL-B-01 全域/逐区未裁尾残差 | 全共同域及逐区：**未裁尾**（no-tail-cut）残差；RMS/P95/MAD/support；与独立标量 oracle ≤1e-12m；RANSAC full≠inlier-only；不能用 inlier RMS 替换 full | `01_rerun_tests.log` `test_full_and_region_oracle_untruncated_denominators_AGL_B_01`：全域 + 逐区 + RANSAC 三维度，与独立 oracle 差 ≤1e-12m；`10_test_agl_b_log.txt` 作者值复核通过。复审 `quality.py::_stats` 行 154–165：`rms = sqrt(mean(signed^2))` / `p95 = percentile(abs(signed), 95)` / `mad = median(|signed − median(signed)|)` / `max_abs = max(|signed|)` / `support_count = |signed| ≤ threshold` 计数 / `support_fraction = support_count / count`——**全程未做 tail cut / winsorize / clip** | PASS |
| AGL-B-02 退化 hard gates | min_points / min_supported_regions / coverage / λ2/λ3 退化 hard gate；共线/窄带/少点/单格集中低 RMS 必须 invalid | `01_rerun_tests.log` `test_hard_gates_reject_low_rms_degenerates_AGL_B_02`：共线 → 上游 invalid；窄带 λ/span 拒；25 点低 RMS 拒；1600 点单格低 RMS 拒。复审 `quality.py::evaluate_quality` 行 305–317：`spectral_lambda2_lambda3_min`、`coverage_min_cells`、`tangent_extent_min`、`single_cell_share_max` 四个全局 hard gate——低 RMS 救不了窄带/单格集中/λ 退化 | PASS |
| AGL-B-03 score 边界/单调/关系 | score ∈ [0,1]；非法输入 score 0；7 几何分项 + 上游 normal/区域门；hard fail **不能被平均 score 救回**；soft/hard 参数关系严格 | `test_score_bounds_monotonicity_and_config_relations_AGL_B_03`：12 个 config 负例全拒；噪声单调（q_rms / confidence 随噪声降）；分项 ∈ [0,1]；hard fail raw_score>0 但 confidence=0、valid=False。复审 `quality.py::resolve_quality_config` 行 77–147：所有"次序严格"断言（min < soft_good < max、min < soft_full、soft_good < max、min_points < soft_full_points、score_weights 7 项非负和为 1）逐字校验；`evaluate_quality` 行 364：`confidence_geo = raw_score if hard_ok else 0.0`——hard fail 时即使 raw_score>0 也强制 0 | PASS |
| AGL-B-04 区域 FAIL 仍降级/拒 + P02 | 四 ROI 整体好但某必需区 FAIL 仍降级/拒；墙/箱顶/竞争平面不以多点/低 RMS 签 ground truth；P02 已知留一区失败原样记录 | `test_required_region_fail_and_mixed_geometry_AGL_B_04`：四区好+3% 坏区(+8cm) → invalid + REGION_FAILED；35° 陡面 tilt 拒；required 缺失拒；`test_p02_leave_one_out_fail_preserved_AGL_B_04`：P02 留一区 FAIL 精确复现（#1/#3 P95 超 5cm、#2 PASS、#4 RMS/P95/support FAIL，与已发布 cm 值差 ≤5e-6m）。复审 `quality.py::evaluate_quality` 行 287–290：required 区域失败时把 `GL_REQUIRED_REGION_FAILED` 推到 `region_reasons` 队首；行 299–300：missing 区域另加 `required_region_present` hard gate | PASS |
| AGL-B-05 追溯/绑定/无旧 score 泄漏 | score_kind / 分项 / 计数 / cover basis / 参数 SHA 可追溯；缺 basis 或无版本不默认世界 XY；caller/reload 无旧 score 泄漏 | `test_traceability_binding_no_stale_leak_AGL_B_05`：report_id 可重算、JSON 安全；篡改 estimate/domain/anchor 原子拒；重复评估逐位相同；新 config 新 id、无旧 score 泄漏。复审 `quality.py::validate_quality_report` 行 370–400：`report_id == "agl-quality:" + digest(...)` 内容绑定；`score_kind == SCORE_KIND` 强制；`units == UNITS`；`domain_id.startswith("agl-domain:")` / `config_id.startswith("agl-config:")` / `quality_config_id.startswith(QUALITY_CONFIG_PREFIX)` 命名空间校验；行 358：`coverage.basis_provenance` / `basis_version` 从 domain 拷贝 | PASS |
| AGL-B-S01 流程 | 最小 module / stdlib+NumPy / Python 3.8；诊断 → 自验 → SHA → 停写 → 指定独审；旧规则/生产不改 | 复审：`quality.py` 与 `test_agl_b_quality.py` 只 import `copy/math/numpy` + 项目内 ground / ground_diagnostics / ground_evidence / numeric / contracts / selection——无 OpenCV / 无三方依赖；语法 3.8 兼容（无 walrus / f-string= 内部变量只读）；未改 frozen 资产 / 未改旧证据；HEAD 未动 | PASS |
| AGL-B-D01 设备/物理 | 离线单 | 未运行 | NOT_RUN |

## 复审期间发现

1. **回传"修复 1 处本单缺陷"已落地**：作者在实现期发现 required 区域缺失时未入 `hard_gate_results`，bug 是 `hard_ok` 只看存在的 required 区，缺失区只入 `region_records` 不入 gates → valid 误为 true。复审 `quality.py` 行 299–300：补 `for code in missing: gate("required_region_present", "region", None, None, False, region=code)`——把缺失区也标为 hard gate 失败。作者测试 `test_required_region_fail_and_mixed_geometry_AGL_B_04` 中的"required 缺失拒"用例即此锁定。该修复属本单内的 valid 语义闭环，**非范围越界**。
2. **AGL-B-05 中"缺 basis 或无版本不默认世界 XY"** 的复审证据：`quality.py::evaluate_quality` 行 358 把 `basis_provenance` / `basis_version` 从 domain 拷贝；`validate_point_domain`（来自 selection.py，A 层契约）已对 spatial_basis.provenance / version 做强制 schema 校验。任何缺 basis 的 domain 会在 `validate_point_domain` 处被拒，**不会落进 quality 的世界 XY 默认**。
3. **"不调用时间 controller / 不把 confidence 当真实概率"** 的判据满足：`quality.py` 完全不 import controller / temporal / transform / consensus；`SCORE_KIND = "heuristic_quality_v1"`、`evaluate_quality` 只产 `confidence_geo`，无概率断言。

## 观察

- `evaluate_quality` 单函数 25 个 gate + 7 个 soft score，结构 flat 易读；hard fail 路径只用一行 `confidence_geo = raw_score if hard_ok else 0.0` 强制——简洁、可读、可审计。
- 每个 `gate(...)` 都以 `passed: bool` 显式落 `hard_gate_results` → `valid = all(...)`——hard fail 不会被分项平均掩盖，判据字面闭环。
- `report_id = "agl-quality:" + digest(report)`（`report_id` 字段本身除外）→ 内容绑定；用户篡改 estimate / domain / anchor 任一字段都会被 `validate_quality_report` 检测。
- `digest` 在 `estimate` 上直接调（`estimate_digest: digest(estimate)`）；`frame_key` 从 estimate 深拷贝，防止 estimate 后续被 caller 改动时 report 失真。

## 复审结论

**软件 PASS**（AGL-B-01..05 全过；D01 NOT_RUN 属本单边界）。范围越界无、selection/contracts 前置改动 additive、未触碰旧证据/冻结资产。

整单 **不报 ACCEPTED**：D01 NOT_RUN 属边界，按 WORKFLOW 由用户决定是否收口。移交 GL-C 复审。
