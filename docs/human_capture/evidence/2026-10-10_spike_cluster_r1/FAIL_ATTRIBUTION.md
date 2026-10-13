# 失败案例归因 — CLUSTER-ADAPTIVE-SPIKE-R1

日期: 2026-10-10
对照: A (5cm 网格 8 邻/现状), B (eps(r)=max(0.08, 0.0092·r−0.0031) 对称门), C (B + 点级 5 z-band 防并簇)

指标口径:
  - **hit**: 人锚 (r=0.55) 被某 top4 簇覆盖 (d_anchor ≤ 0.55, 中位 cx/cy)
  - **t1**: 人锚被 top0 簇覆盖
  - **sf**: 人锚外 [0.55,1.5]m 内、n≥30、zmax>0.5、且非柜位的残片簇数
  - **cab**: 柜锚 0.30m 内被某 top4 簇覆盖 (捕获率)

## 1. 逐帧级**零差异**: A vs B vs C 在人锚命中上**完全一致**
脚本: `pc_apps/human_ml/spike_cluster/crosscheck_diff_frames` (现场计算差帧)
数据: 2874 帧 (n_hot>0), 12 评估段 + 4 ref + 空场, 3 变体
输出: `n_diff_frames: 0`

含义: **B/C 没有把人找得更准或更差** — 它的差异完全在"哪些小簇通过 min_points" 和 "柜的频发性" 上, 不在人锚命中上。

## 2. fail 案例 1: 121622 C 反而比 A 差 (cab=53.3% vs A=21.5%)
触发条件: C 的 5 z-band 把"柜位热点 cell"按 zband 拆成多个 subcell, 但柜位 zmax=1.71m 落在 band(1.30,1.75] — 与人主带同 band. C 的 z-band 分辨不开。
证据 (eval_frames.jsonl cap_20261009_121622 f0):
```
A:   rank0 PER[n=2007]                              (柜位 n<30 被滤)
B:   rank0 PER[n=2008]  rank1 CAB[n=55 zmax=1.83]   (55>30, 纳为候选)
C:   rank0 PER[n=855]   rank1 PER[n=699 z=0.85]
     rank2 PER[n=452 zmax=1.74] rank3 CAB[n=34 zmax=1.71 d_cab=0.053] (过 30 门)
```
根因: C 的 z-band 是粗粒度的"必拆", 把柜内的跨带 cell subcell 后, 每 subcell 各自成簇, ≥30 即过 门. 这是 SF>1 的副作用. **C 在同 band 场景无解.**

## 3. fail 案例 2: 121622 B 柜捕获率 (46.7%) > A (21.5%)
触发条件: B 的 eps(2m)=0.015m 在 cell 域 `ceil(0.015/0.05)=1 cell` 与 A 同 (8 邻),
但 `eps_ref = min(eps_c, eps_n)` 在中位仍大于 A 隐含的 cell 距离上限 (2-cell 形式化),
导致 B 让柜位 cell 间偶发桥接, 柜簇通过 min_points=30.
证据: 121622 全帧 B fr=8 > A fr=1.

## 4. fail 案例 3: stand 域, C 把人拆成 3-4 段
触发条件: 5 z-band (0.10-0.85/0.85-1.30/1.30-1.75/1.75-2.20/2.20+) 把人躯干"按带分簇".
证据 (per-frame PER 分布):
```
stand  A: PER=1 in 1517/1517 frames
stand  B: PER=1 in 1517/1517 frames
stand  C: PER=3 in 500 frames, PER=4 in 1017 frames
```
含义: hit 仍为 100%, 但**人不再是一个簇**, 对应下游 (track 关联 / RF 输入 / 渲染) 都受影响.
**C 的设计在站立域是错的.**
但"sf 站立域" C 全 0: 即 C 把 anchor 外小残片**并入人 band 簇** (sf=0). 它在控制残片上有用.

## 5. fail 案例 4: 215540 静立: A/B/C 都没把人"变大"
触发条件: 静立人种已 z 全 band 稀疏 (z_max=1.77, n=550), A 已把人 isolate 成簇, B/C 无法再增大它。
证据: A/B/C 三变体 top0..top2 在 f0-f63 里人簇位置 (cx=2.09, cy=-0.54) 完全一致,
       n=550 相同, frac_in_anchor 0.42-0.50.
这证实 memo 已记的: **静立问题不在聚类层**, 而在 find_hot/BG 吸收层 (STILL_PERSON_RETENTION_PLAN 设计域).

## 6. fail 案例 5: GT 锚半径 0.55m 的 anchor circle IoU 定义脆弱
所有 hit/t1 判断基于 d_anchor ≤ 0.55 (中位 cx,cy 距离), 不是真 IoU.
frac_in_anchor = 簇内点落 anchor 圆的比例, 在 stand 域很准 (≥0.95) 但在 still 域 0.42-0.50.
**但 cx,cy 是 median, 不是平均值; 圆外稀疏点不影响呼 — 该近似被记录在 README §6 与 SUMMARY 里都未提示**, 审计发现已列为 FAIL (审计点 #6).

## 7. pass 案例 1: stand 域, C 把 sf 全 0 (从 A up to 177)
触发条件: 站立手臂残片 (121622), A 有 177 sf, C 全 0 — 被并入相应 z-band 人簇.
这是 C 的**真实价值**: 它的 z-band 并簇有副作用 → **把残片吸掉**.

## 8. pass 案例 2: 122616/122637 C cab=0 (vs A 90.6/93.1%)
触发条件: 柜位 zmax≈1.85-1.90m > 人主带 (1.30-1.75) → C 把柜放 band 4 (人 band 3), 独立 subcell, 不与人关联.
**这证实 C 工作原理 — 拆不同 zband 的物体.**
但如 §2, 同 band 失败.

## 9. 不可归因域 (诚实 UNKNOWN)
- r_xy > 3.0m 真人 GT: 无 (C1.5 §2); B/C 在 r>3m 是否能改善人簇? **UNKNOWN**, 需要远距采集
- r_xy < 1.2m 真人 GT: 无 (122637 r=1.26m 是最低的); B/C 在近距是否有粘连风险? **UNKNOWN**
- 走动人 (158 帧) 154007 GT 只用 tuning, 不能下评估裁.
- 弯腰/躺卧/多人 GT: 无 (仅 synth_bend_v1). B/C 在低姿态域表现 **UNKNOWN**.

## 10. 消除歧义 — "柜位"是否同一物理柜?
按 2026-10-09 b2a_shadow_r1 文档, 4 段柜位锚点 (3.00,1.14 / 3.63,0.78 / 2.89,1.25 / 3.66,0.74) 本会话主体归属同一房间,
但这些锚位置各异的 leveled transform 差异 ~0.3-0.7m; **未人工逐簇确认同一物理柜**.
**判定**: **侧是按 b2a_shadow_r1 推定的 "稳定 RF 假阳性位置"**, 本次 spike 遵循文档口径.

## 11. 关于"距离自适应"的本质判定 (任务 #7 要求)
事实: 12 段站立域里 A/B/C 人锚命中**逐帧完全一致** (n_diff=0).
这只能推出两层意思:
1. **"人簇碎"这个假设在这批会话里不成立** (人主簇本来就是 5cm 8 邻能搞定的).
2. 自适应半径 **没有增益** (评估范围内), 只是**无效变化** — 主要改的是 "哪些小簇过 30 点门" 和 "柜被切分/b 桥接" 的频度.

**判定**: 自适应半径不是本批次 (1.2-3m, 站立+短静立) 场景下的正确问题解决方案.
