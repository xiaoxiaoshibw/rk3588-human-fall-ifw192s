# HUMAN-UNIFY-R1 · 00 BASELINE（冻结基线）

| 项 | 值 |
|---|---|
| 日期 | 2026-10-10 |
| 分支 | `master` |
| HEAD | `347a5bf` "B2a RF 分类接件: joblib→json 12/12 推理对齐 + JS 51维 特征 + 簇过滤" |
| 工作树 | 30 个 dirty 生产文件（用户其它任务），**全部保留不动**，见 git status |
| 授权 | 一次性完成本轮工程交付；不得修改生产识别核心、不得部署、不得声称算法/生产验收 |

## 0.1 真实调用链（源码已审计，非 README 推断）

### 路线 A · 传统人体识别 `human_detect.html`
```
replay.js(set_idx) → detect_ui.on_frame(S)
  → human_pipe_lib.pipeline_frame(xyzi, frame_idx, ctx)
      denoise → extract_foreground(static_map 或 fused)
      → cleanup_isolated_fg (R2.6b 拓扑保护)
      → cluster_voxels (XY 0.15m 柱 BFS, min_voxels=3)
      → evidence_postpass + cluster_features
      → classify_human (硬门: height/width/radius/upcos → HUMAN_CANDIDATE|NON_HUMAN, **不发 HUMAN**)
      → evidence_label (spread_cv → HUMAN_SHAPE|SOLID_UNIFORM|AMBIGUOUS)
      → joint_status = gates × evidence
      → Tracker.tick (EMA α=.35, gate .75m, lost_max=8)
      → fall_assess (upcos<0.45 且 height<0.9 持续10帧)
  确认语义: CONFIRMED_HUMAN 需 HUMAN_SHAPE + HUMAN_CANDIDATE + 3/5 帧时间确认 + age≥3
```
- UI 由 `detect_ui.js` + `human_detect.js`（Three 渲染）驱动。
- production 已交付： 距离感知 zRange (0.5m/2.5m/11.5m)、ego-only 全视图字段级 swap、静态包络身份缓存、γ 暂留 +0.06/τ=3.5/alpha=0.35、换会话零红点。

### 路线 B · RF 人体识别 `human_track.html`
```
replay.js(set_idx) → HUMAN_DETECT_OVERLAY.on_frame(S)   [detect_overlay.js]
  → level_frame (硬编码空场模板 R @xyz + T, 或 meta.leveling 直透)
  → find_hot (5cm 背景包络 BG[key], z>bg+0.25 为热点)
  → find_clusters (5cm 网格泛洪, min 30 点, 取前 4 大)
  → [可选] rf.extract (51维) + rf.predict_person (100 trees) + ≥0.55 过滤
  → associate (gate 1.0m, claimed 集合同帧一对一, FIX-1)
  → age≥TRACK_MIN_AGE(3) 且过 RF → shown/confimed
  → HUD: "人 N 个 (track #i)"; 3D 红点 + Sprite 标签
```
- `detect_overlay.js` **没有独立时间确认状态机**（不同于路线 A 的 3/5 帧票窗）；跟踪即 age。
- 空场 BG envelope 来源 `bg_envelope.json` （由 `dump_bg_envelope.py` 从 113611 导出）。

## 0.2 已识别的重复实现 / 接口不兼容

| 能力 | 路线 A | 路线 B | 状态 |
|---|---|---|---|
| 体素化 | `voxelize` (0.15m XY 柱) | `find_clusters` (5cm 网格) | **重复**，不同分辨率，不同目的 |
| 协方差特征 | `cluster_features` | RF `frame_feature.extract` | **重复**，维度/口径不同 |
| 背景 | `build_static_map`（online, 本帧见 ≥2 点） | 空场包络 BG（offline, 每帧 ≥1 点） | **重复**，语义相反 (online vs ref) |
| 前景提取 | `extract_foreground` (online only) | `find_hot` (ref vs 当前 ∂z) | 思路不同但都正确，可统一为 API |
| 静止保留 | `STILL_PERSON_RETENTION_PLAN` draft + HR-RET-V2 fused | 无 | A 单边 |
| 时序确认 | 3/5 帧 vote + age≥3 | age≥3 (track age) | 不同模型 |
| 跟踪 | `Tracker`（EMA, gate .75, lost 8） | overlay `associate`（IOU/gate 1.0, No EMA） | **两个跟踪器** |
| Fall | `fall_assess` (pose_history) | 无 | A 单边 |
| 分类器 | `classify_human` (硬门/证据) | `rf_person` (RF 概率) | **两个决策** |

## 0.3 当前基线数字（任务 STEP 0 · 保存真实值）

- `347a5bf` 整体 baseline： 距离感知 zRange 喂 **351** （原 1807) / cand **75→108**; C1 空场 **0 误报** (8/8 硬门/特征）; 暂留 **+1067/18** (hem 0 误吞）; 8 会话/18 帧/146 簇零字段漂移 （距离感知关闭对照 ego_dump); swapped-swap_log **点级相等** （点级 swap = ego 唯一红染者）; human_pipe_lib **35/35** + detect_overlay **38/38**; long 2056.2s/轻薄 279 帧 0 ERR; human_track **5/5**, human_track 共 47 PASS。
- 模型： 100 树 RF person/noperson。新 RF69 fold-mean **9.80** / 旧 RF-51 **16.05** (4-fold CV)。RF 侧已 12/12 Python↔JS 推理对齐 （见 HEAD commit msg)。
- 时间基： replay tick≈50ms；另库 §性能层 PC 离线 P50/P95 后面测。

## 0.4 测试入口

- 路线 A: `node human_pipe_lib.test.js` (35 测试） + `node detect_overlay.test.js` (38+)
- 路线 B: `node rf_person.test.js` + `node human_track_static.test.js`
- 服务器/工具： `node human_replay_lib.test.js` + `node panel.test.js` + `node registration.test.js` + `node session_selection.test.js`
- Python 侧： `python3 -B -W error -m unittest discover -s pc_apps/human_replay -p "*_test.py"` （本仓还没到 board 跑）
- **注意**: `human_detect_lib.test.js` 在 Windows Node v24.14 hangs（隔离 harness 问题，勿用 `*.test.js` 通配）— 记忆 [[human-detect-lib-test-hang]]

## 0.5 唯一生产 writer

- 本轮唯一写者 = 本轮 Codex。生产核心源 SHA 快照已存 `02_source_sha/prod_sha256.json`（19 文件）。
- 若后有 OpenCode 修复补丁：必须先经本人审阅再落盘（CLAUDE.md 现行授权允许 dispatch），不写生产核心。

## 0.6 数据基线（sessions）

27 个本地 cap_*（见 `01_data_audit/sessions_inventory.json`）。可用 GT 真实情况：
- `human_annotations`: **0/27** (meta.json 有该字段但均为 None，C1.5 坐标不可用证全库）
- `ai_labels.json`: 11/27 （全部 HR09 10-09 站立采集， `labelled_by=auto_person_label.py+empty-template-bgdiff`, `confidence=auto`, 仅 stand/none, 坐标级） — **不是人工 GT**，只作弱标签
- 命名（mojibake）： 标准字段（C1 动态 x4, 10-08）、空场景模板（10-09 113611)、身高加权 9 站距（10-09 114641..122700, 9 段）、女孩 3 站距 (121622..121723)、男 3 站距 (122616..122700)

## 0.7 不可绕开的约束

- `wgq_seg_capped=False` 的 C1 静态域 Wilson 0.994→段级 0.61 — 域内"泄漏已排除"不可证
- C1.5 动态 29/83 覆盖 ≠ 召回率； `n_pts≥500` 硬门使 154007 动态 confirmed-recall → **0**，必保留在统一核心作为诊断模式但默认关闭
- 距离自适应聚类 spike 已证失败（拆分 + 耗时）
- 真人 coords 的 x=0.55/1.9/3.4 三标注员互斥 → 本轮**不重建坐标级 GT**，只做合理 grouping
