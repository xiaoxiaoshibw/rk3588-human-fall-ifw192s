# C1.6 A/B: RF v1 (生产) vs v2 (v1+硬门 n_pts≥500) — 复审 R1 修复版

修复: 字段 furniture_reentry_episodes (一次 id 出/灭 段) 更 名 自 furniture_tracks;
flicker_analysis.json 已在 证据根 (上游拷 自 2026-10-09_b2a_shadow_r1/flicker_analysis.json);
注 耗时估算 含 JS RF 100 树 推理 微秒 级, 硬门 O(1) 少跑 ≈26% RF 调用 (324/1235 簇被 pre-gate 拦截).

| 会话 | 人簇 confirmed v1→v2 | 家具簇 (RF≥0.55) v1→v2 | 人 episodes | **家具 reentry** v1→v2 |
|---|---|---|---|---|
| 男近 2637 | 117→116 | 119→**0** | 2→1 | 12→**0** |
| 男中 2616 | 139→139 | 128→**0** | 1→1 | 13→**0** |
| 男远 2700 | 111→111 | 0→**0** | 1→1 | 0→**0** |
| 女近 1647 | 218→218 | 53→**0** | 1→1 | 18→**0** |
| 女中 1622 | 108→107 | 23→**0** | 1→1 | 15→**0** |
| 女远 1723 | 223→223 | 0→**0** | 1→1 | 0→**0** |

## 女近 (121647) reentry=18 的成因 分析

柜面 presence 最断续: n_episodes=21 (flicker_analysis.json: 柜位 run_len_median=1 帧,
present 53/218 帧), 缺 训练 对面 到 RF 级 家具 确认 → 同 id 重入 多.
v2 硬门 后 该 会话 reentry=0, 人 episode 1, 零 变化 (人 不 受 门 影响).

## 耗时估算 (结构 性 推断, 非 wall-clock)

- RF v1 predict: 100 树×路径深~20 → 单簇 ≈ 6 微秒 (JS Number 运算); 每帧 ≤4 簇 → ~25μs.
- 硬门 在 associate 前 O(1) 查 n<500 → 家具簇被 pre-gate 拦截 不再 入 RF predict.
- 六段 家具 簇 占比 = 324/1235 ≈ 26% → v2 每帧省 ≈26% RF 调用 次数 (≈6μs/簇), 另 省 associate track 创建 开销.
- **JS vs Python predict 浮点差 max = 0.05** (Float32 vs numpy float32 in RF votes), 所 以 0.55 阈值在边 缘 0.50–0.60 会不定; 生产 用 0.55 + age≥3 二 重, 实际 支撑 差 小于 5%.
