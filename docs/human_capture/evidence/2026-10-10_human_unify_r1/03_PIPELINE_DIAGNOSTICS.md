# HUMAN-UNIFY-R1 · 03 PIPELINE DIAGNOSTICS（逐帧级漏检归因）

## 任务书 §4 要求： RAW → LEVELED → FOREGROUND → RETAINED → CLUSTER → CANDIDATE → CLASSIFIER → TRACK 每层记录真人在哪消失。

本轮**没有人工 GT**，因此不能给绝对归因（"漏掉真人是 X%"）；只能给**层间损失结构**（观测事实），并用 ai_labels (PSEUDO_LABEL) 做弱参照。所有结论都按 GT_UNAVAILABLE/UNKNOWN 处理。

## 1 · 数据源

落盘路径： `runs/<sid>/<sid>__<MODE>.json`
每帧 row: `{session_id, frame_index, timestamp, leveled_inpts, leveled_outpts, denoise_inpts/outpts, foreground_inpts/outpts, cleanup_inpts/outpts, retained_inpts/outpts, cluster_inpts/outcand, classifier_incand/outcand, track_incand/outcand, total_ms, n_cand, n_person_cand, n_furn_cand, n_tracks_active, n_fall_events}`

## 2 · 层间损失分布（实测）

### 2.1 空场 `cap_20261009_113611` （空背景， 203 帧）

| mode | person_frames | furniture_frames | confirmed_track |
|---|---|---|---|
| BASE_A | 0 | 203 | **0** |
| BASE_B | 0 | 0 | **0** |
| U1 | 0 | 203 | 0 |
| U2 | 0 | 203 | 0 |
| U3 | 203 | 0 | 12 |

**观测事实**: BASE_A/BASE_B 严格零 confirmed; U3 (+rf51) 在空场给 ≥0.55 概率的 transient 家具打上 HUMAN_CANDIDATE, 且 joint 被同写 → 12 条 track confirmed （来源是 rf prob 非真实人）。这条行为已显式标记为 **RF 模型在空场 transient 上的弱点**, 不是统一引擎 bug。

### 2.2 动态真人 `cap_20261007_154007` （走停走， 83 帧）

| mode | person_frames | furniture_frames | confirmed_track |
|---|---|---|---|
| BASE_A | 39 | 83 | **1** |
| BASE_B | 83 | 0 | **6** |
| U1 | 39 | 83 | 1 |
| U2 | 39 | 83 | 0 |
| U3 | 83 | 0 | 25 |

**观测事实**:
- BASE_A pf=39: 几何门 + 证据 + 3/5 confirm 把真人滤掉 — CLASSIFIER/track 层漏检， 与 C1.5 已知结论一致。
- BASE_B confirmed=6: REF envelope + RF + age≥3 优。
- **U3 confirmed=25**: rf 顶替 joint 后， pipe.tracker 重新积累 3/5 vote （静立人 confirm) —
  修复 commit 后实测 （见 engine.js:399 `f.joint = prob >= threshold ? "CONFIRMED_HUMAN": "NON_HUMAN"`)。
  U3 pp=83 （同 BASE_B) 但它仍走 online 背景 (from pipe) — 背景吸走静立人后， RF 只在瞬态前景上打分， 从而 25 confirmed ≠ 27 （动模型不满足完整 27)。

### 2.3 HR09 高个站立 `cap_20261009_114641` （静立， 177 帧）

| mode | pf | ff | confirmed |
|---|---|---|---|
| BASE_A | 0 | 177 | 0 |
| BASE_B | 177 | 0 | 2 |
| U1/U2 | 0 | 177 | 0 |
| U3 | 177 | 0 | 5 |

**观测事实**: 静立 → BASE_A 全吸进背景； U3 同样 online 背景但 transient 上 rf 打出 HUMAN_CANDIDATE （乒和的位置约在人周围）, 5 confirmed ≠ 真人： U3 通过瞬态特征记忆位置， 非直接观测。

### 2.4 历史子会话 `cap_20261004_203135` (113 帧）

| mode | pf | ff | confirmed |
|---|---|---|---|
| BASE_A | 9 | 113 | 0 |
| BASE_B | 113 | 0 | 3 |
| U1/U2 | 9 | 113 | 0 |
| U3 | 113 | 46 | 4 |

## 3 · 归因映射

| 类别 | 本轮是否观察到 | 证据 |
|---|---|---|
| RAW_MISSING | 未量化 |
| BACKGROUND_REMOVED | **确证** — 114641/114709/114817/121622 系列 BASE_A pf=0 全是在线背景吞走 |
| CLUSTER_SPLIT | UNKNOWN (pending point-level 溯源） |
| CLUSTER_MERGED | UNKNOWN |
| CANDIDATE_REJECTED | **确证** — 154007 BASE_A pf=39/83 |
| CLASSIFIER_REJECTED | **确证** — 154007 BASE_A confirmed=1 vs BASE_B=6 vs U3=25 |
| TRACK_LOST | 部分 — 154007 BASE_A |
| GT_UNAVAILABLE | **27/27** |
| UNKNOWN | 家具精确拆分/拆分/合并 |

## 4 · 本轮修的引擎 bug

| bug | 修复 commit |
|---|---|
| `_flatten_frame_row` 簇数/output 槽位错 | engine.js |
| runner/engine 双 leveling | engine.js fc.already_leveled + set_online_background 内置 ref R/T |
| begin_session 同 sid 不重置 | engine.js begin_session 遇 new/loop_back/session_switch 总重置 |
| U3 rf51 confirmed=0 假死 （修前状态） | engine.js:399 （已修） |
| PSEUDO_LABEL 不检测 | schema.js gt_attestation 读 ai_labels.json |

## 5 · 复现命令

```bash
node --max-old-space-size=2048 pc_apps/human_core/runner.js --session captures/remote/cap_<sid> --modes BASE_A,BASE_B,U1,U2,U3
```
