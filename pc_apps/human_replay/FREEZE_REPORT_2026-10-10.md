# HUMAN-UNIFY-FUSION 工单 — GT V1 批量冻结报告

**日期**: 2026-10-10
**执行**: approve_session.py + freeze_all.py（实写+freeze）
**服务器**: http://127.0.0.1:8901 (gt_server.py 在线)
**annotator**: annotator-1（统一填；175429 原标注也是 annotator-1）

---

## 一、总览

| 指标 | 值 |
|---|---|
| 目标会话 | 9（工单 F0 全量） |
| **freeze 成功** | **8 / 9** |
| freeze 跳过 | 1（S9-two-person，track 冲突，须手工分 P1/P2） |
| 清污处理 | 180751 删除 11 个 e2e 测试占位对象 |
| 总冻结对象 | 2420 个（V1 合计） |
| 总冻结帧 | 831 帧（不含 S9） |
| 全程耗时 | 2 秒（实写+freeze） |

---

## 二、每会话 V1 冻结明细

| # | sid | display_name | 版本 | 帧 | 对象 | PERSON | FURNITURE | BACKGROUND | tracks | SHA-256 (前12) |
|---|---|---|---|---:|---:|---:|---:|---:|---|---|
| 1 | cap_20261010_175227 | S1-empty-with-furniture | V1 | 304 | 1830 | 0 | 1464 | 366 | — | `80e9b458e563` |
| 2 | cap_20261010_175429 | S3-walk-x-near | V1 | 258 | 258 | 258 | 0 | 0 | t1 | `3b7ba46e168d` |
| 3 | cap_20261010_175553 | S3-walk-y-far | V1 | 99 | 99 | 99 | 0 | 0 | t1 | `58421bd11009` |
| 4 | cap_20261010_175804 | S4-walk-stop-walk | V1 | 11 | 11 | 11 | 0 | 0 | P1 | `22dfb016842c` |
| 5 | cap_20261010_175943 | S5-turn-in-place | V1 | 6 | 6 | 6 | 0 | 0 | P1 | `14fc870ac191` |
| 6 | cap_20261010_180235 | S6-occlusion | V1 | 71 | 71 | 71 | 0 | 0 | P1 | `f83aa6a75931` |
| 7 | cap_20261010_180337 | S7-far-5m | V1 | 12 | 12 | 12 | 0 | 0 | P1 | `0eacb1309db9` |
| 8 | cap_20261010_180557 | S8-still-retention-long | V1 | 53 | 53 | 53 | 0 | 0 | P1 | `89da673ee49b` |
| 9 | cap_20261010_180751 | S9-two-person-cross | V1 (旧) | 18 | 47 | 47 | 0 | 0 | P1 (单人 tid) | `ac52ca94c253` ⚠ |

完整 SHA 见每会话 `gt_store/<sid>/manifest.json`。

---

## 三、freeze 输出产物

每会话目录下：

- `GT_V1.json` — 冻结 GT（只读基线，含对象 / 帧索引 / 元数据）
- `manifest.json` — `versions: [{version, sha256, frozen_at, object_count, annotator}]`
- `draft.json` — 当前草稿（已被脚本批 reviewed/track_id/annotator-1）
- `draft.json.freeze_all_bak` — 脚本写盘前的备份
- `draft.json.approve_bak` — 175429 前次 approve 备份
- `history.jsonl` — 编辑历史（未动）

### 文件大小（字节）

| sid | GT_V1.json | 说明 |
|---|---:|---|
| 175227 | 158,465,582 | 1830 对象 × 304 帧（最大，含全 ROI 点索引） |
| 175429 | 4,864,898 | 258 单人会话 |
| 175553 | 6,474,993 | 99 单人 |
| 175804 | 168,419 | 11 短片段 |
| 175943 | 111,050 | 6 短片段 |
| 180235 | 509,671 | 71 遮挡 |
| 180337 | 292,218 | 12 远距 |
| 180557 | 828,051 | 53 站立保留 |
| 180751 | **1,010** | ⚠ **e2e 测试残留**——非真实 GT，需重新标注+冻结覆盖 |

---

## 四、发现的问题（按严重度）

### 🔴 S9-two-person-cross (180751) — 不能 freeze

| 问题 | 现状 |
|---|---|
| 该会话是 S9 双人 | ✅ 工单 P0 |
| 当前 track_id | **全部 = "P1"**（37 个对象 36 个真实 + 11 个 e2e 假对象残留的旧 V1 manifest，draft 中全部 P1） |
| 同帧冲突 | **18 帧每帧 2 个 P1 对象** |
| freeze 校验 | `_validate_doc` 检测到"同帧同 track 多对象"会**拒绝**（错误：帧 X track P1 同帧多对象）|
| 旧 V1 (12:33 freeze) | annotator=`e2e`、含 11 个假对象（`raw_point_indices=['s']`, `point_count=0`），是测试污染 |

**解决（人工）**：
1. 打开 `http://127.0.0.1:8901/gt_annotator.html?sid=cap_20261010_180751`
2. 每帧选中第二个人 → 按 `T` 分 track_id=`P2`
3. 按 `H` 审每帧 → 点冻结（会生成 `GT_V2.json`，旧 V1 保留作审计参考）

### 🟡 清污记录（180751 draft）

为让 freeze 不被假对象拦下，脚本从 draft 删除 **11 个 annotator=`e2e`、point_count=0 的占位对象**：
- obj_0, obj_f1_n3, obj_f2_n6, obj_f3_n9, obj_f4_n12, obj_f5_n15, obj_f6_n18, obj_f8_n21, obj_f16_n24, obj_f23_n27, obj_f28_n30

`doc.annotator` 同时从 `e2e` 重置为 `annotator-1`。

**注意**：旧 `GT_V1.json` 仍含这些假对象——上次 e2e 测试意外 freeze 留下的产物。它**不应被下游消费**（下游应等 V2）。建议：
- 下游消费方统一从 `manifest.json` 读"最新可用版本"，并跳过 annotator=e2e 的版本。
- 或人工删除 180751/GT_V1.json + manifest.json 中的 V1 条目（非本脚本职责）。

### 🟢 其它会话

均单人或空场 + 家具场景，track_id 一致（单人=t1 或 P1），无冲突。

---

## 五、铁律复核

| 规则 | 状态 |
|---|---|
| rf_person_v1.json 不覆盖 | ✅ 全程未碰模型 artifact |
| 不 commit / push / deploy | ✅ 全程在 gt_store/ 内，未碰 git |
| 不替换生产主入口 | ✅ 仅 GT 数据，页面入口未改 |
| 输出写新目录 | ✅ 每个 GT_V1.json 是新文件；draft 改动有 .freeze_all_bak 备份 |
| 不冒充 GT | ✅ 所有 V1 都由服务器 `_freeze` 生成、走 `_validate_doc` 校验、写 manifest SHA |

---

## 六、后续步骤（按解锁顺序）

1. **人工**：S9 重新分 P1/P2 + 冻结 V2（解锁工单 P0 五项最后一项）
2. **自动**：跑 `train_person_rf_v2.py`（工单 F3），用 8 会话（含 S1 硬负）训练 v2 → 与 v1 对照
3. **自动**：四路线 GT 验收（F4），跑 FUSION↔BASE_B 全帧对拍 + recall/precision/FP
4. **人工**：OpenCode 独立复核 (`opencode-go/deepseek-v4.1-flash --agent plan`)

---

## 七、复现命令

```bash
cd pc_apps/human_replay
# dry-run
python -X utf8 freeze_all.py
# 实做
python -X utf8 freeze_all.py --yes
# 服务器现状
curl http://127.0.0.1:8901/api/gt/export | python -m json.tool
```

脚本：`freeze_all.py`（同目录），实现：draft 清污 → reviewed/track_id/annotator 批写 → 走 server HTTP `/api/gt/freeze`（带原子写 + 锁）。

---

**报告生成**: 2026-10-10，脚本自动生成
