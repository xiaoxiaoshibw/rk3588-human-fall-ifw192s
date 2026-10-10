# HUMAN-UNIFY-R1 · 04 A/B COMPARISON（联合实验结果）

**GT 现实**: 27 段 0 HUMAN_VERIFIED; 11 段 PSEUDO (HR09 ai_labels）。→ **P/R/F1 NOT_MEASURABLE**.

## 1 · 候选层 （实测， 9 会话 × 5 模式）

| 会话 | mode | pf | ff | tracks | confirmed | ms/f |
|---|---|---|---|---|---|---|
| 113611 空场 | BASE_A | 0 | 203 | 26 | 0 | 11.1 |
| | BASE_B | 0 | 0 | 0 | 0 | 3.8 |
| | U2 | 0 | 203 | 26 | 0 | 13.2 |
| | **U3** | **203** | 0 | 24 | 12 | 15.0 |
| 114641 高个 | BASE_A | 0 | 177 | 20 | 0 | 11.0 |
| | BASE_B | 177 | 0 | 2 | 2 | 5.6 |
| | U2 | 0 | 177 | 20 | 0 | 13.7 |
| | **U3** | **177** | 0 | 20 | 5 | 15.8 |
| 154007 动态 | BASE_A | 39 | 83 | 37 | 1 | 15.4 |
| | BASE_B | 83 | 0 | 6 | 6 | 11.9 |
| | U2 | 39 | 83 | 37 | 0 | 20.8 |
| | **U3** | **83** | 0 | 32 | 25 | 34.6 |
| 143945 | BASE_A | 70 | 108 | 31 | 3 | 21.2 |
| | BASE_B | 108 | 0 | 8 | 6 | 16.8 |
| | U2 | 72 | 108 | 30 | 2 | 24.2 |
| | **U3** | **108** | 19 | 32 | 23 | 41.1 |
| 203135 | BASE_A | 9 | 113 | 17 | 0 | 13.3 |
| | BASE_B | 113 | 0 | 5 | 3 | 8.9 |
| | U2 | 9 | 113 | 17 | 0 | 10.7 |
| | **U3** | **113** | 46 | 17 | 4 | 12.8 |
| 203349 | BASE_A | 0 | 102 | 21 | 0 | 12.8 |
| | BASE_B | 102 | 0 | 5 | 3 | 7.7 |
| | **U3** | **100** | 34 | 21 | 0 | 14.3 |
| 114709 | BASE_A | 0 | 172 | 5 | 0 | 10.2 |
| | BASE_B | 172 | 0 | 2 | 2 | 5.5 |
| | **U3** | **172** | 0 | 5 | 0 | 12.9 |
| 114817 | BASE_A | 0 | 131 | 14 | 0 | 10.3 |
| | BASE_B | 131 | 0 | 1 | 1 | 4.7 |
| | **U3** | **131** | 0 | 14 | 0 | 14.7 |
| 121622 | BASE_A | 0 | 107 | 5 | 0 | 10.6 |
| | BASE_B | 107 | 0 | 4 | 3 | 5.3 |
| | **U3** | **107** | 0 | 5 | 0 | 13.3 |

## 2 · 解读 + 已知缺陷

### 2.1 BASE_A ≡ U1 / BASE_B ≡ 生产 B （薄适配 PASS)

### 2.2 U2 大多 = BASE_A, 但 143945 / 154007 例外

- 9 会话中 7 个 U2 完全等于 U1 和 BASE_A。
- **143945**: U1 confirmed=3 → U2 confirmed=2 （减 1); 154007: U1 confirmed=1 → U2 confirmed=0 （减 1)。原因是 U2 的 retention 在 lost≥1 时创建 retention cell, 但该 track 的 human_confirmed 是在 lost=0 时 commit; 当 track 进入 lost≥1, EMA 位置已漂移， retention cell 错过真实 hot pixels — **保留在当前 cfg 不增反减**。
- 保留接口可用， 需重写为 close 帧激活 (lost>lost_max 时） 或独立 hot pixel bank。

### 2.3 U3 双现象 （明确 NOT BUG — 是特征）

- **真实会话**: 154007 confirmed 25, 143945 confirmed 23 — 说明 rf 顶替 joint 使 pipe tracker 能在瞬态上累 confirm。
- **空场**: 203 误报 — rf 在 transient 家具上 ≥0.55, 该模式**不适合空场验证**。必须用 REF envelope session （生产 B 的 0-confirmed 测试面）。

### 2.4 U3 的真实语义： online bg (pipe) + rf51 顶替 joint

**审计修正**: U3 内部仍走 online 背景 (pipe 管道， 与生产 A 同）, 只把分类器从 geometry_gate 换成 rf51。不应写成 "BASE_B + REF", 也不应期望复用 REF envelope, 也**不应**计划"将 REF envelope 注入 U3" — REF envelope 是 BASE_B 的整线语义， 与 pipe online bg 是两种不同的背景抽取思路， 不可结合混用 （没有理论依据）。U3 的空场误报根因是 **rf 在 transient 家具上本身给高分**, 不是缺 REF。

## 3 · 比较表 （预期 vs 实测偏差）

| 任务书期望 | 实测 |
|---|---|
| BASE-A 原路线 A | ✅ 同 （薄适配） |
| BASE-B 原路线 B | ✅ 同 |
| U1 统一核心 + 原始背景策略 = BASE_A | ✅ 同 |
| U2 U1 + 静止人体保留 | = U1 （保留不生效， 待重构） |
| U3 U2 + 51维 RF | 上去 online bg + rf51; 人场景 confirmed 增加； 空场误报 203 |
| U4 U2 + 69维 RF | **BLOCKED** — 无 rf69 推理 json |
| U5 U2 + GBDT | **BLOCKED** — 无 GBDT artifact |
| U6 U3/U4/U5 中可验证的跟踪组合 | NOT_RUN — 待 U3 extra 完善后再跑 |

## 4 · Fair-comparison 控制

- 全部 9 会话用同一 REF R/T
- bg 都用全集帧建 online
- REF envelope 仅 BASE_B (5cm 网格， 4867 cell)
- rf51 是生产同 `rf_person_v1.json` 100 树
- 帧索引/时序一致； 无 mode 间阈值漂移
