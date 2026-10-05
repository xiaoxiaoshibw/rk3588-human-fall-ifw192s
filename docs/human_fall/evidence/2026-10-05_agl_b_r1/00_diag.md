# GL-B R1 实现前集中诊断与操作矩阵映射

日期 2026-10-05。范围：新增 `core/adaptive_ground/quality.py` 与集中检查；同时闭合 A 独审登记的两项 B 前置（region_codes SHA/domain_id、sign_anchor 比对）。设计来源：契约 §4、计划 §6、【GL-B 工单】。

## 0. 设计边界

- 只评估：QualityReport = 全域/逐区未裁尾残差 + 谱退化 + 切平面 coverage + normal 合理性 + 7 分项 score + hard gates；`confidence_geo` 是启发式指数（score_kind=heuristic_quality_v1），非正确概率；任一 hard gate 失败 → valid=false 且 confidence=0（平均分不能救回）。
- 不实现：consensus（C）、时间/状态机（D）、transform/应用（E）；不给 FINAL 资格。
- 复用：residual_stats（全域/逐区残差原语）、ground._tangent_basis（版本化切线基，来自 domain.spatial_basis，不默认世界 XY）、A 的 estimate/domain 校验；不新增依赖。
- 权重：谱度量与拟合同用 domain 权重（等权=逐点等权）；支持/计数为逐点口径，分母显式（full=全域、region=逐区）。

## 1. 入口与赋值顺序

`evaluate_quality(estimate, domain, estimator_config, quality_config)`：
1) `resolve_quality_config`（21 键严格解析，缺键/未知键/bool/非有限/关系错即拒，不设默认）→ `quality_config_id`；
2) `resolve_estimator_config` + `estimator_config_id==domain.config_id`；
3) `validate_point_domain` + `validate_plane_estimate(estimate, domain)`（含新增 sign_anchor 比对）→ 同 domain snapshot，无重筛/重拟合；
4) 上游 `numerical_valid=false` → 即刻返回 invalid 报告（reason=GL_UPSTREAM_INVALID + 上游原因，无几何字段）；
5) `signed = p·n + d`（estimate 已规范）→ 全域 `_stats`（RMS/P95/MAD/max_abs/support，阈值取 estimator config 的 inlier_threshold_m）；
6) 逐区按 `region_codes` 分组统计；required 区逐门强判；`min_supported_regions` 计通过区数；
7) 谱（加权协方差 eigh，λ1≤λ2≤λ3）、coverage（固定切线基 + cell）、tilt（vs sign_anchor）；
8) 组装 hard_gate_results（full×4 + 每个 required 区×4 + supported 数 + λ + 格数 + 跨度 + 单格占比 + tilt）；
9) 7 分项 q（lower/higher-better 归一，严格序保证分母非零）→ raw score=Σw·q；hard_ok 时 confidence=raw，否则 0；
10) `report_id = "agl-quality:"+digest(报告)`；输出 JSON 安全、深拷贝。

## 2. 操作矩阵逐行映射（工单前置矩阵）

| 组合 | 入口/触发 | 检查与行为 | 证据 |
|---|---|---|---|
| clean/noisy | evaluate | 门与 q 随噪声单调；噪声梯子 | B 测试 3 |
| plane+人/箱（离群体） | full 统计含全部点（未裁尾）；support/P95 表达；**禁止用 inlier-only RMS 替换 full** | 独立 oracle + inlier-only 对照差分 | B 测试 1 |
| 平行台面/竞争平面 | required 区落在另一面 → 区门 FAIL → 整体 invalid | 四区偏移合成 | B 测试 4 |
| 多ROI缺失 | required code 不存在 → GL_REQUIRED_REGION_MISSING | 同 4 |
| 相同RMS但点数/覆盖/线状不同 | min_points / min_occupied_cells / λ / 跨度 / 单格占比门独立生效，低 RMS 不放过 | 线/窄带/单格/少量 GT | B 测试 2 |
| norm/offset/malformed | validate_plane_estimate/validate_point_domain 结构性拒（含 sign_anchor、region SHA） | B 测试 6 |
| region权重/支持分母 | 支持/残差逐点、分母显式；谱用 domain 权重；无 region 等权 | oracle 全域/逐区 | B 测试 1 |
| bad startup/config reload | quality config 严格拒；坏 domain 原子 raise，无半报告 | B 测试 3/6 |
| caller mutation × 消费者 | estimate_digest/domain_id 绑定；报告深拷贝、JSON 安全；重复评估逐位相同；无缓存旧 score | B 测试 6 |

## 3. 前置闭合与记录

- selection.py：新增 `region_codes_sha256`（构建计算、校验重算、并入 domain_id 绑定）。
- contracts.py：`validate_plane_estimate(..., domain)` 增比 `sign_anchor` 与 `domain.spatial_basis.up_axis`。
- 二者为 A 独审登记项，在 B 回传中记为“前置闭合”；A 专项与全量回归须保持通过。
