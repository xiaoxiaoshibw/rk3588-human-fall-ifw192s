# HUMAN-GT-ANNOTATOR-R3 独立审计 prompt (周期 3)

2026-10-10 第三轮：审查 R1+R2 之后又加的两块新 feature：

## 新加代码

|功能|位置|
|---|---|
|`V` 粘贴上一帧全部对象到本帧|`gt_annotator.js::paste_from_prev_frame`|
|`I` 两 K 帧间按 track_id 线性插 ROI|`gt_annotator.js::interpolate_between_keyframes` 和 `gt_lib.js::interpolate_shapes` 和 `gt_lib.js::shape_of_object`|
|`WASD` 移当前选中框|`gt_annotator.js::nudge_selected` 和 `gt_lib.js::translate_shape`|
|删除改 `Del` (`D` 让给移动)|`gt_annotator.js::on_keydown`|

## 审计问题

1. **数据一致性**：`translate_shape`/`paste_from_prev_frame`/`interpolate_between_keyframes` 是否同步更新 `S.doc.objects` 和 `S.objects_by_frame`？与 `doc_render_map` 单数据源约定的兼容性？找「一边改了另一边没改，审核/保存失败」的 case。
2. **撤销/重做**：新 3 个动作 (V/I/WASD) 之前是否都 `undo_push`？没压栈的动作用 `Ctrl+Z` 会发生什么？
3. **插值正确性**：`interpolate_shapes` 用 `t = k/(steps+1)`，steps 从 1..gap 而生成的 out 长度 = steps。`interpolate_between_keyframes` 用 `out[gap_pos-1]` 会不会数组越界或错拿？多帧 gap 时是不是 k 应该用 0..gap-1？
4. **双人交叉安全**：`S9` 的 P1/P2 用 I 时，会不会因为**中间帧已有 P2** 就把 P1 错插到 P2 track 上？auditor 查到 track_id 匹配 (`p.src.track_id === sa.track_id`)是不是只对 keyframe 校验，还是整段 interp 都对？
5. **`reselect_points_in_frame` 用途**：paste/interpolate 都会**重选点**——`raw_point_indices` 会**覆盖**旧 encoded。在有一些 ROI 新建（粘贴）且旧的 compact 指上级索引还指着旧帧点时，会不会造成 cross-frame 索引错乱？（特别：粘贴时 clone.object_id 改 frame_idx，同 ID 出现 doc）
6. **`is_keyframe` 的语义分裂**：mark_keyframe 把本帧全部对象 is_keyframe=true; interpolate 只 doc 里 objects 带 is_keyframe原样保留，而 frames_index 跨会话存不存在？ingest_draft 后"哪些帧是关键帧"能不能从 S.doc.objects 算出来？
7. **HUD 键位 D→Del**：`KeyD` 原来删除 role 没暴露，改成 `Delete` key — 用户原来记忆 D=删 会懵，文档要同步（USER_GUIDE.md 说 D 删）
8. **测试**：新 5 个 interpolate_* 单测覆盖了 src/dst/t 的数学正确性；但没测：
   - "粘贴上一帧 + 已存在同 track_id 跳过" 的 pair 逻辑
   - undo 对粘贴/插值 的完整往返
   - interpolate 在「缺关键帧边上」拒绝路径
   - 双人交叉下 P2 track 不被错插
9. **note display / gt_annotator** 字段泄漏（Q5 类似的新错）：suggested_engine_track、interpolated_from、is_keyframe 这些在 doc.session 里落了什么格式？
10. **其他就有可能漏的真实 bug** （如 mousemove 时 mouse_lev 不存在的 undefined访问；pan_drag 状态污染粘贴）

## 预期产出

独立 markdown 审计 → `OPENCODE_INDEPENDENT_REVIEW_R3.md`；每项 fail 出：
- file:line
- 具体失败案例（最好可复现测代码)
- 建议修法

跑全套测试：gt_lib.test.js (应当 25 PASS)；gt_roundtrip / gt_server_test / gt_audit_fix / gt_server_e2e 确认 R3 没破原有 49 前端。
