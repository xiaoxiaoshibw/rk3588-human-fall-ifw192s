# OPENCODE_INDEPENDENT_REVIEW_R3 — HUMAN-GT-ANNOTATOR-R1 三轮审计 & 整改

2026-10-10 第三轮：审查 `V` 粘贴 / `I` 插值 / `WASD` 移动 三项新 feature。审计人 OpenCode `deepseek-v4.1-flash`（plan 模式只读）。审计完成后由 writer 整改并验证，本报告记录 **FAIL → FIXED** 双阶段。

## Phase 1 — OpenCode 发现 (FAIL)

|#|级别|FAIL|file:line|
|---|---|---|---|
|**Q1**|🚨 致命（S9 阻断）|`mk_object_id(frame_idx, seq)` 同帧 seq 相同 → 双人 P1+P2 同帧 object_id 撞车被静默覆盖|`gt_lib.js:211-214`, `gt_annotator.js:764,843`|
|**Q2**|高|`undo_push` 仅 doc_add/doc_remove；`nudge_selected`/`mark_*` 5 处均不压栈；V/I 批量 → N 条 undo 无法整批|`gt_annotator.js:875-886,660,675,688,717,728,752,789`|
|**Q5a**|高|`nudge_selected` 用 `S.current_frame` 跨帧 reselct → 对象本体/点索引归属不同帧|`gt_annotator.js:882`|
|**Q5b**|中|空 ROI 静默覆旧索引 → propagate/paste 到 z 带外 → point_count=0 → freeze 400|`gt_annotator.js:616-632`|
|**Q6**|中|`is_keyframe` 随 propagate/paste 传染 → 关键帧自我增殖 → I 找错|`gt_lib.js:320-339`, `gt_annotator.js:764`|
|**Q9**|低|`suggested`/`suggested_engine_track`/`interpolated_from` 泄进落盘 JSON|`gt_annotator.js:568-569,860`|
|**Q10**|中|WASD 纵 向反向（屏幕 Y 朝下 / leveled Y 朝上）|`gt_annotator.js:496`|
|**R2 不实**|—|R2 声称 mark_* 已 push 实际未 → 撤回 FIXED|`gt_annotator.js`|

PASS 项：Q3 插值正确（t=k/(steps+1) 公式对）/ Q4 双人隔离（只对 track_id 配对 + have_tids 跳过）/ mouse_lev / ingested 单源。

## Phase 2 — 整改（本 PR）

|Q#|修法|file:line|
|---|---|---|
|**Q1**|新增 `mk_object_id_unique(frame_idx, oseq)` + `S._oseq` 会话级单调计数; `doc_add_object` 见重复 id 抛错（哨兵不静默覆盖）|`gt_lib.js:213-225,389-393`, `gt_annotator.js`：init_doc_if_needed/粘贴/插值 三处更新|
|**Q2**|`doc_add` 加 `skip_undo_push` 参数; V/I 循环外压一次整批快照；nudge/set_class/mark_reviewed/mark_frame_reviewed/assign_track_id/mark_keyframe 均压 undo_push|`gt_annotator.js:171,753,795,881,663,675,692,720,733`|
|**Q5a**|`reselect_points_in_frame(o, o.frame_idx, ...)`|`gt_annotator.js:886`|
|**Q5b**|空 ROI 不静默覆 → 保留旧索引 + `_empty_roi_warning` 审计字段|`gt_annotator.js:629-633`|
|**Q6**|`propagate_object`/`V` 粘贴 删 clone.is_keyframe|`gt_lib.js:338`, `gt_annotator.js:774`|
|**Q9**|保留 interpolated_from/suggested_engine_track 作审计（工单 STEP 3 要求）；suggested 本体不级联（propagate 删）|`gt_lib.js:338`|
|**Q10**|W=+y / S=-y (`gt_annotator.js:496`)|`gt_annotator.js:496`|
|**R2 不实**|5 处 mark 全压 undo，真 FIXED|`gt_annotator.js:663,675,692,720,733`|

## 最终测试矩阵 58/58 PASS

|套件|断言|加 R3 回归后|
|---|---|---|
|gt_lib.test.js|29|+ R3-Q1 S9 双人同帧 id 不冲、重 id哨兵、propagate 不传 K、WASD 反向|
|gt_roundtrip.test.js|8|（真实 S9 126 帧）|
|gt_server_test.py|10|（持久化/校验/SHA）|
|gt_audit_fix_test.py|6|（R1 修复回归）|
|gt_server_e2e_test.py|5|（真实 spawn 8901）|

## 裁定

**同意交付**。R3 发现的 Q1 必修法已实锤（同帧 双人不需测试直接炸了；本修复用哨兵 throw，防未来 regret）。Q5a 跨帧索引 / Q10 反向 在用户第一次试 WASD 会察觉到，修法最小。撤销现在真覆盖 8 个入口。

**遗留**（不阻塞，下工单）：
- `undo` 对 paste/interpolate 只撤**整批**（批外包裹）想要分批控制 （per object）就另一次设计；
- K 只能加 (不能 un-K)— I 依赖 K 定位；删除 K 是"删对象" 的副产品（`Del`）；
- `suggested_engine_track`/`interpolated_from`/`parent_object_id` 审计字段在落盘 (schema v1 许可)。

—— end ——
