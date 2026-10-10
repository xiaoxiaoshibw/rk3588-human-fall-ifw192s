# HUMAN-UNIFY-R1 · 01 ARCHITECTURE PLAN

目标：把 A/B 抽成一个**可观测、可测试、可替换**的离线统一核心，不替换生产代码，不破坏现有页面。
实现哲学（ponytail）：**薄适配厚复用** — 统一引擎只定义 FrameContext / Candidate / Track / Diagnostics 接口 + 层间调度，把计算委派给现 `human_pipe_lib.js` / `rf_person.js` / `frame_feature.py`。

## 1 · 模块划分（新代码全部在 `pc_apps/human_core/`，完全隔离，不 import 生产路径）

```
pc_apps/human_core/    (本轮新增, 完全隔离, 不 import 生产路径)
├── schema.js           # FrameContext / Candidate / Track / Diagnostics + GT_LEVEL
├── leveling.js         # 传感系→leveled 变换 (R/T 外注入)
├── data_loader.js      # 28B 点流切帧 (load_session 整块 / iter_frames_lazy)
├── engine.js           # **聚合实现** — UnifiedEngine 主类
│                       #    内部复用生产 human_pipe_lib.js + rf_person.js (require, 不重写)
│                       #    BASE_B 分支的 5cm 网格聚类 + REF envelope 是**内嵌实现**
│                       #    (复制 detect_overlay.js find_hot/find_clusters 语义的等价重写 — 不是 require)
├── runner.js           # CLI: --session --modes --outdir; 写 json + manifest (含 SHA)
└── test_*.js × 6       # schema/data_loader/engine_smoke/replay_contract/edge_cases/model_compat/perf

测试运行： node --max-old-space-size=2048 pc_apps/human_core/run_all_tests.js
```

**审计说明**: 上层规划原本列 ~10 个模块（background/candidates/clustering/retention/tracking 等）, 实际 ponytail 简化为 7 个文件 （聚合到 engine.js 单类 + 4 个辅助模块）, 此节与 01 一致性已更正。BASE_B 的 5cm 网格聚类为内嵌实现 — 不是复用 detect_overlay.js （未导出 find_hot/find_clusters), 但语义与 detect_overlay 完全等价 （同 BG_CELL=0.05, 同 z∈(0.1,2.3), 同 bg+0.25, 同 30 点门， 同 4 大簇 cap, 同 1.0m gate)。**生产 detect_overlay.js 完全未被修改**。

## 2 · 公共抽象（schema.js）

**FrameContext**: `{session_id, frame_index, timestamp, xyzi: Float32Array(x,y,z,i), leveling: {R,T}, config, frame_id}` — `frame_id` 是 `(session_id, frame_index, content_hash)` 组合，回放防重。

**Candidate**: `{candidate_id, point_indices: Uint32Array, bbox, centroid, point_count, foreground_source: "fg"|"retained"|"merged", geo_features, gen_reason: "cluster"|"self_retained"|..., rejection_reasons: [...], scores: {rf51:?, rf69:?, geometry:?, none:null}, classifier_decision}`

**Track**: `{track_id, associated_candidate_ids: [...], status: "active"|"lost"|"closed"|"confirmed"|"candidate", confidence, missed_frames, first_frame_idx, last_frame_idx, age_frames, votes: {confirmed_frames, last_k}}`

**Diagnostics**: 每层 `{in_points, out_points, in_candidates, out_candidates, reject_reasons: {reason -> n}, elapsed_ms, dropped_to_layer}`，帧级 + 会话级聚合。

**GTAttestation**: `{level: "HUMAN_VERIFIED"|"HUMAN_UNVERIFIED"|"PSEUDO_LABEL"|"UNKNOWN", source, person, frames}` — 评价逻辑用它决定是否可算 P/R/F1。

## 3 · 双来源候选（统一 Candidate Generation）

```
raw ─→ foreground_path (从 background 输出)
    └→ retained_path  (retention: 从 trails的年龄过、未确认、但曾 CONFIRMED 的 track "热像素")
    └→ merge & dedupe:
        - 同一 XY cell (0.15m) 多来源同一簇 → 合并, foreground_source="merged"
        - 一个真人不得在 merge 后被两个来源同时建 track
        - retention 带 timeout (180s 无重进) + 失效 (BG 重新强占) + 重确认 (新帧热点)
```

## 4 · 分类器适配（classifiers.js）

| 名称 | 来源 | 特征 | 决策 |
|---|---|---|---|
| geometry_gate | 路线 A `classify_human` + evidence | 管道几何 | HUMAN_CANDIDATE / NON_HUMAN |
| rf51_v1 | `rf_person.js` + 100树 json | 51 | prob |
| rf69_copy | pc_apps/human_ml/rf_subset_pc.json 需重导 | 69 | prob |
| geometry_only | 只 classify_human 硬门 | — | ok/non-ok |
| none | — | — | null |

**硬性不兼容**: 特征维度 ≠ 模型 n_features → 拒绝推理，不允许填零；分类器输出保留 `{raw_score, threshold, decision, model_version, model_sha256_prefix}`。

## 5 · 跟踪（tracking.js 统一状态机）

- 单一 TrackManager （接口与 detect_overlay.associate / human_pipe_lib.Tracker 都兼容）
- 同帧一对一: claimed 集；同帧重复调用: frame_id 守卫 （重入 → no-op 返回上次结果）
- 非单调回放： `replay_contract.js` 定义 `policy`: `monotonic | jump | seek_back | loop | session_switch` → 对应 `tick / rebuild / reset`, 旧帧不 push
- 关联: 距离门 + 位置平滑 (可关） + claimed + age; lost>N → closed

## 6 · 双路线调用接口（dash of consumers）

```js
const core = require('pc_apps/human_core/runner.js');
const session = core.load_session('captures/remote/cap_...');
const engine = core.create_engine({
  background: core.BG.ONLINE_PIPE,
  candidates: core.CAND.FG_PLUS_RETAINED,
  clustering: core.CLUSTER.PIPE_VOXEL,
  classifier: core.CLS.RF51_V1,
  temporal: {confirm_window:5, votes:3, min_age:3},
  tracking: {gate:0.75, lost_max:8, ema_alpha:0.35},
  diagnostics: true,
});
for (const fc of core.frames(session)) engine.tick(fc);  // → Diagnostics[]
const out = engine.report(); // per-frame + per-session
```

路线 A 生产 = `{background: ONLINE_PIPE, classifier: geometry_gate}`；路线 B 生产 = `{background: REF_ENVELOPE, classifier: rf51_v1}` — **同一 engine 可复现两者**。

## 7 · 排除的设计（明确不做）

- 不做坐标级人工 GT 渲染器（C1.5 教训，改用带刻度的渲染器是下一轮）
- 不重训 RF69（模型 artifact 在 `rf_subset_pc.json`，json 导出器非本轮范围）
- 不改 `human_pipe_lib.js` / `detect_overlay.js` / `rf_person.js` 生产源（只 import）
- 不部署/不打包 EXE/不动 UI default；observation layer 走独立 runner 输出 CSV/JSON
- 不接受 0.55 默认阈值的提升或候选硬门放宽
