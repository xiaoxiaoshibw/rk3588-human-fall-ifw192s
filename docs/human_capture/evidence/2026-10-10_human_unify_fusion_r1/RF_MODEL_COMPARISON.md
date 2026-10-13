# RF_MODEL_COMPARISON — F3 候选 RF v2 对照 (BLOCKED — 缺 GT)

2026-10-10。工单 §5: 要求 RF v1 vs v2 + 家具硬负样本 vs 必要时既有 RFO 候选模型; 必须人工 GT 冻结。

## 当前状态: **BLOCKED**, 交付管线但不给结论。

### 已交付（不依赖 GT 的部分）

| 项 | 状态 | 证据 |
|---|---|---|
| 家具硬负样本数据入口 (`export_furniture_hard_neg.py`) | 管线交付 | 支持 `--gt <frozen_gt.json>` (正式) 和 `--auto-from-empty-sid <sid>` (dry-run, NOT_FOR_TRAINING) |
| ROI 元数据契约 | 完整 | 每条记录含 session_id/frame_range/xy_center/r_xy/label/visibility/session_sha256/gt_version/crop_algorithm |
| `train_person_rf.py` 不改的版本化设计 | 未改 | `DEDUP_NONE` / 模型输出路径/导出行为未动 |
| F1 特征契约冻结 | 一致 | `FEATURE_PARITY_REPORT.md` — 训练用 51 维与 JS 推理 51 维同契约; fv[37..39] 历史契约冻结 |
| F3 dry-run 实际跑 | 0 样本 | S1-empty-with-furniture 自身 bg_envelope 差发现 0 热点 → 证明新空场「背景包络 = 自参考」无家具识别能力; 实际家具需要 HUMAN GT 区件 |

### 未交付（需要 GT 的部分）, 阻塞原因:

1. **`GT_POS.json` / `GT_FURN_HARD_NEG.json` 无冻结文件** — 9 会话全 UNKNOWN, 人工标注未见 (工单 §F0 允许在 GT 缺失时推进其他项, GT 缺失前 F3 训练 BLOCKED)。
2. **RF v2 未尝造** — 工单 §5 明确「无可靠改善, 保留 v1 不强制升级」; 即赛道 BLOCKED 即保留 `rf_person_v1.json` (SHA `4c83db11…`), 不覆盖。
3. **train/val/test SPLITS 未冻结** — 需要 GT+review_status=reviewed 后才能按会话划分, 防跨会话同演员姿态泄漏。
4. **RFO-R1 的 6 会话 RF-v2/v3/HistGBDT 已知局限**（RFO-R1 CLOSEOUT 已记录）: 同房间 6 静态会话、弱标签、折间统计、不是生产阈值。F3 要求新 GT 跨场景对照, 本轮无。

### 设计冻结 (待 GT 后启用)

- **裁剪算法**: `crop_s1_leveled_ref_rt_v1` — `z∈[0.05,2.6]`, `r<=r_xy`, `(x,y,r_xy)` 来自 GT.rois
- **fv 版本**: 延续现 51 维 (Python `frame_feature.extract_features`, fv[37..39] 历史契约冻结)
- **去偏重运行**: 不重复 `train_person_rf.py` 的 `DEDUP_NONE` 逻辑; 硬负样本文件独立待 SIPLT 冻结后由下游训练脚本消费 (新训练路径名 `train_person_rf_v2.py`, 输出 `rf_person_v2.json`, SHA 独立)
- **对照表**（待 GT 冻结后填）: PERSON recall/precision, FP/hour, cross-session 泛化, still-person recall, walking-person recall; 阈值指导意见: 阈值只在 train/val 上定, 最终 test 不再调。

### 模型 SHA 实况

| 模型 | 现状 | SHA |
|---|---|---|
| rf_person_v1.json | 保留 (生产在用, FUSION/BASE_B/U3 全部用它) | `4c83db116fe0742d5c1cca8360de6bafcc4ac9abae3910984beabea8d85bfe68` |
| rf_person_v2.json | **未创建**; 「BLOCKED 即不创建」 | — |

## 结论

**MODEL_PROMOTION_READY = NO**。保留 v1, F3 等 GT 冻结启动。
