# HFUS Integration R1 — sub_d01_verify 报告

> 本文件由主控按 D01 verify 代理完成通知原文固化落盘（代理因沙箱写限制无法自写 REPORT.md）。内容即其最终报告全文。

日期 2026-10-11。只读 `sidequests/human_fusion_lab_next/`、`sidequests/human_fusion_lab/`、`captures/`、原 baseline_final 与 D03_r1；只写 `docs/human_capture/evidence/2026-10-11_hfus_integration_r1/sub_d01_verify/`（脚本 + 落盘证据均在此）。

## 1. 命令 / exit / 落盘去向

| # | 命令 | exit | 落盘 |
|---|---|---:|---|
| 1 | `mkdir …/all_run` 预建空目录（误用） | 0 | 触发 baseline.js `new absent output directory` 抛出；先 rmdir 才进入正式跑 |
| 2 | `node sidequests/human_fusion_lab_next/eval/baseline.js …/all_run --all > all_run_stdout.log` | 首 0（误）、重 0 | 被 429 中断止于 `cap_20261010_180235 sensor_valid` 100/238 帧（无 SUMMARY） |
| 3 | `rm …/all_run/cap_20261010_180235__BG_A__sensor_valid.jsonl` 删半成品 | 0 | 在自有 OUT_DIR 内 |
| 4 | `node …/resume_run.js > resume_run_stdout.log` | 0 | 补跑 7 runs：`180235 sensor_valid` + `180337/180557/180751 × 2 inputMode` → `resume_run/` |
| 5 | `python -I diff_summaries.py` | 0 | `summary_diff_vs_baseline_final.json` |
| 6 | `python -I aggregate_table.py` | 0 | `nine_session_table.json`；`180235 sensor_valid` resume vs baseline_final 非易变 diff=0 |
| 7 | `python -I reconcile_frames.py` | 0 | `task2_frame_reconcile.json` |
| 8 | 多次 `python -I -c` 读 D03 FLOW json | 0 | 仅 stdout |

坑记录（未静默修正）：① 第 1 次 baseline.js 因 mkdir 触发 existsSync 拒——operator path 误用；② 第 2 次被 429 中断，100 帧半成品显式删除，以 `resume_run.js`（同 `runSession`）独立 out_dir 补跑；③ Windows 默认 GBK 解码大 JSON，必须 `encoding='utf-8'`；④ S9 `eligible=false` 属预期 INVALID_BINDING，不是回归；⑤ baseline.js 的 MANIFEST 仅主运行写盘，resume 单独产 `RESUME_RESULTS.json` 备溯源。

## 2. 九会话 × 两 inputMode strict/legacy 汇总表（BG_A，tp/fn/fp/unmatched_unknown）

| session | activity | mode | gtv | frames | qframes | strict proposal | strict accepted | strict obs_conf | legacy accepted (tp/fp/fn) | legacy confirmed |
|---|---|---|---:|---:|---|---|---|---|---|---|
| 175227 | S1 empty | src/valid | T | 304 | 304 | 0/0/0/600 | 0/0/0/0 | 0/0/0/0 | 0/0/0 | 0/0/0 |
| 175227 | S1 empty | sensor_valid | T | 304 | 304 | 0/0/0/600 | 0/0/0/0 | 0/0/0/0 | 0/0/0 | 0/0/0 |
| 175429 | S3near walk-x | src/valid | T | 258 | 258 | 163/95/0/478 | 163/95/0/114 | 161/97/0/104 | 258/19/0 | 256/9/2 |
| 175429 | S3near walk-x | sensor_valid | T | 258 | 258 | 163/95/0/478 | 163/95/0/114 | 161/97/0/104 | 258/19/0 | 256/9/2 |
| 175553 | S3far walk-y | src/valid | T | 464 | 99 | 38/61/0/310 | 38/61/0/158 | 36/63/0/154 | 99/97/0 | 97/93/2 |
| 175553 | S3far walk-y | sensor_valid | T | 464 | 99 | 38/61/0/310 | 38/61/0/158 | 36/63/0/154 | 99/97/0 | 97/93/2 |
| 175804 | S4 walk-stop-walk | src/valid | T | 239 | 11 | 7/4/0/32 | 7/4/0/13 | 6/5/0/12 | 11/9/0 | 10/8/1 |
| 175804 | S4 | sensor_valid | T | 239 | 11 | 7/4/0/32 | 7/4/0/13 | 6/5/0/12 | 11/9/0 | 10/8/1 |
| 175943 | S5 turn | src/valid | T | 202 | 6 | 6/0/0/6 | 6/0/0/0 | 5/1/0/0 | 6/0/0 | 5/0/1 |
| 175943 | S5 | sensor_valid | T | 202 | 6 | 6/0/0/6 | 6/0/0/0 | 5/1/0/0 | 6/0/0 | 5/0/1 |
| 180235 | S6 sit/stand | src/valid | T | 238 | 71 | 47/24/0/159 | 47/24/0/19 | 45/26/0/17 | 65/1/6 | 61/1/10 |
| 180235 | S6 | sensor_valid | T | 238 | 71 | 47/24/0/159 | 47/24/0/19 | 45/26/0/17 | 65/1/6 | 61/1/10 |
| 180337 | S7 | src/valid | T | 251 | 12 | 11/1/0/22 | 11/1/0/2 | 11/1/0/1 | 12/1/0 | 11/1/1 |
| 180337 | S7 | sensor_valid | T | 251 | 12 | 11/1/0/22 | 11/1/0/2 | 11/1/0/1 | 12/1/0 | 11/1/1 |
| 180557 | S8 | src/valid | T | 523 | 53 | 53/0/0/53 | 53/0/0/0 | 51/2/0/0 | 53/0/0 | 51/0/2 |
| 180557 | S8 | sensor_valid | T | 523 | 53 | 53/0/0/53 | 53/0/0/0 | 51/2/0/0 | 53/0/0 | 51/0/2 |
| **180751** | S9 ineligible | src/valid | **F** | 126 | 0 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | 0/0/0 | 0/0/0 |
| 180751 | S9 | sensor_valid | **F** | 126 | 0 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 | 0/0/0 | 0/0/0 |

legacy accepted 合计（8 有资格会话）tp=504 fp=127 fn=6；legacy confirmed 合计 tp=491 fp=112 fn=19 ——**与统一计划 §2.1 同口径合计行严格一致**。机器可读版：`nine_session_table.json`。

## 3. D01 三复跑 vs baseline_final —— 逐字段 diff 结果

| session/mode | 结论 | 与 baseline_final 非易变 diff 数 |
|---|---|---:|
| 175227 × 2 | MATCH | 0 |
| 175429 × 2 | MATCH | 0（prop=163/95/0/478, obs=161/97/0/104 一致） |
| 180235 × 2 | MATCH | 0（prop=47/24/0/159, obs=45/26/0/17 一致） |

唯一差异：`performance.{p50_ms,p95_ms,p99_ms,peak_heap_mb}`（机器负载相关，非检测/合约字段）。`input_sha256`/`gt_sha256`/`qualified_frames`/`strict`/`legacy`/`component_count`/`coast_observations`/`duplicate_track_ids`/`invalid_candidate_row_count`/`coordinate config`/`limits` **逐字段相等**。落盘：`summary_diff_vs_baseline_final.json`。

## 4. 任务 2 —— 逐帧对账 near / S6

- 公共键 `(sid,frame_index)`：near 258/258 (100%)，S6 238/238 (100%)
- 比较的 keys：`strict/evaluation` 的 `proposal.accepted.observed_confirmed.{tp,fn,fp,unmatched_unknown}`、legacy、候选 id/prob/score/decision/track_id/track_confirmed/source/`raw_indices`（集比较）
- **结论：near 与 S6 上 metric_mismatches=0、cand_mismatches=0、legacy_mismatches=0 → D01 baseline_final ≡ D03-A ledger 逐帧数值一致**（`task2_frame_reconcile.json`）。
- 样本 sanity-check：frame 0 D01 `<score=0.9985302,CONFIRMED_HUMAN,track_id=FUS_t0_1>` ≡ D03 同 id 同值。

## 5. 任务 3 —— f128/f187/f188 A 侧分层 flow 结论

### 5.a 每层数量

| frame | raw | valid | fg | cleanup | retained (added) | cluster a/b 硬门过 | classifier a/b | final `_candidates` | track |
|---|---:|---:|---:|---:|---|---|---|---:|---:|
| f128 | 49133 | 38341 | 670 | 651 | 651 / **added=0** | PA 1/31、PB 1/55 | A 1→0, B 1→0 | 1 (a_128_4) | 3 |
| f187 | 49131 | 38349 | 639 | 622 | 622 / **added=0** | PA 0/31、PB 2/53 | A 0→0, B 2→0 | 0 | 3 |
| f188 | 49129 | 38347 | 675 | 659 | 659 / **added=0** | PA 2/26、PB 0/49 | A 2→0, B 0→0 | 2 (a_188_1, a_188_5) | 3 |

### 5.b 最终候选 coverage / purity / score

| frame | cand | n | gt_overlap | cov | purity | prob | decision | src | track |
|---|---|---:|---:|---:|---:|---:|---|---|---|
| f128 | a_128_4 | 380 | 0 | 0.000 | 0.000 | 0.01165 | NON_HUMAN | A | FUS_t0_3 |
| f187 | — | — | — | — | — | — | — | — | — |
| f188 | a_188_1 | 402 | 0 | 0.000 | 0.000 | 0.01165 | NON_HUMAN | A | FUS_t0_3 |
| f188 | a_188_5 | 63 | 0 | 0.000 | 0.000 | 0.00288 | NON_HUMAN | A | FUS_t0_2 |

### 5.c GT Person 点 fate（`point_flow`）

| frame | n_GT | cleanup 删 | retained 补 | 进 final_fg 所在组件 | 后果 |
|---|---:|---:|---:|---|---|
| f128 | 33 | **15** | 0 | 18 点 → pa12 (18/21) + pb1 (18/21) 均 gate_fail | strict prop FN=1 |
| f187 | 260 | **251 (96.5%)** | 0 | 9 点 → pa17/pa18/pb8/pb25 均 gate_fail | strict prop FN=1，0 顶层候选 |
| f188 | 268 | **252 (94.0%)** | 0 | 16 点 → pa14/pb4/pb12 均 gate_fail | strict prop FN=1，2 顶层候选均家具 |

### 5.d 失败层 / 谁挑出"实际根因"

- f128 根因层=`cleanup` + `cluster 硬门`：cleanup 删 15/33，剩余 18 点小簇未过硬门；顶层唯一候选 a_128_4 (n=380, GT 0 重合) score 0.0117 拒，**非根因、是后果**。
- f187/f188 根因层=`cleanup`：两帧 GT 各 96.5%/94.0% 被 cleanup 删；retention added=0 缺参考；已有零件未过硬门。两候选 a_188_1/a_188_5 与 GT 0 重合。
- f187 额外 sub-根因=PB 硬门：PB 侧 2 个 GT 小件 gate_fail；且即便过门也进不了 `_candidates`（见陈述 (3)）。

### 5.e 对照统一计划 §5.1 三条陈述

| # | 陈述 | 判定 | 证据 |
|---|---|---|---|
| (1) | f128 人体 15 点进大簇 | **REJECT（A 侧）** | A 侧 f128 中那 15 点 `cleanup=False/final_fg=False`，未进任何组件；实际进大簇 pa_component_6 (n=380) 的 gt_overlap=0。陈述仅对 B 侧成立，不能外推到 A 侧 |
| (2) | f187/f188 前分类缺参考删除有直接证据 | **CONFIRM** | 两帧 retained `added=0` 直接证据；cleanup 各删 96.5%/94.0% GT 点；strict proposal FN=1 在两层同时成立 |
| (3) | PB 不成"人"不进入 d._candidates | **CONFIRM** | f187 PB classifier_b in=2 out=0；f128/f188 顶层候选源全 A。扩展：S6 全 ledger 496 顶层候选源 A=470、A+B=1、B=25 且 25 个 B 源全部 CONFIRMED_HUMAN；near A ledger 481 候选源 A=479、B=1、A+B=1 中的 B/A+B 也全 CONFIRMED_HUMAN ⇒ **未成人的 PB 组件从未出现在 `_candidates`**，正是 §3 120 行要求补诊断出口的旧行为 |

## 6. REPRODUCIBLE

**REPRODUCIBLE: yes**

理由：D01 三会话（175227、175429、180235）× 两种 inputMode × BG_A 复跑与 `baseline_final/` 6 组对照，全部非易变字段逐字段相等（仅 `performance.*` 4 字段不同，同机不同 run 系统负载波动）；near 与 S6 的逐帧 jsonl 与 D03-A ledger 在 proposal/accepted/observed_confirmed/legacy/候选成员/分数/decision/track_id 上 **0 mismatch**。三套独立证据（复跑 vs baseline_final、复跑 near 与 S6 vs D03、以及 near/S6 套全 ledger candidate source 一致检查）共同支撑 numeric 可复现。

## 附录：sub_d01_verify/ 文件清单

- `all_run/` 6 会话 × 2 模式（首次 partial，Dead at 180235 sv）
- `resume_run/` 7 runs 补齐
- `nine_session_table.json`、`summary_diff_vs_baseline_final.json`、`task2_frame_reconcile.json`
- 脚本 `resume_run.js / aggregate_table.py / diff_summaries.py / reconcile_frames.py`
- 日志 `all_run_stdout.log / resume_run_stdout.log / aggregate_table.log / diff_summaries.log / reconcile_frames.log`
