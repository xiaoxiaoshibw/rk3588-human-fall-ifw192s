# HFUS-D04 engine hook 登记表

日期 2026-10-11。基线（D03 run_b/engine/detector + contracts + eval）SHA 在 `BASELINE_SHAS.json` 冻结。本表只描述 `sidequests/human_fusion_lab_next/d04/run_d04.js` 在**当次 createDetector 返回的 engine 实例**上做的 monkey-patch；**所有只读源文件（background/contracts/eval/human_fusion_lab/**）二进制零改动**。

## 变体 → hook 点映射

| 变体 | 唯一 hook 点 | 作用机制 | 代码位置 (d04/run_d04.js) |
|---|---|---|---|
| `base` | 无 | 等价 run_b.js 的 B 模式 | — |
| `point30_only` | `pipe.PIPE.human_n_min = 30`<br>`pipe.cluster_features` 包一层 | `human_pipe_lib.js:583` 的 `n < PIPE.human_n_min` 门被替换成 `n < 30`，reason 同步 `points<30`；engine_b.js L238/L342 两处 `pipe.cluster_features(cl)` 调用点零改动自然走入新门 | `hookPointGate` |
| `point15_only` | 同上，但 n_min=15 | 同上 | `hookPointGate` |
| `unknown04_only` | 无（一组标记） | 保持 `detector_b.js:19` 写死的 `.4` 不动；`run_d04.js` 复用 `e._bg_diagnostics.reasons[]` 自带的 `no_bg_match_SUPPORTED` / `no_reference_XY_support_UNKNOWN` / `bg_voxel_match` 直方图（run_b.js L36 已写 SUMMARY/row.bg），只把 0.4 的值显式登记进 `variant_info` | `hookU04` |
| `split_only` | `pipe.voxelize`（透明透传，只为记 curFgFinal）<br>`pipe.cluster_voxels` 替换 | 对 `_fusion_a_chain` 内 `pipe.cluster_voxels(pipe.voxelize(fg_final))` 这一唯一调用点（engine_b.js:335）插入：每个原始簇先过 `cluster_features`，若 `radius_m > human_radius_max` 或 `height_m > human_height_max` → XY BFS 分量（0.45m=3 voxel hop）→ 每分量内 z-hist 0.15m 峰分离（空槽 ≥2 bin 切）→ 子簇重算 acc → 重走 `cluster_features + classify_human` → 子簇替换原簇进入下游。`engine._split_log` 每帧清，被 run 循环写进 row.split_log。**不用 GT**。默认关（非 split 变体不挂） | `hookSplit` |

## 关键保证

- 所有 hook 在 `B.createDetector(ref)` 返回的**单次实例**上生效；每 session 重新 `createDetector`，hook 不跨 session 污染。
- `instrument(engine)`（eval/instrument.js）在 hook 之后调用；它包 `voxelize` 时看到的是我的包装，二者串行透明。
- `check_d04_hooks.js` 验证：
  - P30/P15 门被拒 (`points<30` / `points<15`)，且 `pipe.PIPE.human_n_min` 骤变限定在该实例。
  - SPLIT 默认关 → `engine._split_log === undefined`。
  - SPLIT 真帧（audit sessions[0] frame 0）跑 `_fusion_a_chain` `_split_log` 被填为数组（本次为 `[]`，异质簇未触发——保守拆分器设计语义）。
  - SPLIT 合成 z 双峰 600 pt 簇（z=0.2-0.6 / 2.4-2.9，XY 0.45m 内单 voxel cluster）→ 拆出 2 × 300 pt 子簇。
- `run_d04.js` 顶部 `mode = 'D04_' + variant`，避免与 run_b 的 `B_cap_*.jsonl` 混淆（满足「ledger mode 字段与 base 目盲」约束）。

## 下一代理可直接运行

```bash
# 单变体（默认 outdir = docs/human_capture/evidence/2026-10-11_hfus_d04_r1/runs/<variant>）
node sidequests/human_fusion_lab_next/d04/run_d04.js base
node sidequests/human_fusion_lab_next/d04/run_d04.js split_only
node sidequests/human_fusion_lab_next/d04/run_d04.js point30_only
node sidequests/human_fusion_lab_next/d04/run_d04.js point15_only
node sidequests/human_fusion_lab_next/d04/run_d04.js unknown04_only

# 指定 outdir 或 sid 过滤
node sidequests/human_fusion_lab_next/d04/run_d04.js <variant> <outdir> [sid,sid,...]
```

## 副作用/边界

- 拆分器是几何驱动的保守实现（XY 距离 > 0.45m 或 z 空槽 ≥2 bin 才切），纯几何无法可靠分离的近邻混合簇（人+家具 < 0.45m 且 z 重叠）**不被拆分** — 符合 D04 预登记「拆分误分不强制有用」原则。
- SPLIT 现行实测 0 触发可能成立；`SPLIT_ARMED_LOG_N=0` 是该变体正常语义的候选输出，不是 bug。
- `hookPointGate` 的 reason 字符串与上游 `points<60` 不同；下游 `ledger.components.rejection_reasons`（instrument.js L16）将看到 `points<30` / `points<15` —— 属预期变体侧信号。
