# R3 STEP 6 — REGRESSION_REPORT

**日期**: 2026-10-10/11
**作者**: Claude (Sonnet)
**目标**: 验证 M1 优化 (engine.js indexOf→Map) + R3 GT/训练改动**没有破坏任何现有功能**

---

## 1. 测试矩阵

| 套件 | 断言 | 结果 |
|---|---:|---|
| `pc_apps/human_core/run_all_tests.js` | 96 | ✅ PASS |
| — schema | 13 | ✅ |
| — data_loader | 16 | ✅ |
| — engine_smoke | 9 | ✅ |
| — replay_contract | 11 | ✅ |
| — edge_cases | 14 | ✅ |
| — model_compat | 12 | ✅ |
| — rework | 21 | ✅ |
| `pc_apps/human_replay/gt_lib.test.js` | 29 | ✅ |
| `pc_apps/human_core/test_fusion_specific.js` | 16 | ✅ |
| `pc_apps/human_core/test_fusion_gt.js` | GT contract | ✅ |
| `pc_apps/human_core/test_m1_parity.js` (R3 新） | 100 cands | ✅ indexOf vs Map 0 mismatch |
| `pc_apps/human_core/test_s1_v3_regression.js` (R3 新） | 1818 propagated | ✅ idx space valid |

**总计 156+ 断言全部 PASS，0 失败**。

## 2. 关键回归保障

- **FUSION 完整功能**: 16/16 specific + GT contract PASS — M1 没破 Track / Bank / decision / unknown
- **输出等价**: test_m1_parity 100 candidates × 100 索引 random input 下 Map 与 indexOf 输出**逐字节一致**
- **数据完整性**: test_s1_v3_regression 1818 propagated 对象索引**全部在合法空间**
- **生产侧**: 未动 `webui/human_fall/` / 生产主入口**0 字节差异**

## 3. 已知不能跑 （不归因本次）

| 项 | 原因 |
|---|---|
| `test_baseline_parity.js` | `collect cap_20261004_203135` capture 缺失 (R1 已知记录于 FINAL_REPORT §5) |
| `human_detect_lib.test.js` | Windows Node v24 HANG (memory 已记，与本工单无关） |

## 4. STEP 6 结论

| 项 | 结果 |
|---|---|
| M1 优化对所有 7 套件兼容 | ✅ |
| FUSION 专项不变 | ✅ |
| GT 数据索引合法 | ✅ |
| 未授权操作（commit/push/deploy/改生产入口） | **无** |
| **REGRESSION_PASS** | ✅ |
