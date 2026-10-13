# STEP 0 — GT_AUDIT (R3)

**日期**: 2026-10-10/11(**2026-10-11 修订 — S1 实际消费版本**)
**作者**: Claude (Sonnet)
**输入**: `pc_apps/human_replay/gt_store/<sid>/{manifest.json, GT_V*.json, draft.json}`
**目标**: R3 工单 §1 要求的 GT 独立核验（非表格 SHA 前缀）

> **修订注**: 2026-10-11 凌晨训练时发现 S1 propagated 副本的 point_indices 索引空间与下游 export_samples 不兼容，已重新生成 **V3** 并验证。本文档初版基于 V1，修订后描述**实际消费的 V3**。S1 manifest 当前最新为 **V3**。

---

## 1. 9 会话 manifest 核验完整结果

| sid | display | version | SHA-256 (16hex) | sha_match | objects | PERSON | FURN | BG | review |
|---|---|---|---|---|---:|---:|---:|---:|---|
| cap_20261010_175227 | S1-empty-with-furniture | **V3** | `1280d1953f2520b6` | ✅ | 1824 | 0 | 1520 | 304 | 1824/1824 |
| cap_20261010_175429 | S3-walk-x-near | V1 | `3b7ba46e168d8439` | ✅ | 258 | 258 | 0 | 0 | 258/258 |
| cap_20261010_175553 | S3-walk-y-far | V1 | `58421bd110095340` | ✅ | 99 | 99 | 0 | 0 | 99/99 |
| cap_20261010_175804 | S4-walk-stop-walk | V1 | `22dfb016842ca208` | ✅ | 11 | 11 | 0 | 0 | 11/11 |
| cap_20261010_175943 | S5-turn-in-place | V1 | `14fc870ac1918227` | ✅ | 6 | 6 | 0 | 0 | 6/6 |
| cap_20261010_180235 | S6-occlusion | V1 | `f83aa6a75931fc97` | ✅ | 71 | 71 | 0 | 0 | 71/71 |
| cap_20261010_180337 | S7-far-5m | V1 | `0eacb1309db92f4f` | ✅ | 12 | 12 | 0 | 0 | 12/12 |
| cap_20261010_180557 | S8-still-retention-long | V1 | `89da673ee49b446d` | ✅ | 53 | 53 | 0 | 0 | 53/53 |
| cap_20261010_180751 | S9-two-person-cross | V2 | `285c11026b57c5c6` | ✅ | 36 | 36 | 0 | 0 | 36/36 |

**总对象 = 2375**（PERSON 545 / FURNITURE 1520 / BACKGROUND 304 / UNKNOWN 0）
**总 human-source 对象 = 557**（剩余 1819 是 propagated = S1 1818 + S9 1）

---

## 2. SHA 算法复核

按 `gt_server.py` 的 `_freeze` 算法：
```python
payload = json.dumps(doc, ensure_ascii=False, indent=1, sort_keys=True).encode("utf-8")
sha = hashlib.sha256(payload).hexdigest()
```

9/9 会话：文件重算 SHA == manifest.versions[-1].sha256。无篡改。

---

## 3. 关键风险项

### 3.1 S1 (cap_20261010_175227) —  propagated 主导

| 项 | 值 | 风险 |
|---|---|---|
| 帧数 | 304 | ✅ 与 SESSION_DATASET_MANIFEST 一致 |
| **human 对象** | **6** （f=0 唯一直标帧） | — |
| **propagated 对象** | **1818** （303 帧 × 6 克隆） | **不能把 propagated 当 human-reviewed 消费** |
| FURNITURE:BACKGROUND | 5:1 per frame | ✅ 场景语义正确 （无 PERSON） |
| 空场无人 | 全部帧 PERSON=0 | ⚠ **下游不得把 FURNITURE 当人体正样本** |

**传播语义检查**（工单 §1 要求）：
- V1→V3 演进：**空间框传播 + 每帧独立选点**（不是字节级克隆 raw_point_indices）。V1/V2 历史版本 raw_point_indices 直接克隆 f=0 （越界下游）,**V3 才是合法可消费版**
- ✅ 坐标系一致：`coordinate_frame: leveled-IFW192S` 全程保持
- ✅ V3 propagated 对象的 raw_point_indices **都在 valid 后索引空间**（经 test_s1_v3_regression 1818 全通过）
- ⚠ **几何漂移未验证**：家具应该静止，但 propagation 假设 304 帧间 0 漂移是"理想近似"。真实漂移待 STEP 5 用原生点云做 consistency check（逐帧 FG 点 vs GT polygon 求 IoU 分布）。

**风险等级**: 中。RUNS 可接受，但**指标计算时标记 propagated 占 99.7%**，任何 P/R 不得被解读为"人工标的精度"。

### 3.2 S9 (cap_20261010_180751) — 真实双人 + 1 propagated

| 项 | 值 | 风险 |
|---|---|---|
| 帧数 | 18 | S9 短场景 |
| human 对象 | 35 | ✅ 人标 P1=18 + P2=17 |
| **propagated 对象** | **1** (`obj_f1_p2_propagated` at f=1) | 我补的，源=f=2 P2 克隆（同位置站桩） |
| track_id 组合 | P1=18, P2=17 | ✅ 双人区分清 |
| 同帧冲突 | 0 | ✅（修复后） |

**风险等级**: 低。1 个 propagated 是**同源克隆**，坐标 (1.352, 1.379) 与 f=0/f=2 一致；不影响双人 track 语义。

### 3.3 PERSON 会话 GT 完备性

- **S3-near (175429)**: 258/258 全覆盖 ✅
- **S3-far (175553)**: 99/464 帧（21%）——抽稀标注。**未标帧(365)不能当无人**；下游计算 recall 须只用 99 已标帧
- **S4/S5/S6/S7/S8**: 全部独立短场景，已标帧数=[11,6,71,12,53]，**不应将未标帧解释为无人**

### 3.4 工单一票否决项核验

- ✅ "不能把 propagated 伪装成逐帧 human-reviewed"：所有 propagated source 明确标注
- ✅ "空场会话不得因存在家具 GT 而被解释成人体正样本"：S1 PERSON=0，下游若开箱 GT_POS 会跳过 S1
- ✅ "任何 GT 质量问题应首先隔离和归因，不得静默修改已冻结版本"：除我之前 freeze 外未动 manifest，旧 e2e V1 用 annotator=e2e 标记显式跳过
- ⚠ "若传播的是空间框必须检查坐标系一致性与几何漂移"：只覆盖一致性，**漂移检查待 STEP 5 环节**

---

## 4. GT_POS / GT_FURN_HARD_NEG / SPLITS 定义（下游消费约定）

按 R2 `train_02` 已交付的产物定义（工单 §1 要求"明确 GT_POS、GT_NEG、UNKNOWN 的实际定义"）：

| 集合 | 来源 | 定义 |
|---|---|---|
| **GT_POS** | 非 S1 会话中 `class=PERSON` 的对象 | 当前 8 会话共 **545** 样本（510 human + 35 含 propagated 双人） |
| **GT_FURN_HARD_NEG** | S1 中 `class=FURNITURE` 的对象 | 1520 样本（**R2 用去重后 1216**，去重逻辑见 `train_02/frozen_gt.py`） |
| **GT_BG** | S1 中 `class=BACKGROUND` 的对象 | 304 样本（**R2 未用作训练**） |
| **UNKNOWN** | 未标帧 + `class=UNKNOWN` 的对象 | 现存 UNKNOWN=0，但未标帧应视为"不参与训练/评估"，不是负样本 |

**泄漏检查**（工单 §4 数据契约）：
- 同一 GT 源传播副本不能在 train/test —— **S1 的 1818 个 propagated 全部来自 f=0 6 个对象**，**如果把 S1 拆 train/test 就会全泄漏**。所以 **split 必须按会话级**，S1 要么整 train 要么整 test，不能拆。
- 同一帧内多对象空间分布相关性 —— S9 帧内 P1/P2 当然相关，拆开就泄漏。**S9 也必须会话级 split**。
- R2 已交 `train_02/SPLITS.json` 按会话划分。R3 沿用。

---

## 5. 帧号/对象 ID/坐标系/时间戳一致性

- 坐标系：所有对象 `coordinate_frame=leveled-IFW192S`、`leveling_transform_id=render_person_label.R/T` 一致 ✅
- 对象 ID 格式：`obj_f{frame}_n{seq}` 唯一，帧内不撞 ✅（V2 S9 有 1 个 `obj_f1_p2_propagated` 不规则但是唯一）
- 帧号：`frame_idx ∈ [0, max]` 无缺口（S1 0..303 / S3-near 0..257 / ...） ✅
- 时间戳：2030 epoch (2026-10-10) 一致；GT 自体时间戳是**标注时的 wallclock** 不是点云时间戳，**消费方不能用 GT.timestamp 评估时序** ⚠

---

## 6. GT 与原始点云绑定完整性

每个对象有 `raw_point_indices`（compact 编码）和 `point_count`。

抽样验证 3 个对象用 `gt_lib.decode_indices`（Node 实测）：

| sid / oid | class | point_count | decoded 长度 | match |
|---|---|---:|---:|---|
| 180751/obj_f0_n2 | PERSON | 1144 | 1144 | ✅ |
| 175429/obj_f10_n19 | PERSON | 1149 | 1149 | ✅ |
| 175227/obj_f0_n1 | FURNITURE | 2186 | 2186 | ✅ |

**绑定 OK**——compact 编码不是 1:1 长度，但解码后 == point_count。

---

## 7. STEP 0 结论

| 项 | 结果 |
|---|---|
| 9/9 会话 manifest 完整 SHA 校验 | ✅ |
| 全 reviewed 状态（freeze 硬校验过） | ✅ |
| 坐标系一致（leveled-IFW192S） | ✅ |
| 帧号无缺口 | ✅ |
| raw_point_indices 绑定完整 | ✅（3 抽样） |
| **可继续 STEP 1+** | ✅ |

**遗留 risk（不阻塞，但 R3 全程要披露）**：
- S1 propagated 主导 (99.7%)，指标计算须披露
- S3-far / S4/S5 抽稀标注，未标帧不视为无人
- GT 几何漂移未实测（STEP 5 做 consistency check）
- GT 时间戳是标注 wallclock，不能用于时序评估