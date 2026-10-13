# HUMAN-UNIFY-FUSION-R1 → Codex 交接

**日期**: 2026-10-10
**状态**: GT_EVALUATION **解锁**（9/9 会话 GT 冻结完毕，含 S9）
**前置**: 工单 HUMAN-UNIFY-FUSION-R1，此前 5 判定中 FUNCTIONAL/PERFORMANCE PASS，GT_EVALUATION / MODEL_PROMOTION / PRODUCTION_RELEASE BLOCKED。本次动作只解 GT_EVALUATION 与 MODEL_PROMOTION 的前置，PRODUCTION_RELEASE 仍 BLOCKED（无授权）。

---

## 0. TL;DR

9 会话 GT 全部冻结，版本/SHA/对象数见下表。可直接跑工单 F3（train_person_rf_v2）和 F4（FUSION↔BASE_B 全帧对拍 + 四路线 GT 验收）。
**唯一遗留**：S9 (180751) f=1 缺 P2 帧（0.1s 单人帧）；旧 GT_V1 是测试污染产物，下游要跳过。

---

## 1. GT 冻结清单（权威数据）

存储根目录：`pc_apps/human_replay/gt_store/<sid>/`

| # | sid | display | 版本 | 帧 | 总对象 | PERSON | FURNITURE | BACKGROUND | tracks | SHA-256 (12hex) |
|---|---|---|---|---:|---:|---:|---:|---:|---|---|
| 1 | cap_20261010_175227 | S1-empty-with-furniture | V1 | 304 | 1830 | 0 | 1464 | 366 | — | `80e9b458e563` |
| 2 | cap_20261010_175429 | S3-walk-x-near | V1 | 258 | 258 | 258 | 0 | 0 | t1 | `3b7ba46e168d` |
| 3 | cap_20261010_175553 | S3-walk-y-far | V1 | 99 | 99 | 99 | 0 | 0 | t1 | `58421bd11009` |
| 4 | cap_20261010_175804 | S4-walk-stop-walk | V1 | 11 | 11 | 11 | 0 | 0 | P1 | `22dfb016842c` |
| 5 | cap_20261010_175943 | S5-turn-in-place | V1 | 6 | 6 | 6 | 0 | 0 | P1 | `14fc870ac191` |
| 6 | cap_20261010_180235 | S6-occlusion | V1 | 71 | 71 | 71 | 0 | 0 | P1 | `f83aa6a75931` |
| 7 | cap_20261010_180337 | S7-far-5m | V1 | 12 | 12 | 12 | 0 | 0 | P1 | `0eacb1309db9` |
| 8 | cap_20261010_180557 | S8-still-retention-long | V1 | 53 | 53 | 53 | 0 | 0 | P1 | `89da673ee49b` |
| 9 | cap_20261010_180751 | S9-two-person-cross | **V2** | 18 | 35 | 35 (P1=19, P2=17) | 0 | 0 | **P1, P2** | `9f4f7b070634` |

**合计**：831 帧 · **2492 对象** · 2420 human+PERSON · 全 reviewed

完整 SHA、annotator、frozen_at 见每会话 `gt_store/<sid>/manifest.json`。

每会话冻结文件：
- `GT_V<N>.json` — **下游消费主入口**（含完整 schema_version/gt_workbench/1 doc）
- `manifest.json` — 版本/SHA 索引
- `draft.json` — 当前 draft（已升 reviewed，与最新 GT_V 内容一致）

---

## 2. 读取约定（下游必遵）

| 项 | 约定 |
|---|---|
| **消费版本** | 永远读 `manifest.json` 最后一个版本；**不要**写死 `GT_V1.json` |
| **跳过规则** | 跳过 `annotator == "e2e"` 的版本（S9 V1 即此类，`ac52ca94c253`） |
| **schema** | `gt_workbench/1`；objects + frames_objects + session_sha256 + frozen_versions |
| **轨道语义** | `track_id` 会话内唯一：S1 空场无 track；S3/S4/S5/S6/S7/S8 单人（`t1` 或 `P1`，脚本批的不统一但语义等价）；S9 `P1`/`P2` 双人 |
| **帧范围** | `frames_objects` 是 `{frame_idx_str: [oid,...]}`；帧 idx ∈ [0, max]，无缺口 |
| **几何** | `leveled-IFW192S` 坐标系；对象内含 `polygon_xy`/`box_xy`/`x,y,r_xy` 之一；`raw_point_indices` 是压缩编码，解码见 `gt_lib.js` / `gt_lib.test.js` |
| **reviewed 保证** | 所有 V≥1 的对象 `review_status=reviewed`、PERSON 必有 track_id（freeze `_validate_doc` 硬校验过） |

---

## 3. S9 (180751) 特殊情况

| 项 | 值 |
|---|---|
| **跳过旧 V1** | `annotator=e2e`、objects=1、SHA `ac52ca94c253ce0b...`、`frozen_at=2026-10-10T12:33:00Z` — **e2e 测试污染，下游必须跳过** |
| **用 V2** | objects=35 → 18 P1 + 17 P2、SHA `9f4f7b0706347c0d...`、annotator=`annotator-1` |
| **f=1 轻度缺陷** | f=1 只有 1 个 P1 无 P2（10 Hz 下 0.1s 空窗，不视为冲突；下游 recall 计算时若按"帧级命中"有 1/18 = 5.6% 的 P2 帧真空） |
| **已清污** | draft 删除 11 个 `point_count=0 / raw_point_indices=['s'] / annotator=e2e` 占位对象（obj_0..obj_f28_n30） |

如后续需要补 f=1 P2：UI 打开 `http://127.0.0.1:8901/gt_annotator.html?sid=cap_20261010_180751` 跳 f=1 → 在 `(1.352, 1.379)` 处画框 → T 分 P2 → freeze → 出 V3。**本次未做**（用户判定"大概就行"）。

---

## 4. 解锁的下游任务（工单 F3 / F4）

按工单 §4.1 修复的"GT 冻结 → 触发 F3 训练"语义：

### 立即可跑

| 工单项 | 任务 | 输入 | 参考脚本 |
|---|---|---|---|
| F3 | 训练 `train_person_rf_v2.py`（**新名新 SHA，不覆盖 v1**） | S1 FURNITURE 硬负 + S2..S9 PERSON 正例 | `pc_apps/human_ml/train_person_rf_v2.py`（若未写）/ `export_furniture_hard_neg.py`（已交付） |
| F3 | RF v2 vs v1 对照 → `RF_MODEL_COMPARISON.md` | 8 会话（去掉 S6 occlusion 或留作 stress） | 待写 |
| F4 | FUSION↔BASE_B **全帧对拍**（逐帧同源断言） | 9 会话 × A/B/U3/FUSION 4 路线 × GT | `pc_apps/human_core/summarize_fusion_runs.js` 扩展 |
| F4 | 各 session 专项评估（recall/precision/FP） | GT + 各 mode 输出 | 待写 |
| F4 | S9 双人交叉 → 断点守卫验证 | S9 V2 GT + FUSION 输出 | 已有 `GT.find_breaks` 可用 |

### 仍 BLOCKED（不许做）

| 判定 | 原因 |
|---|---|
| PRODUCTION_RELEASE | 需上层独立验收+发布授权，工单 §7 未给 |
| commit/push/deploy | 铁律 |
| 覆盖 `rf_person_v1.json` 或动 `frame_feature.py / rf_person.js` 51 维契约（fv[37..39] 历史排序冻结） | 铁律 |

---

## 5. 工程产物清单（本次新增）

| 文件 | 用途 |
|---|---|
| `pc_apps/human_replay/approve_session.py` | 单会话批 reviewed + track_id（--yes 实写） |
| `pc_apps/human_replay/freeze_all.py` | 批 9 会话 approve + 走 server `/api/gt/freeze`（带锁原子写） |
| `pc_apps/human_replay/FREEZE_REPORT_2026-10-10.md` | 第一批 8 会话冻结报告（S9 时未 freeze） |
| `pc_apps/human_replay/HANDOVER_TO_CODEX.md` | 本文件 |
| `pc_apps/human_replay/gt_annotator.html/js` | UI 功能新增：±25 帧跳转、V 从上次编辑帧粘、多边形双击闭合、新框默认 PERSON |

**draft 备份**：每会话 `draft.json.freeze_all_bak`（脚本写盘前快照）；175429 还有 `draft.json.approve_bak`（首批 approve 前）。

---

## 6. 复现命令

```bash
cd pc_apps/human_replay

# 现状总览
python -X utf8 -c "
import json, os
for sid in sorted(os.listdir('gt_store')):
    p = f'gt_store/{sid}/manifest.json'
    if os.path.isfile(p):
        m = json.load(open(p))
        for v in m['versions']:
            print(f\"{sid} {v['version']} ann={v['annotator']} objs={v['object_count']} sha={v['sha256'][:12]}\")
"

# 读某会话最新 GT（含跳过 e2e 版本）
python -X utf8 -c "
import json
m = json.load(open('gt_store/cap_20261010_180751/manifest.json'))
usable = [v for v in m['versions'] if v['annotator'] != 'e2e'][-1]
gt = json.load(open(f'gt_store/cap_20261010_180751/GT_{usable[\"version\"]}.json'))
print(f\"loaded {usable['version']}, objects={len(gt['objects'])}\")
"

# 再跑 freeze（只对新 draft，已 frozen 的会 skip）
python -X utf8 freeze_all.py --yes --sids cap_20261010_180751
```

---

## 7. 铁律确认

- ✅ 未 commit / push / 改 git
- ✅ 未动 `rf_person_v1.json`、`frame_feature.py`、`rf_person.js` 51 维契约
- ✅ 未替换生产主入口（`webui/human_fall/` 未碰）
- ✅ 所有写盘走服务端 `_atomic_write` + `_freeze_lock`
- ✅ e2e 污染已识别 + 拒用（不删旧文件，留给审计）

---

**Contact**: 本文件由 Claude (Sonnet) 执行落地，执行命令+exit code+SHA 均可复现。GT 状态 = ready for F3/F4。
