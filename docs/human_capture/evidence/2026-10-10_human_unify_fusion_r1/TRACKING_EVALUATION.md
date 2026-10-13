# TRACKING_EVALUATION — F2 融合跟踪器行为评估 (统计, 非 GT 身份)

2026-10-10。评估口径: 只做**「fusion 跟踪器是否按工单 §4 规则运行」**的行为事实, GT 身份 — 未评估。

## 1. Fusion 跟踪器关键规则实现核对

| 工单规则 | 实现位置 | 验证 |
|---|---|---|
| 同一物体 A/B 重复框合并, 不重复起 Track | `engine.js:_fusion_organize` — `a_*/b_*` 候选按质心门 ≤0.75m 合并, A/B 任一被并入时标记 `_merged_into`, 后续不再独立 walk 一条 track | test_fusion_specific (16 PASS); _fusion_organize 测试结果: S1-empty 的 v3 输出里 furniture 源 `A+B` merged, 均成 track FUS_t0_1/2 (2 条, 非 10+); S9 two-person 交叉期同一人保持「单 track」, 交叉后重捕才产生新代际 (`FUS_t0_2`→`FUS_t0_3`) |
| 权威 Track ID 一套 | `FusionTracker` 独立分配 `FUS_t{segment}_{id}`, 不与 PIPE.Tracker 共用 id 空间 | report.fusion_track_ids 验证 (PASS); `FUS_t0_4` 与 `4` 不冲突 |
| 融合 track 不自续命, 只由 A/B 独立命中刷新 | `fusion.js:FusionTracker.tick` — `best.lost = 0` 只在本帧被关联时置 0; lost>track_lost_max 后置 active=false | test_fusion_specific 项「lost=1 仍 active / lost>max → active=false」PASS; S8 still-retention 实测 ever=2 轨 |
| 静止保留 bank 独立证据 | `_tick_fusion` 仅当 A 候选 `track_id===t.id && foreground_source===FG && joint===CONFIRMED_HUMAN` 才刷锚点; retained/merged 不刷 | 代码同 _tick_pipechain 的守卫, 延续 U3 语义 |
| UNKNOWN 输出 | `_fusion_organize`: A-only rf<0.35 → NON_HUMAN; 合并态中 A/B 冲突期确实可浮 UNKNOWN | 代码按阈值分层不强制 PERSON; `CLS_DECISION.UNKNOWN` 保留可输出位置 |
| 会话代际隔离 | `UnifiedEngine.begin_session` → `this.fusion_ctx.tracker=new FM.FusionTracker(fcw)` | test_fusion_specific 项「重 begin generation 递增 / 旧 generation tick 拒绝」PASS |
| 帧回退/重复帧 | 与 BASE/U 共用 `_seen_frames/_last_frame_index` 守卫 | test_fusion_specific 该两项 PASS |

## 2. 会话逐会话行为统计 (FUSION, runs_fusion_v3)

| sid | ever_tracks | 解读 |
|---|---|---|
| S1 empty-with-furniture (304f) | 2 | 家具被分类器检人 (同 BASE_B ever=2), 融合未劣化, 同物体合并为 1 轨 (非 10 轨) |
| S3 walk-x-near (258f) | 6 | 主要人旋转+多家具 → ever=6 (行走分段+家具干扰) |
| S3 walk-y-far (464f) | 10 | 远距往返两轮 →人分裂 → ever=10 |
| S4 walk-stop-walk (239f) | 6 | 停-走分段 |
| S5 turn-in-place (202f) | 3 | 原地转身 → 主要是 1 主 track + 1-2 家具 |
| S6 occlusion (238f) | 4 | 遮挡期帧丢失, lost 30 帧内重捕, ever=4 (遮挡重捕 1 次 + 家具) |
| S7 far-5m (251f) | 6 | 远场点数少 → 边界跟踪挑战 |
| S8 still-retention-long (523f) | 2 | 静止人 → ever=2 (>90% 帧 confirmed), U3=2 → 与 BASE_B ever=3 持平 |
| S9 two-person-cross (126f) | 6 | 两人 split 交叉重捕, ever=6 |

training_fall_events: 全部 0 帧 (fall_assess 有 pose_history 但未触发, 9 会话皆非 fall 场景, 正确行为)。

## 3. 与工单 §4 期望的差距

1. **静止保留不能凭空复活遮挡人**: 被遮挡期间 lost 递增, 重捕后 track_segment 递进, ever 增加 — 在 S6 occlusion/S9 cross 上如实看见。
2. **S1 空场分类器依然判家具为人**: FUSION 不解决分类准确性, 只保证「同一物体不重复」。该项由 F3+GT 决定。
3. **track 寿命**: FUSION 用 `track_lost_max=30` (=3s@10Hz), 与生产 BASE_B 的 15 (=1.5s) 不同; 影响遮挡恢复长度。该**融合默认值可在 fusion_cfg 里调**, 目前取保守值。
4. **跟踪确认**: track_still_confirm_votes=3/window=5/min_age=3, 与 BASE_A/U3 同。

## 4. 证据

- `runs_fusion_v3/<sid>/<sid>__FUSION.json` 9 会话 SHA 守卫输出 (每会话 frame 级 diag._tracks 含 `source_a_hit/source_b_hit/last_seen/track_segment`)
- `pc_apps/human_core/test_fusion_specific.js` 16 项 PASS 输出 (见 REGRESSION_REPORT.md)
- `pc_apps/human_core/summarize_fusion_runs.js` 重生成 `FUSION_ABLATION_REPORT.md`
