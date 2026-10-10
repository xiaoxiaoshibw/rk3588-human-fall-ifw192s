# HUMAN-UNIFY-R1 · 08 INTEGRATION READINESS

## A. SOFTWARE_ACCEPTED — 评估： **PASS**

核心证据：

| 要求 | 实测 |
|---|---|
| 公共核心可运行 | ✓ `pc_apps/human_core/` 7 文件 |
| 数据 schema 良好 | ✓ 13/13 schema tests, 16/16 loader tests |
| 对齐生产行为 | ✓ 9 会话 × 5 模式 BASE_A = 生产 A, BASE_B = 生产 B |
| 测试覆盖 | ✓ 73 tests PASS (schema/loader/smoke/replay/edge/model_compat/perf) |
| 关键回归 | ✓ 空场零误报/换会话隔离/循环回放/重复帧守卫/严格模式 |
| 性能 | ✓ PC 离线 P95 < 50 ms/f 全 9 会话， heap < 1500 MB |
| 模型兼容 | ✓ 51 维 100 树 json 校验； n≠51 拒； 可复现 |
| 生产文件不变 | ✓ 02_source_sha/prod_sha256.json 19 文件 SHA 未动 |
| 数据源 | ✓ 28B 布局 meta.frames offset/count 实测对得上 |

**未完成/已知**:
- U2 retention 实际不吸收候选 — 应重新实现于 close 帧而非 active
- U3 classifier=rf51 在空场误报 — 需 REF envelope 注入， 本轮不做
- U4/U5 BLOCKED （无 artifact)
- U6 NOT_RUN （基于 U3 extra 后再组合）

## B. ALGORITHM_ACCEPTED — 评估： **NOT_MEASURABLE**

| 要求 | 状态 |
|---|---|
| 独立可信 GT 证明统一方案达到登记指标 | **BLOCKED** — 全库 0 段 HUMAN_VERIFIED; 仅 PSEUDO (11 段 HR09) |
| 没有不可接受的关键回归 | **PARTIAL** — 薄适配 BASE_A/B 零回归； 但 U2/U3 不是单纯"包装" — 实际产生新语义， 需在 GT 下验证 |
| 预登记指标存在 | **NO** — 无登记数字门槛， 本轮不应硬划 |

**诚实声明**: 本轮**并不**证明统一核心在准确度上优于生产 A 或 B。它证明的是：
1. 同一套代码可以**等价复现**生产 A 和 B （薄适配正确性）
2. 分类器可作为**插件**插入 (rf51 已演示）, 语义直通 tracker
3. 静止保留的"统一保留"概念已建接口， 但当前实现需重构时机

## C. PRODUCTION_READY — 评估： **BLOCKED**

| 要求 | 状态 |
|---|---|
| 环境兼容 | PC node 已 OK; **RK3588 未实测**, **NOT_MEASURABLE** |
| 性能 | PC 离线 OK; 板端**NOT_MEASURABLE** |
| 资源 | PC heap<1500MB OK; 板端**NOT_MEASURABLE** |
| 集成回归 | 引擎不出现在任何生产页面 — **路径已预留, 未集成** |
| 回退验证 | 引擎是隔离新代码， 关掉即回到生产 — **不涉及回退** |

## 交付清单

| 产物 | 位置 |
|---|---|
| 统一核心 | `pc_apps/human_core/` |
| 测试 | `pc_apps/human_core/test_*.js` × 6 + run_all_tests.js |
| runner CLI | `pc_apps/human_core/runner.js` |
| 9 会话跑产物 | `docs/human_capture/evidence/2026-10-10_human_unify_r1/runs/` |
| 生产源 SHA | `02_source_sha/prod_sha256.json` |
| Baseline | `00_BASELINE.md` |
| Architecture | `01_ARCHITECTURE_PLAN.md` |
| Data audit | `02_DATA_AND_GT_AUDIT.md` |
| Pipeline diag | `03_PIPELINE_DIAGNOSTICS.md` |
| A/B | `04_AB_COMPARISON.md` |
| Regression | `05_REGRESSION_REPORT.md` |
| Performance | `06_PERFORMANCE_REPORT.md` |
| OpenCode review | `07_review_findings.md` |
| 本整合 | `08_INTEGRATION_READINESS.md` |
