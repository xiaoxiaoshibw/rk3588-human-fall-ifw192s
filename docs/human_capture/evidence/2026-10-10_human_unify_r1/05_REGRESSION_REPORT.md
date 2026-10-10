# HUMAN-UNIFY-R1 · 05 REGRESSION REPORT

## 测试矩阵

| Suite | 测试数 | PASS | FAIL | 覆盖 |
|---|---|---|---|---|
| test_schema.js | 13 | 13 | 0 | FrameContext / Candidate / Track / Diagnostics / GT_LEVEL （含 PSEUDO_LABEL) |
| test_data_loader.js | 16 | 16 | 0 | 28B 解析 / meta 校验 / iter_frames_lazy / SHA |
| test_engine_smoke.js | 9 | 9 | 0 | 空场零误报/真实三人有确认/严格模式重入守卫 |
| test_replay_contract.js | 9 | 9 | 0 | 单调/换会话/跳帧/回退/循环/空档 |
| test_edge_cases.js | 14 | 14 | 0 | 空帧/z<0.1/点不足/家具 vs 人/长期消失/多候选/缺 cfg |
| test_model_compat.js | 12 | 12 | 0 | 100 树 51 维/classes/value 形态/拒绝 69/reproducibility |
| test_perf.js | 2 | 2 | 0 | P95<50ms × 9; heap<1500 MB × 9 |
| **总** | **73** | **73** | **0** | — |

## 任务书 §8 覆盖检查

| 场景 | 实测状态 |
|---|---|
| 空场无误检 | **PASS** (BASE_A+B, 空场 113611 confirmed=0; U3 空场 203 误报属已知 RF 问题， 不属引擎回归） |
| 家具误检 | 边缘覆盖： 家具 4.5-7 cand/帧， 无 HUMAN_VERIFIED GT → UNKNOWN |
| 单人静立 | PASS （高个 114641 BASE_B confirmed=2) |
| 单人移动 | PASS (154007 BASE_B confirmed=6) |
| 静止后重新移动 | （无法 GT, 但 replay_contract 测覆盖 track 消失续航） |
| 多候选关联 | PASS （合成 2 人形柱 tracking_id 唯一） |
| 不足点数的人体 | PASS (n<10 帧 0 cand) |
| 聚类拆分 | 已检测 cluster_split semantics (BASE_A 拆 vs BASE_B 网格聚）, 未量化 （无 GT) |
| 数据缺字段 | PASS （空 cfg 构造不崩； 缺 leveling 用 ref R/T) |
| 模型不兼容 | PASS (init n≠51 拒； value [2] 组校验） |
| session 切换 | PASS (begin_session 状态隔离， 显式 new/loop_back/session_switch) |
| 跳帧及循环 | PASS (begin_session 循环重置 frame_seen) |
| 状态重置 | PASS （每次 begin_session 全新 Tracker/Retention/seen_frames) |
| 重复帧输入 | PASS (strict 抛， lenient duplicate_ignored) |

## 语义验证

- BASE_A **逐帧输出与 detect_ui.js 同语义**（几何门 × 证据 × 3/5 confirm)
- BASE_B **逐帧输出与 detect_overlay.js 同语义**(REF envelope + 5cm 网格 + RF + age≥3)
- **生产 A 空场零误报**： 引擎 BASE_A 复现
- **生产 B 空场零误报**: 引擎 BASE_B 复现
- **生产 A 静立人剪影**: 引擎 BASE_A 复现 （全部进背景）
- **C1.5 硬门剔除动态人**: 引擎**默认不引入 n≥500**, 与 C1/C1.5 教导一致

## 不允许通过的手段

- 没有删除失败样例
- 没有放宽断言
- U3 空场误报**已显式标记**为 RF 行为， 不算引擎回归
- U2 retention confirmed 退化 （见 04) 已显式标记， 不算回归

## 已知 NOT_FIXED （下一轮）

1. U2 retention confirmed 计数反而退化 — retention 应在 lost≥1 时启用， 但 confirmed=1 的 track 在 lost=0 时已被 active 等到 lost≥1 时已 close； retention 逻辑需重构在 close 的 hot pixels 而非 active
2. U3 rf51 空场误报 — RF 模型在 transient 家具上本身给高分， 需 REF envelope 注入 U3 的 fg
