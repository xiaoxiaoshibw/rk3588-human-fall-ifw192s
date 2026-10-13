# GT_COVERAGE_REPORT — F0/F3 人工 GT 覆盖与标注任务

2026-10-10。数据源：`SESSION_DATASET_MANIFEST.json`（audit_fusion_sessions.py 实跑，exit 0，9 会话契约全过）。

## 1. 当前 GT 真实状态

| 会话 | 活动类型 | GT 状态 | 来源 |
|---|---|---|---|
| 9 × 新会话 (cap_20261010_*) | 见工单 S1–S9 | **UNKNOWN（全部）** | 无 ai_labels.json、无 meta.human_annotations |

- 0 段 HUMAN_VERIFIED，0 段 HUMAN_UNVERIFIED。NEW_CAPTURE_NOTES.md 已明确「仅有 meta/bin 时没有 GT，自动框/脚本标签不能升级 HUMAN_VERIFIED」。
- 因此：**F3 训练、F4 GT 驱动指标（recall/precision/FP/hour/ID switch）当前 NOT_EVALUABLE**；GT_POS/FURN_HARD_NEG/SPLITS 冻结只能在人工标注完成并审阅后进行。
- 不依赖人工 GT 的工作（F1 特征对拍/性能、F2 融合器、F4 功能回归、WebUI）正常推进，不受此阻断。

## 2. 自动前置候选（非 GT，仅标注加速）

`gt_workbench_export.py --auto` 将为每会话生成 `AUTO_CANDIDATES.json`：
- 背景：同场景新空场 S1 (cap_20261010_175227) 在线 5cm 网格 z95 包络（auto_person_label.background_envelope 同法）。
- 方法：leveled 点高于背景 +0.25m、z∈[0.1,2.3] 的热点 → 5cm XY 连通分量 → 簇 ≥30 点 → 输出 xy/半径/点数/z_max。
- 每帧保留全部过阈簇（上限 8，支持双人），**不**套用原 auto_person_label 的单簇+时序跳变门限（那会吞掉遮挡/双人场景）。
- 明确标记 `PSEUDO_LABEL/auto_candidate`，标注器必须逐帧确认或改正，确认前不得进入任何 GT 文件。

## 3. GT 契约（gt_workbench/schema v1）

每帧 ROI：`{cls: PERSON|FURNITURE|BACKGROUND|UNKNOWN, x, y, r_xy, track_id(PERSON), visibility: visible|partial|occluded}`。
每会话：`episodes[{track_id, born_frame, exit_frame|null, still_frames[], moving_frames[]}]`、`uncertain_intervals[{start,end,reason}]`、`annotator`、`review_status: draft|reviewed`、`annotated_at`、`gt_version`、`session_sha256`（锚定 SESSION_DATASET_MANIFEST 的 meta/points SHA，防标错数据版本）。
规则：文件不存在 → 全帧 UNKNOWN；PERSON 必须有 track_id 且同帧内唯一；FURNITURE 建议逐件标注（供 F3 硬负样本 ROI 裁剪）。

## 4. 标注任务（9 会话，最小充分精确口径）

| 优先 | 会话 | 必须标注 | 备注 |
|---|---|---|---|
| P0 | S1-empty-with-furniture | FURNITURE ×每件（≥4 件建议），只需 annotated frames 子集亦可（静态可抽稀 ≥每 20 帧 1 帧） | FURN_HARD_NEG 唯一来源；同时是空场误检测试集 |
| P0 | S8-still-retention-long | PERSON ×1：入场帧、静止区段起止、离场帧；可抽稀（静止区段每 25 帧标 1 帧） | still-recall 分母 |
| P0 | S9-two-person-cross | PERSON ×2 全程逐帧 track_id + 交叉期为双方标 partial | twin/ID-switch 分母；最难，建议对照旁观视频 |
| P1 | S3-walk-x-near | PERSON ×1 逐帧 | moving-recall 近场 |
| P1 | S3-walk-y-far | PERSON ×1 逐帧（往返两轮） | moving-recall 远场 |
| P1 | S4-walk-stop-walk | PERSON ×1 逐帧 + 静止子段起止 | still+moving 混合 |
| P1 | S5-turn-in-place | PERSON ×1 逐帧 | 原地运动 |
| P1 | S6-occlusion | PERSON ×1 逐帧 + 遮挡区段（occluded 帧标 visibility/uncertain） | re-acquire 分母 |
| P1 | S7-far-5m | PERSON ×1 逐帧（阶梯距离段记入 episodes 备注） | 低点数边缘 |

抽稀标注的帧间时段：标注器按「线性插值 + 人工抽检修正」补全还是保守标 uncertain_interval，由标注人选择并记录 method 字段。

## 5. 交付与冻结流程

1. 运行 `python pc_apps/human_ml/gt_workbench_export.py`（本工单产出）生成交付包。
2. 标注人按 §3 契约在逐会话 JSON 上工作（手写或工具），标注来源填 annotator ID。
3. 回收后运行 GT 校验（契约 verifier，F3 开工前实现）：schema + track_id 一致性 + SHA 锚定 + UNKNOWN 语义检查。
4. 校验通过 → 冻结 `GT_POS.json` / `GT_FURN_HARD_NEG.json` / `SPLITS.json`（含 SHA），train/val/test 按整会话划分，禁止跨会话同演员姿态泄漏进不同集合（S1 空场只能进 test 或 val 误检集）。
