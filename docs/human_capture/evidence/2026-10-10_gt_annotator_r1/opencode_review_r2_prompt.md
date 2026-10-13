# HUMAN-GT-ANNOTATOR-R2 复核 prompt

2026-10-10 二轮。基线在 R1 审计 7 项 FAIL 上已修：

| Q# | 修复 | 测试 |
|---|---|---|
| Q4 SHA 保存 | `_save_draft` 与守卫同用 `json.dumps(sort_keys=True, separators=(",",":"))`；`test_second_save_does_not_409` 通过 | gt_audit_fix_test |
| Q2 reviewed 链 | `_freeze` 现在拒含 unreviewed 对象的 doc（n_unreviewed>0 → 400）；`G` 键单对象 reviewed、`H` 键整帧；`test_freeze_rejects_unreviewed_objects` 通过 | gt_audit_fix_test |
| Q3 gt_suggest 索引 | 新增 `raw_to_compact_frame_indices(point_indices, leaf_of_raw)` 投影；`test_gt_suggest_index_translation`（含 NaN/0 帧）通过 | gt_audit_fix_test |
| Q5 session_sha256.points | `_get_session` 现分别返回 meta_sha + points_sha；客户端 init_doc_if_needed 用 points_sha 给 doc.session_sha256.points | gt_audit_fix_test |
| Q6 冻结原子 + 顺序 | GT_V*.json 也原子写；GT 先 manifest 后 | 用代码审计证 |
| Q7 var best / mouse_lev / doc_snapshot 深拷 / .open().read | 4 处小修 | 单元测试 |

复核任务：
1. 重新读 R1 FAIL 的项目，验证修复真实代码生效（不要读 FINAL/R1 文档内的"已修"声称；拿代码 + 实跑结果）。
2. 审有没有修复中引入新缺陷（特别是 `mark_reviewed`/`mark_frame_reviewed`/`toggle_play` 的副作用；这可能是我自作主张加的）。
3. 跑全部测试（gt_lib/gt_roundtrip/gt_server_test/gt_audit_fix_test=6 + 先前 gt_server_e2e_test=5 合计 49 项），应该全 PASS。如果 gt_server_e2e 5 项有 409 提示，复审 expected_sha 是否被引入副作用。
4. 报告 OPENCODE_INDEPENDENT_REVIEW_R2.md （留旧 R1 不覆盖）。
