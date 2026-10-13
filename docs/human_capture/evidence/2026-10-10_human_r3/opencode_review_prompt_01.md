独立审查 HUMAN-R3-CONTINUOUS 的离线交付。仓库根 D:\Code\ldiar。

# 你的角色
独立审计员。不照抄 Claude/Codex 的自评。独立验证。

# 审查对象（本次 R3 交付）
1. docs/human_capture/evidence/2026-10-10_human_r3/ 全部 (GT_AUDIT.md, PERF_REPORT.md, EVALUATION_REPORT.md)
2. 本 R3 改动的生产源码：pc_apps/human_core/engine.js (_fusion_b_chain indexOf→Map, 7 行新加 1 行换)
3. 本 R3 新增源码：
   - pc_apps/human_core/perf_r3_baseline.js
   - pc_apps/human_core/test_m1_parity.js
   - pc_apps/human_core/test_s1_v3_regression.js
   - pc_apps/human_core/evaluate_v3_s3near.js
   - pc_apps/human_core/evaluate_track_recall.js
   - pc_apps/human_ml/train_person_rf_v3.py
   - pc_apps/human_replay/propagate_s1.py
   - pc_apps/human_replay/fix_s9_f1_p2.py
   - pc_apps/human_replay/reselect_propagated_indices.py
   - pc_apps/human_replay/freeze_all.py (R2 时已存)
4. 产物：
   - gt_store/<sid>/manifest.json 与 GT_V*.json (S1 V3, S9 V2 是当前最新)
   - docs/human_capture/evidence/2026-10-10_human_r3/train_03/rf_person_v3.json
   - docs/human_capture/evidence/2026-10-10_human_r3/perf_baseline_s3far + perf_m1_indexOf_map
   - docs/human_capture/evidence/2026-10-10_human_r3/eval_v3/*.json

# 铁律 (审查必看)
- rf_person_v1.json 不得被覆盖；fv[37..39] 历史排序不许"修正"
- 不 commit / push / deploy；不替换生产主入口
- GT 已冻结版本不得静默修改
- UNKNOWN 不得写成 PASS

# 必查项（独立验证，独立结论）
A. M1 性能优化语义是否等价
A1. 独立读 engine.js:_fusion_b_chain 的 indexOf→Map 替换 (line 375~381)，确认
    pos_by_id.get(pi) 返回与 final_ids.indexOf(pi) **完全相同的 first-match frame_pos**，包括 final_ids 存在重复时行为一致
A2. 跑 node --max-old-space-size=2048 pc_apps/human_core/perf_r3_baseline.js --out <你自己的临时目录> 复测，比较与 evidence/perf_m1_indexOf_map/summary.json 是否一致
A3. 跑 node pc_apps/human_core/run_all_tests.js 与 node pc_apps/human_core/test_fusion_specific.js / test_fusion_gt.js / test_m1_parity.js / test_s1_v3_regression.js；独立核对退出码与断言数

B. GT 完整性与安全
B1. 独立读 gt_store/cap_20261010_175227/manifest.json，验证 V3 SHA 与 GT_V3.json 文件 payload 的 sha256 一致 (按 gt_server._freeze payload 序列化: json.dumps(doc, ensure_ascii=False, indent=1, sort_keys=True))
B2. S1 V3 propagated 对象 (1818个) 的 raw_point_indices 是否在本帧 valid 后索引空间且无越界
B3. S9 V2 36 对象中 obj_f1_p2_propagated 的 source/propagated/track_id 标注是否清楚
B4. 任何人是否在 S1 propagated 上加 track_id / 在做不容许的 class 升级

C. 训练流程诚实性
C1. train_person_rf_v3.py 是否会在训练界 train/val/test split 时报 100%/100%/100% — 检查 stratified_oversample 是否有泄漏 (按会话隔离是关键)
C2. rf_person_v3.json 是否有 n_features=51, trees 数=200，并核对 predict 路径与 rf_person.js 契约兼容
C3. R2 train_02 (v2) 和 R3 train_03 (v3) 的训练样本是否真正做到会话隔离（同一 GT 源 propagated 不能同时出现在 train 和 test）
C4. S1 的 propagated 副本是否应该被允许进训练集（训练集应该只信 human 标的 f=0 6 个样本？）— 这是关键诚实问题

D. 模型选择
D1. R3 EVALUATION_REPORT.md 的 track recall 数字（v1=0.895 / v2=0.341 / v3=0.620）是否能从 evidence/eval_v3/*.json 复核
D2. v3 在 S6 (0.578) 比 v2 (0.761) 还差的解释是否合理
D3. "v1 保留，MODEL_PROMOTION BLOCKED" 结论是否被 track recall 数据正确支持

E. 生产保护
E1. claude 是否动了 rf_person_v1.json / frame_feature.py / rf_person.js 51 维契约
E2. 是否有未授权的 commit / push / deploy / 生产主入口替换
E3. engine.js 改动是否在 _fusion_a_chain、_fusion_organize、Tracker 之外还能引发副作用

# 你的输出要求
- 分级：BLOCKER / MAJOR / MINOR / PASS
- 每个发现给：复现命令 / exit code / SHA / 证据位置
- 最后给独立总裁定：PASS / CONDITIONAL PASS / FAIL / BLOCKED
- 报告写 docs/human_capture/evidence/2026-10-10_human_r3/OPENCODE_INDEPENDENT_REVIEW.md（用 Write 工具直接写）
