# 实际命令与日志

所有*.run.json含命令/cwd/runtime/exit/源码和日志SHA，stdout/stderr同名。首次失败保留。报告/追加/manifest后产生的命令元数据见对应run文件。

| 记录 | 命令 | exit | runtime s |
|---|---|---:|---:|
| baseline | `python -B -W error -X utf8 docs/human_capture/evidence/2026-10-09_hrskeleton_offline_r1/record.py baseline` | 0 | 57.042 |
| binding | `node --max-old-space-size=8192 docs/human_capture/evidence/2026-10-09_hrskeleton_offline_r1/bind_inputs.js prepare` | 1 | 2.620 |
| binding_r2 | `node --max-old-space-size=8192 docs/human_capture/evidence/2026-10-09_hrskeleton_offline_r1/bind_inputs.js prepare` | 1 | 11.553 |
| binding_r3 | `node --max-old-space-size=8192 docs/human_capture/evidence/2026-10-09_hrskeleton_offline_r1/bind_inputs.js prepare` | 0 | 10.623 |
| binding_tests | `node --max-old-space-size=8192 docs/human_capture/evidence/2026-10-09_hrskeleton_offline_r1/binding_tests.js` | 1 | 7.200 |
| binding_tests_final | `node --max-old-space-size=8192 docs/human_capture/evidence/2026-10-09_hrskeleton_offline_r1/binding_tests.js _final` | 0 | 7.244 |
| binding_tests_r2 | `node --max-old-space-size=8192 docs/human_capture/evidence/2026-10-09_hrskeleton_offline_r1/binding_tests.js _r2` | 0 | 7.257 |
| corpus_pass1 | `python -B -W error -X utf8 docs/human_capture/evidence/2026-10-09_hrskeleton_offline_r1/run_offline.py run --out pass1` | 0 | 2.151 |
| corpus_pass2 | `python -B -W error -X utf8 docs/human_capture/evidence/2026-10-09_hrskeleton_offline_r1/run_offline.py run --out pass2` | 0 | 2.441 |
| corpus_pass3 | `python -B -W error -X utf8 docs/human_capture/evidence/2026-10-09_hrskeleton_offline_r1/run_offline.py run --out pass3` | 0 | 1.412 |
| corpus_pass4 | `python -B -W error -X utf8 docs/human_capture/evidence/2026-10-09_hrskeleton_offline_r1/run_offline.py run --out pass4` | 0 | 1.396 |
| corpus_pass5 | `python -B -W error -X utf8 docs/human_capture/evidence/2026-10-09_hrskeleton_offline_r1/run_offline.py run --out pass5` | 0 | 1.487 |
| corpus_pass6 | `python -B -W error -X utf8 docs/human_capture/evidence/2026-10-09_hrskeleton_offline_r1/run_offline.py run --out pass6` | 0 | 1.557 |
| freeze | `python -B -W error -X utf8 docs/human_capture/evidence/2026-10-09_hrskeleton_offline_r1/run_offline.py freeze` | 0 | 0.297 |
| freeze_final | `python -B -W error -X utf8 docs/human_capture/evidence/2026-10-09_hrskeleton_offline_r1/run_offline.py freeze` | 0 | 0.204 |
| freeze_r2 | `python -B -W error -X utf8 docs/human_capture/evidence/2026-10-09_hrskeleton_offline_r1/run_offline.py freeze` | 0 | 0.207 |
| independent_audit | `python -B -W error -X utf8 docs/human_capture/evidence/2026-10-09_hrskeleton_offline_r1/independent_audit.py` | 0 | 17.595 |
| independent_final | `python -B -W error -X utf8 docs/human_capture/evidence/2026-10-09_hrskeleton_offline_r1/independent_audit.py` | 0 | 13.466 |
| integrity_check | `python -B -W error -X utf8 docs/human_capture/evidence/2026-10-09_hrskeleton_offline_r1/record.py integrity integrity_final.json` | 0 | 56.260 |
| materials | `python -B -W error -X utf8 docs/human_capture/evidence/2026-10-09_hrskeleton_offline_r1/closeout.py materials` | 0 | 1.632 |
| pipe_regression | `node pc_apps/human_replay/human_pipe_lib.test.js` | 0 | 0.089 |
| registration_regression | `node pc_apps/human_replay/registration.test.js` | 0 | 1.212 |
| replay_regression | `node pc_apps/human_replay/human_replay_lib.test.js` | 0 | 0.248 |
| review_contract_tests | `node docs/human_capture/evidence/2026-10-09_hrskeleton_offline_r1/review_tests.js` | 0 | 0.054 |
| synthetic_export | `python -B -W error -X utf8 docs/human_capture/evidence/2026-10-09_hrskeleton_offline_r1/test_skeleton.py --dump` | 0 | 0.214 |
| synthetic_tests | `python -B -W error -X utf8 docs/human_capture/evidence/2026-10-09_hrskeleton_offline_r1/test_skeleton.py -v` | 0 | 0.409 |
