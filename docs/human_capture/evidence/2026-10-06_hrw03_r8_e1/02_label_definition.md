# 02 · E-1 标签定义（宁 UNRESOLVED 勿 MOVABLE）

标签只在一个体素 `covered == 165` 时才有资格给出 **STATIC / MOVABLE**；否则强制 `UNRESOLVED`。

## 1. 前置：覆盖判定（registration 排除器）

对 universe 体素 v（参考体素，形心 c ∈ ref lev 系）：

1. 计算 `d_v_inside` —— c 与"当前在线 map（tier≠none）形心集合经 `R_icp·c_cur+t` 投到 ref lev 系"的 ±1 邻域内最小距离（production matcher 语速 ±1 邻域充分）。
2. 计算 `d_v_any` —— c 与"当前在线 map（全部 occ 记录）投到 ref lev 系"的全场最近距离。

```
dgeo_cov(v) :=  in      if d_v_any ≤ 0.12
                shell   if 0.12 < d_v_any ≤ 0.24
                far     if d_v_any > 0.24
                null    if 没有 online 记录（registration 整体不可信）

covered(v)  :=  165     if dgeo_cov(v) == "in"
                0        otherwise
```

**目的**：只要 online map 的空间几何（经固定 ICP）都无法把当前场景映射到 v 的 0.12 m 内，就无法区分"v 的消失"是「static 物体移动」还是「registration 残差导致的错位」——一律走 UNRESOLVED。

## 2. 支持状态（per-frame）

对 `covered == 165` 的 universe 体素 v，逐帧在 223757 上：

- `SUPPORTED`（2）：在线 map 中 ±1 邻域内存在一个 tier≠none 的体素，其形心（投到 ref lev 系）到 c 的距离 < 0.12，且该体素在**该帧**的原始 raw 3D 体素 `hits ≥ 1`（与 builder 的 ≥2 门无涉——支持用 ≥1 在场计数）。
- `INDECISIVE`（1）：存在 tier 记录但上面任一条件不成立（距离不中 / 帧 hits 缺）。
- `ABSENT`（0）：邻域内完全没有 tier 记录。

- 附加独立的"在当前会话 raw 点内直接落"位图（**voxel-presence**，无距离判定）：
  `cur_visible[f] = 1` iff 第 f 帧 raw 点（leveled）经 `R_icpᵀ·(p−t)` 后 `key_bg(q) == v.key`。
- reference 侧对应的 `ref_present` 位图同理（在 203349 raw 内）。

## 3. 标签（简洁三态）

| 标签 | 判据（全部在 covered==165 时才生效） |
|---|---|
| **STATIC** | `absent 最长 run ≤ 3` 且 `SUPPORTED 命中数 ≥ 165 − 3`（容忍很短帧级 jitter；无持续缺失）。 |
| **MOVABLE** | 下面任一条：<br>① 出现起一次 `SUPPORTED→ABSENT` 或反向的明确转变，且正向 `run ≥ 5` 且反向 `run ≥ 8`（遮挡解释被排除，因为遮挡引起的 usually 只占 1–2 帧）。<br>② `cur_visible` 的占用 ≥ 0.90 且 `SUPPORTED 命中数 == 0`（**可见但从未被支持**；说明 reference 上有这个状态，但当前在线 tier 从未吸收它——这是"在线 tier 受遮挡/阈值污染"的空间证据，不是 static 本身移动）。 |
| **UNRESOLVED** | 其余全部；特别地，`covered != 165` 一律走此（registration 残差无法排除的情况）。 |

## 4. 设计取舍

- 不把「与人同出现」直接当 MOVABLE——subject phase 只作**独立证据**记入每体素 `phase_sup_frac`，判定仅靠可持续时间转变；
- 只有 ≥1 帧 `hits` 也视作 SUPPORTED（不和在线 ≥2 门绑定）；
- MOVABLE 判定是**空间在线污染**与**真实移动**不可分的空间证据——它在 E-1 里的意义是"reference 的这条记录在在线侧不可用"，并不尝试区分污染机制（M1/M2）；
- 控制区 sanity：如果 WD01 / WD02 大量 MOVABLE，说明 audit label / registration conditioning 有问题，立即停止 E 层解释（工单 §9）。

## 5. 最终标签数据（本轮实测；详见 `08_final_attribution.md`）

| 类别 | 数量 | 比例（universe=3707） |
|---|---:|---:|
| STATIC | 681 | 18.4% |
| MOVABLE | 360 | 9.7% |
| UNRESOLVED | 2666 | 71.9% |

MOVABLE 的 rule 分布（360）：
- `M2:visible_never_supported` = **360**（**100%**）
- `M1:sustained_transition` = 0

→ MOVABLE 全部是"reference 可见但当前在线 tier 从未支持"的**在线侧污染**空间证据，不是"reference 复制了 movable state"。
