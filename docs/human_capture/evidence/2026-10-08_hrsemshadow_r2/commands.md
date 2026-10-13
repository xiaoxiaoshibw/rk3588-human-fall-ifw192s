# R2 实际命令

| 日志 | exit | 实际命令 |
|---|---:|---|
| browser_export_validation.run.json | 0 | `node --max-old-space-size=8192 docs/human_capture/evidence/2026-10-08_hrsemshadow_r2/review_binding.js docs/human_capture/evidence/2026-10-08_hrsemshadow_r2/browser_synthetic_export.json` |
| build_review.run.json | 0 | `node --max-old-space-size=8192 docs/human_capture/evidence/2026-10-08_hrsemshadow_r2/build_review.js` |
| build_review_final.run.json | 0 | `node --max-old-space-size=8192 D:\Code\ldiar\docs\human_capture\evidence\2026-10-08_hrsemshadow_r2/build_review.js` |
| build_review_r2.run.json | 0 | `node --max-old-space-size=8192 D:\Code\ldiar\docs\human_capture\evidence\2026-10-08_hrsemshadow_r2/build_review.js` |
| data.run.json | 1 | `python -B -W error -X utf8 docs/human_capture/evidence/2026-10-08_hrsemshadow_r2/data_audit.py` |
| data_r2.run.json | 0 | `python -B -W error -X utf8 docs/human_capture/evidence/2026-10-08_hrsemshadow_r2/data_audit.py` |
| edge.run.json | 0 | `python -B -W error -X utf8 docs/human_capture/evidence/2026-10-08_hrsemshadow_r2/edge_audit.py` |
| full_recompute.run.json | 0 | `node --max-old-space-size=8192 docs/human_capture/evidence/2026-10-08_hrsemshadow_r2/replay_audit.js` |
| negatives.run.json | 0 | `node --max-old-space-size=8192 docs/human_capture/evidence/2026-10-08_hrsemshadow_r2/negative_audit.js` |
| receipts_final.run.json | 0 | `python -B -W error -X utf8 docs/human_capture/evidence/2026-10-08_hrsemshadow_r2/independent_receipts.py` |
| receipts_independent.run.json | 0 | `python -B -W error -X utf8 docs/human_capture/evidence/2026-10-08_hrsemshadow_r2/independent_receipts.py` |
| regression_pipe.run.json | 0 | `node pc_apps/human_replay/human_pipe_lib.test.js` |
| regression_registration.run.json | 0 | `node docs/human_capture/evidence/2026-10-08_hrsemshadow_r2/registration_check.js` |
| regression_replay.run.json | 0 | `node pc_apps/human_replay/human_replay_lib.test.js` |
| sem12.run.json | 0 | `node --max-old-space-size=8192 docs/human_capture/evidence/2026-10-08_hrsemshadow_r2/sem12.test.js` |
| sem12_final.run.json | 1 | `node --max-old-space-size=8192 docs/human_capture/evidence/2026-10-08_hrsemshadow_r2/sem12.test.js` |
| sem12_final_r2.run.json | 0 | `node --max-old-space-size=8192 docs/human_capture/evidence/2026-10-08_hrsemshadow_r2/sem12.test.js sem12_final_results.json` |
| sem12_release.run.json | 0 | `node --max-old-space-size=8192 docs/human_capture/evidence/2026-10-08_hrsemshadow_r2/sem12.test.js sem12_release_results.json` |
| sem12_verified.run.json | 0 | `node --max-old-space-size=8192 docs/human_capture/evidence/2026-10-08_hrsemshadow_r2/sem12.test.js sem12_verified_results.json` |
| wd02.run.json | 0 | `node docs/human_capture/evidence/2026-10-08_hrsemshadow_r2/wd02_audit.js` |

每个命令对应同名stdout/stderr，输入工具SHA在run.json；失败和有警告记录不覆盖，不计最终成功。浏览器具体操作见browser_ui_status.json及本聊天工具轨迹。完整性命令后续记录为integrity_final.run.json。

收尾实际命令：`python -B -W error -X utf8 docs/human_capture/evidence/2026-10-08_hrsemshadow_r2/record.py integrity`，由record.py run integrity_final记录，exit0。`closeout.py`只在此检查成功后生成05_integrity/manifest并追加上述return收尾。
