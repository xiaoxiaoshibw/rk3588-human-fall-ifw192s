# HUMAN-UNIFY-R1 · 02 DATA AND GT AUDIT（数据与真值审计）

审计日期 2026-10-10。数据根 `captures/remote/cap_*/`。详细 inventory: `01_data_audit/sessions_inventory.json` (27 sessions, UTF-8 落盘）。

## 1 · GT 来源三级分类（映射到任务书）

| 等级 | 本库实例 | 数量 | 用途 |
|---|---|---|---|
| HUMAN_VERIFIED | 无 | 0 | — |
| HUMAN_UNVERIFIED | 无 | 0 | — |
| PSEUDO_LABEL | `*/ai_labels.json` （由 `auto_person_label.py+empty-template-bgdiff` 生成， `confidence:auto`） | 11 段 （全 HR09) | **训练 RF 标签** — 不是测试 GT |
| UNKNOWN | `cap_20261007_143945`...`154920` （动态， 无 ai_labels) | 5~6 段 | 无法直接量化， 需层间诊断 |

**结论**: 本库没有任何可称为"人工金标"的逐目标 GT。C1.5 的 29/83 覆盖数字是 probe.json 的 candidate center 统计，不是 GT。本轮**不会生成虚假人工 GT**，全部精确率/召回率指标按 UNKNOWN/NOT_MEASURABLE 报告，只对比**相对指标**（层间损失分布、家具 vs 真人候选占比、跟踪稳定性、耗时）。

## 2 · 数据清单（按采集段/场景/人员划分 — 不随机按帧）

| 组 | 段 sid | 帧 | MB | 场景 | 姿态 | 人员 | 域 |
|---|---|---|---|---|---|---|---|
| G-empty | `cap_20261009_113611` | 203 | 279.2 | 空场景模板 | — | — | 空场 |
| G-c1dyn | `cap_20261008_114205/114254/114340/114422` | 244-281 ×4 | ~1200 | C1 动态捕捉/逼近前/逼近活跃/逼近后续 | walk | 1员 (C1) | 动态 |
| G-hr09-chen | `cap_20261009_114641..114817` (5) | 99-177 ×5 | ~1050 | HR09 高个加权 | stand | 高个员 (A) | 站立多距 |
| G-hr09-girl | `cap_20261009_121622..121723` (3) | 107-223 ×3 | ~750 | HR09 女孩 | stand | 女孩 (B) | 站立多距 |
| G-hr09-man | `cap_20261009_122616..122700` (3) | 111-139 ×3 | ~500 | HR09 男人 | stand | 男 (C) | 站立多距 |
| G-c15 | `cap_20261007_143945, 154007, 154920, 154545...` | 83-108 ×2-4 | ~500 | C1.5 动态/走停走/静态 | walk/still | 1员 | 动态验证 |
| G-other | `cap_20261002_165321_clip..., 223757, 203135, 203349, 215540, 150455...` | 8-113 | ~700 | 旧库 | ? | ? | 未知 |
| G-trim | `cap_20261002_165321_clip_*` | 8 | 11 | 裁剪测试 | — | — | 仅供 trim 测试 |

训练/验证/测试划分方案（下一轮实现 STEP 4 时遵守）：
- **按段隔离**（一段只进一个 split）+ **按人员隔离**（A/B/C 不跨 split）
- HR09 12 段已形成 RF 训练集 → 任何分类器评估**必须**用 G-c1dyn / G-hr09-? leave-one-person-out 做 holdout，不得用同帧/同段
- G-empty 只做空场无误检回归
- G-c15 / G-c1dyn 用于动态层间诊断 (STEP 2)，无 GT → 层间损失分布归因

## 3 · 与 ai_labels.json 的契约

```json
{
 "session_id": "...",
 "labelled_by": "auto_person_label.py+empty-template-bgdiff",
 "posture_set": ["stand"],
 "frames": { "<fi>": {"posture":"stand","x":1.764,"y":1.147,"r_xy":0.6,"n_hot":1632,"z_max":1.853,"confidence":"auto"} }
}
```
仅用于：
1. RF 训练可选 ROI 中心（posture=stand → person；none → noperson）
2. 层间诊断时作**参考点**（非 GT），找出在 r_xy 内的真人点期望位置

禁止：
- 把 `ai_labels.json` 帧数当 GT 覆盖率
- 从中导出 precision/recall/F1
- 它不能进 HUMAN_VERIFIED 测试集

## 4 · probe.json 的角色

11 段有 `probe.json`（每帧 candidate center, r90, n_hot, z_p90），这是路线 A 的 probe 探针序列，可用于：
- 观测 candidate 轨迹的**时间一致性**（同一人抖动小）
- 不能直接算精度（仍非 GT）

## 5 · 数据缺口（必须明示）

- **家具负例缺**: 当前只有正面"人 vs 空背景"; HR09+C1 没有"干净家具环绕无人"集合 → 家具误检率不可测 → UNKNOWN
- **跌倒标签缺**: 0 段 fall 姿态 → fall 性能不可测
- **跨家具场景缺**: 沙发/床/椅不存在 → 家具判别力 UNKNOWN
- **动态 walk 标签缺**: G-c1dyn 4 段无 ai_labels → 动态召回不可测， 只能层间归因
- **多人缺**: 无 ≥2 人段 → 多目标跟踪 ID switch 不可测

## 6 · 数据与标注 SHA

`/captures/remote/*/points.bin + meta.json + ai_labels.json` SHA 列表见 `01_data_audit/sessions_sha.json` （下一轮生成，避免扫描 ~6GB）。

## 7 · 本轮使用策略（诚实声明）

- 精确率/召回率/F1: **NOT_MEASURABLE**（无 HUMAN_VERIFIED GT）
- A/B 对比只比：
  - 层间每帧存活点数（survey-able 实测）
  - 家具误检在空场/纯家具负例（受限）
  - 候选中心 jitter （probe.json 二次分析）
  - 跟踪 ID stability （通过相对一致性自评）
  - 处理耗时 （实测）
- 任何"更高概率 = 更准确"的解释禁止出现
