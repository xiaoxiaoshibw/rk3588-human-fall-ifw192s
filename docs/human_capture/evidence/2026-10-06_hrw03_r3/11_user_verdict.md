# W03-R3.0 用户判定记录（正式锁定）

- 日期：2026-10-06（Asia/Shanghai）
- 来源：用户对 [10_summary.md](10_summary.md)（R3.0 Static Leakage Audit）的评审回复。
- 本文件为新记录：不改写 `10_summary.md` 的历史表述（其 §5 的「待用户确认」由本文件正式关闭）。
- 生效判定：**W03-R3.0 Static Leakage Audit = PASS / ROOT CAUSE IDENTIFIED**；同意**停止继续调 R2.6b**。
- 关联验收规范：[W03_R3_ACCEPTANCE.md](../../W03_R3_ACCEPTANCE.md)（本判定同步写入其 §0–§4）。

## 1. 用户判定正文（摘要）

```text
W03-R3.0 STATIC BACKGROUND LEAKAGE AUDIT

STATUS: PASS / ROOT CAUSE IDENTIFIED

Primary causes:
1. online background occupancy denominator contaminated by occlusion
2. >=2 points/frame observation gate rejects sparse static surfaces
3. center-distance matcher is geometrically mismatched to voxel occupancy

Rejected fixes:
- lower 0.65 occupancy threshold
- radius-only expansion
- modify R2.6b
- persistence-only static deletion

Next:
R3.1 immutable empty-scene reference builder
R3.2 cross-session leveled reference alignment/matching audit
R3.3 voxel-surface background matcher only after R3.2 evidence
```

完整因果链（用户确认）：静态物 → 背景建图受遮挡 → occupancy 分母被污染（`occ(≥2)=0.593 < 0.65`）→ 未进 background map → 每帧成为 foreground → R2.6b 正确保留大连续结构 → HUMAN_SHAPE 恰好通过 → 3/5 confirmation → 长期绿色假人。

## 2. WD01 / WD02 正式锁定（金标负样本）

### WD01 — Persistent upright static false human

```text
sid: 223757
coord: ≈ (3.50, -0.76)          （leveled/console 口径）
height: ≈ 1.74 m
points: ≈ 950
persistence: 0.864
motion: ≈ 0.01 m

Expected（R3 完成后）:
green = 0
purple = 0
static object absorbed by background
active human preserved
R2.6b cleanup_split_delta = 0
```

### WD02 — Sparse far-field static background

```text
sid: 203349
representative: (43,17) 桶, n≈778（0.25m XY 分桶）

Expected:
foreground static candidate = 0
no new green
no new purple
```

- 截图口径：用户截图与审计数值 **visual correspondence highly consistent**；未做截图坐标级验证（`coordinate-level verified` 不宣称）。
- WD01 的最终吸收性验证属 R3.2 跨会话 match audit（223757 current vs 203349 reference），本轮（R3.1）不预先断言。

## 3. 新增正样本门 HP01–HP03（R3 验收矩阵必含）

| ID | 姿态 | 要求 |
|---|---|---|
| HP01 | standing human | retain |
| HP02 | bending human | retain（与背景判据重叠最大，最关键） |
| HP03 | lying / fall posture | retain |

原因（用户）：R3 动的是 **background layer**；一旦过强，最危险的 regression 不是 split，而是「直接把人吞进背景，后面所有算法都再也看不到他」。

## 4. 口径规则（写进后续所有 W03 验收规范）

> 从 R3 开始，生产行为验收必须以 console 的 leveled pipeline 为权威口径。Raw 只能作为算法诊断辅助，不应该再拿它作为最终绝对 green 数量的验收基准。

- 依据：223757 raw green=35 vs leveled green=132（R3.0 附录 A）。
- R2.6b 的 raw 口径 AB 相对结论（split/new-green 相对门）不因此失效；失效的是 raw 的**绝对**数量基准。

## 5. 设计约束（用户本轮指定）

1. 拆步执行：不同时改 builder、坐标、matcher（R3.1 → R3.2 → R3.3）。
2. R3.1：`voxel ≥1 point → observed_this_frame=true`；`O_v = #observed 帧 / N_reference 帧`；跨帧 persistence；不沿用「每帧 ≥2 点」。
3. 不能马上把 203349 当最终 reference（Δroll≈2.58°，3m 处≈0.135m，已达匹配半径量级）；R3.2 第一件事必须是 leveled-reference → leveled-current 跨会话 match audit；不能直接把 reference 接到 production。
4. matcher 不简单改 0.20m；推荐点→占用体素 AABB 距离（R3.3，仅当 R3.2 证据支持）。
5. 两级地图：immutable reference（场景原有）+ online（运行后缓慢学习）；REFERENCE_STATIC 优先级 > ONLINE_PERSISTENCE。
6. persistence 暂不参与强删除（仅 diagnostic/confidence）；已有 HUMAN track 不因后续静止被吸回背景。
7. 不动在线 0.65：synth 弯腰人 `occ50≈0.58`，下调会开始吞人。

## 6. 下一步（用户指定顺序）

1. **R3.1** immutable empty-scene reference builder —— 交付记录见 [r4 证据](../2026-10-06_hrw03_r4/04_summary.md)。
2. **R3.2** 跨会话 leveled reference alignment/matching audit（223757 vs 203349 reference）。
3. **R3.3** voxel-surface background matcher（仅当 R3.2 证据支持）。
