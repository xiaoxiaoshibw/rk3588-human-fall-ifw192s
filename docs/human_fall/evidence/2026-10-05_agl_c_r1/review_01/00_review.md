# GL-C 独审（复审 r1）

## 独立性声明

- 复审者：Claude（claude-fable-5）。与作者 OpenCode（opencode-go/deepseek-v4.1-flash）**不同提供方、不同模型**，2026-10-05 ONESHOT 授权下同一会话独立复审。**未参与实现**。
- ponytail：`C:\Users\30680\.claude\skills\ponytail\SKILL.md`（skill 工具加载，full）。
- 基线：`master @ b190834edd3b5ec4f74d2a662ee65fd0e88460f4`。

## 复审对象

- 工单：`docs/human_fall/tickets/GL-C_adaptive_consensus.md` v1（作者 SUBMITTED）
- 回传：`docs/human_fall/returns/GL-C.md`
- 证据源目录：`docs/human_fall/evidence/2026-10-05_agl_c_r1/`
- 复审产物目录：`docs/human_fall/evidence/2026-10-05_agl_c_r1/review_01/`

## 范围核对

| 文件 | 回传 SHA | 实测 SHA | 一致？ |
|---|---|---|---|
| `core/adaptive_ground/consensus.py` | `eb583d1a…` | `eb583d1a…` | ✅ |
| `tests/test_agl_c_consensus.py` | `72be58ac…` | `72be58ac…` | ✅ |

## 逐条验收

复跑日志：`review_01/01_rerun_tests.log`（GL-C 专项 5/5 OK）。GL-C 改的文件**不在** A/B 共享范围（只新增 consensus.py + test_agl_c_consensus.py），但 GL-C 依赖 A（contracts/canonical_plane/validate）+ B（quality_summary/validate_quality_report）；A+B 的全部回归（GL-B 复审已核 30/30 + 504/504）覆盖 GL-C 接入面。

| 验收 ID | 判据字面 | 复跑证据 | 结论 |
|---|---|---|---|
| AGL-C-01 三 pairwise 与 oracle 一致 | 三 pairwise 角/d/pitch/roll 与独立 scalar oracle ≤1e-12；翻 n/d 不误 180°；不同 frame/domain/units/weights 禁比较 | `01_rerun_tests.log::test_pairwise_oracle_flip_and_binding_AGL_C_01` ok。复审 `consensus.py::build_consensus` 行 181–198：只对 planes 非 None 的两两计算 angle/offset_gap/pitch_gap/roll_gap——**字面 oracle 对应**；`canonical_plane`（来自 contracts.py，A 层）在 n≈−n 时同步规范化 → 翻转后 offset 与法向符号一致，不产生伪 180°；`validate_point_domain(domain)` + `validate_plane_estimate(estimate, domain)` 在每个 estimate 入口强制（domain/frame/units 由后者 schema 校验） | PASS |
| AGL-C-02 状态矩阵唯一 | 3 valid 全 GOOD → GOOD；2/3 或 3 仅 DEGRADED 门 → DEGRADED；无一致簇/硬 fail → BAD；.4999/.5001/1.4999/1.5001 边界语义唯一 | `test_status_matrix_and_pair_boundaries_AGL_C_02` ok。复审 `consensus.py::build_consensus` 行 223–250：GOOD 要求 (1) numeric_check_ok=true、(2) set(active)==三、(3) 三对全 GOOD 三者**同时**成立——边界 .4999/.5001 在 `_pair_level`（行 140–147）由 `<=` 严格决定，语义唯一 | PASS |
| AGL-C-03 家族感知 | TLS≈SVD、RANSAC 分歧或 invalid → DEGRADED 但 LS-only 不 bootstrap/更新；RANSAC+LS 跨家族可给**受限 candidate**；数值故障不隐藏 | `test_family_aware_and_numeric_visibility_AGL_C_03` ok。复审 `consensus.py` 行 261–268：`status == "DEGRADED"` 时 `cross_family = len(families) > 1`，`update_allowed = degraded_updates_enabled if cross_family else ls_only_updates_enabled`——**用配置而非硬编码**表达"LS-only 不更新"语义；行 200–211：tls/svd 数值检查失败时 `REASON_NUMERIC` 入 `reason_codes`——数值故障可见、不能隐藏为 GOOD | PASS |
| AGL-C-04 非传递/顺序/tie | A≈B/B≈C/A−C 远非传递链不全部并为 GOOD；order/tie 确定；无方向/无唯一支持保守 BAD | `test_nontransitive_order_and_tie_AGL_C_04` ok。复审 `consensus.py::_maximal_cliques` 行 150–157：先生成 3-clique 再 2-clique，去被超集——非传递链会得两个 2-clique → `len(candidates) != 1` → BAD（不强行三并）；行 261–265：`ranked` 以 `(-confidence, ESTIMATOR_ORDER.index(name))` 排序 → tie 时按 TLS→SVD→RANSAC 固定顺序 | PASS |
| AGL-C-05 追溯/cap/P02 | final confidence cap / selected estimator / 支持簇 / 原因完整；新旧 frame/epoch 不混三结果；当前 0.74136° 在候选 good 0.5 门下明确非 GOOD | `test_cap_reasons_and_p02_current_angle_AGL_C_05` ok。复审 `consensus.py` 行 273：`confidence = min(min_confidence, cap) if status != "BAD" else 0.0`；行 278–282：selected / supporting_estimators / supporting_families / numeric_check_ok / confidence_cap / update_candidate_allowed / reason_codes 全部入 report；行 285：`report_id = "agl-consensus:" + digest(report)` 内容绑定；`build_consensus` 行 274–275：`frame_key = copy.deepcopy(domain["frame_key"])`、`domain_id/config_id` 直接引用——frame/epoch 由调用方保证同 domain，本层在 `validate_plane_estimate` 与 `validate_point_domain` 双锁 | PASS |
| AGL-C-S01 流程 | 当前模块只 candidate 不 commit transform；WF 单 writer / ponytail / diag / 回归 / manifest / 停写 / 独审；旧物理字段不改 | 复审：`consensus.py` 不 import controller/temporal/transform；只产 `update_candidate_allowed` 标志，实际 apply 在 GL-D。文件 stdlib + NumPy；HEAD 未动；未改旧规则/生产 | PASS |
| AGL-C-D01 设备/物理 | 离线单 | 未运行 | NOT_RUN |

## 复审期间发现

1. **作者"自检（实现期）"已落地**：回传记录 `quality_summary` 的 `quality_report_id` 键过严被拒。复审 `consensus.py::_member` 行 103–104：`{"valid", "confidence", "reasons"} <= set(summary) and set(summary) <= {"valid", "confidence", "reasons", "quality_report_id"}`——精确的"必需 + 可选白名单"双向校验。该修复属本单 B→C 桥接语义闭环。
2. **`canonical_plane` 给出 n ≈ −n 同步规范化**：行 126–133；offset_source_m 与 normal 一并进 `canonical_plane` → 翻转后 offset 同步翻转，不会出现 "n 翻转但 offset 不翻" 的伪 180°。
3. **`_pair_level` 严格 `<=`**：`.4999/.5001` 边界唯一；`.5` 与 `.5` 都视为 GOOD（含边界）。
4. **作者初版用"pitch 增量 ≈ 法向夹角"近似被修正**（roll≠0 时夹角≈cos(roll)·Δpitch）：回传记录该测试构造问题已改为"统一 reference 角 + roll=0 基座"——**产品代码阈值语义未变**，测试夹角 oracle 改为绝对角。

## 观察

- `build_consensus` 逻辑可读：estimate→member→plane→pairwise→numeric_check→active→cliques→status→cap→confidence→report 一条直线；family-aware 与 status 决策分离。
- `_maximal_cliques` 用 combinations 穷举 3/2-clique（n=3，规模 trivial）→ 不存在近似启发式。
- `confidence = min(min_confidence, cap)`：min_confidence 来自 supporting 的最小成员（不信任最高成员）；cap 是家族的硬顶（DEGRADED=0.7、GOOD=1.0）——两层 cap 一并在判据内。

## 复审结论

**软件 PASS**（AGL-C-01..05 全过；D01 NOT_RUN 属本单边界）。范围越界无、A/B 委托依赖忠实。

整单 **不报 ACCEPTED**：D01 NOT_RUN。移交 GL-D 复审。
