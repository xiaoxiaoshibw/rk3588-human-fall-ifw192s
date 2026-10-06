# Determinism

每 selector / session 重复运行 **20 次**，比较 selected ROI 序列与下游 summary
（已剔除 timestamp）是否逐字节一致。

| session | repeats | byte_stable |
|---|---|---|
| cap_20261004_202456 | 20 | ✅ true |
| cap_20261004_203135 | 20 | ✅ true |
| cap_20261004_203349 | 20 | ✅ true |
| cap_20261002_223757 (control) | — | v1 本就 fail，不参与 A/B determinism |

确定性来源：
- CURRENT v1：`np.unique`（排序）+ `sorted(components, key=...)` + 贪心 `min(key=(…, k))`；
- SHADOW：组合枚举顺序固定（`itertools.product`）+ rank 字典序含 `tuple(sorted(combo))` tie-break；
- 无 `set` 遍历、无随机数、无字典序依赖泄漏到结果。

✅ Determinism 前置条件满足，可进入算法结论。
