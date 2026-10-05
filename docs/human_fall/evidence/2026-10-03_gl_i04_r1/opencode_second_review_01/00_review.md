# GL-I04 R1 independent OpenCode second review

Status: SECOND_REVIEW_SUBMITTED / STOPPED. No production/config/tests/draft/capture/status changes.
This report is the reviewer's own conclusion; author self-labels were provisional.

## 0. Reviewer identity and skill use

- Role/model: independent reviewer, `opencode-go/deepseek-v4.1-flash`, **default DB** (no `OPENCODE_DB`,
  no model/DB/auth/permission/global-config change).
- Interface: opencode CLI interactive session over `D:/Code/ldiar`; the tool layer does not expose a
  session id to this report (the author's Q10 service probe session is recorded separately in
  `27_probe_session.json`, `ses_efdc64657ffeZMecnYddJTdRJ7`).
- Native skill used **before** reviewing: `skill(name=ponytail)` (not an external/rejected skill path).
  Resolved file: `C:\Users\30680\.claude\skills\ponytail\SKILL.md`, SHA256
  `1316a2f3f95741d2300b116fe0c2d81ce4a9568656ed0a62643f54aaf09957f2` (identical bytes to the
  legacy `.codex` path, but loaded through the native skill tool as required). Intensity: full.
- Scope honored: read-only on production; new scripts/outputs only under
  `docs/human_fall/evidence/2026-10-03_gl_i04_r1/opencode_second_review_01/`. No rework, no writer spawn,
  no prototype integration, no acceptance/status doc edits. The author experiment/audit ledgers were
  **not** overwritten (their `open("x")` writers would refuse; independent reimplementations were used).

## 1. Reviewed SHA baseline (BEFORE / AFTER)

- Working tree HEAD/branch at review: `cbd0be1c86a1051a9a5800dfb7263f842896e1e6` / `master` (unchanged).
- Submission manifest `11_submission_manifest.json` SHA256 (BEFORE and AFTER review):
  `acd545f82080ab3a49b931209a76af3f41b94882c6f1063d2d0def65dee8c06d` — equals the
  `25_manifest_addendum.json` `manifest_sha256`, confirming the manifest itself did not drift.
- File-hash verification (`verify_hashes.py`): **111/111 declared files match**. The only superseded SHA
  is the explicitly recorded log-only addendum: `24_submission_run.txt` old
  `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` (empty) → actual
  `95da1ce6f9450b26ced57865053373762f15a34855f23faddb8c334b320eb12e`. This is the open-stdout-of-
  `21_finalize` timing issue the dispatch described; `source_drift: false` is correct. No other file
  differs, so there is **no source/config/input/report drift**.
- Full-tree baseline `03_start_baseline.json` (2383 files, 22:17:02 +08:00) vs
  `23_submission_baseline.json` (2427 files, 22:43:14 +08:00): **old_tree_changes = 0** (no pre-existing
  tracked/untracked file was modified). Frozen anchors all match current bytes:
  `evaluate_gli02_candidate.py fddeeee0`, `geometry_constrained_gli03_r1.yaml 16c9d983`,
  `test_gli03_candidate_override.py 6433fa21`, `core/ground.py 2d25ccfd`, `core/calibration.py d29519a1`,
  `core/capture_input.py 56355e95`, `captures/.../meta.json 675c23de`, `captures/.../points.bin b81797f9`.
- Post-submission protected-path drift vs `23_submission_baseline.json`: **none**.
- New production files (absent in start, present in end, current SHAs):
  `core/ground_diagnostics.py 80ef45ae…`, `scripts/diagnose_gli04_geometry.py 85a83b88…`,
  `tests/test_gli04_geometry.py 7a3df86a…`.

## 2. Environment

- Local: Python `3.12.10`, NumPy `1.26.4`. Board target Python `3.8.10` / NumPy `1.17.4` was **not**
  executed; only `ast.parse(feature_version=(3,8))` and import-layer checks were performed. Local run
  does not validate the board; this is recorded, not claimed as PASS.

## 3. Exact commands, exit codes, results

| # | Command (workdir `D:/Code/ldiar`) | Exit | Result |
|---|---|---|---|
| 1 | `python -B docs/.../opencode_second_review_01/verify_hashes.py` | 0 | 111/111 match, manifest SHA unchanged (BEFORE and AFTER) |
| 2 | `python -B -W error -m unittest discover -s src/human_fall_detection/tests -p test_gli04_geometry.py -v` | 0 | Ran 8, OK (`gl04_tests.txt`) |
| 3 | `python -B -W error -m unittest discover -s src/human_fall_detection/tests -v` | 0 | Ran 423, OK (`fall_regression.txt`) |
| 4 | `python -B -W error -m unittest discover -s src/human_follow_calibration/tests -v` | 0 | Ran 2, OK (`follow_regression.txt`) |
| 5 | `python -B src/human_fall_detection/scripts/diagnose_gli04_geometry.py --prepared-npz …/real_candidate.adapted.npz --draft …/filled_real_draft.json --constrained-config …/geometry_constrained_gli03_r1.yaml --output-dir docs/.../opencode_second_review_01/12_real_final_rerun --display-budget 40` | 0 | `box_frame_records=356, sidecar_count=351255` (`12_real_final_rerun.txt`) |
| 6 | `python -B docs/.../probe_baseline.py` | 0 | heads match, old_tree_changes 0, anchors match, no drift (`probe_baseline.txt`) |
| 7 | `python -B docs/.../probe_ast.py` | 0 | 3.8 AST PASS all 5 files; core imports math/numpy/local only (`probe_ast.txt`) |
| 8 | `python -B docs/.../probe_cli.py` | 0 | all adversarial CLI refusals rc=2, positive rc=0 (`probe_cli.txt`) |
| 9 | `python -B docs/.../compare_real_reports.py` / `diff_05_12.py` | 0 | rerun byte-identical to author `12_real_final` on all 4 artifacts (`compare_real_reports.txt`) |
| 10 | `python -B docs/.../probe_report.py` | 0 | L02/L05 recompute PASS; 351255 sidecar rows, 356 records, 0 stat/bin/display mismatches (`probe_report.txt`) |
| 11 | `python -B docs/.../probe_prototype.py` | 0 | chain/dup/late/close/boundary/budget/terminal semantics all PASS (`probe_prototype.txt`) |
| 12 | `python -B docs/.../probe_positive.py` | 0 | clean+noisy closure 6/6 each, high-noise unresolved 6/6, baseline valid (`probe_positive.txt`) |
| 13 | `python -B docs/.../probe_edges.py` | 0 | empty frame count0/null/reason, hand stats, pca degeneracy PASS (`probe_edges.txt`) |

## 4. Independent evidence highlights (beyond rerunning author tests)

- **Real reproducibility (L06/R06).** My independent CLI run produced `diagnostic.json`,
  `source_indices.jsonl`, `local_source.svg`, `diagnostic.md` **byte-identical** to the author's
  `12_real_final` (SHAs `e879b51a…`, `4bb7c6cf…`, `968ae038…`, `f7815f24…`). Full-JSON field diff = 0.
  The `05_real_diagnostic` vs `12_real_final` difference is exactly the two corrected source SHAs plus
  the added `support_tail_threshold_m` field — i.e. the retained initial failure's fix, not hidden
  semantic drift; `box_frame_records/temporal/experiments` are identical between them.
- **L01 refusals (independent).** Refused with rc=2 and no output: schema `True`/`2`, kind
  `geometry_calibration`, status `approved`, missing/blank review, non-unit up_axis, inverted height,
  source mismatches (frame/units/meta_sha256/bin_sha256/manifest_points_sha256/time_domain),
  fit-group alias, fit `indices`, duplicate region id `FIT`, cross-frame/cross-group indices, bad config
  (`seed: true`), output == capture dir, output inside capture dir, frame mismatch, compute exception,
  legacy NPZ, tampered `points.bin`. Positive output is `kind=gli04_geometry_diagnostic`,
  `physical_verified=false`, and `validate_geometry_calibration` **rejects** it. Existing output is never
  overwritten (bytes unchanged; second run rc=2).
- **L02 conditional rotation (independent).** `R = Ry(+90°)` reconstructed exactly; `R·ẑ=[1,0,0]`,
  `Rᵀ·ẑ=[-1,0,0]`, `R·(Rᵀ ẑ)=ẑ`; report `extrinsic.status="unknown"`, `physical_verified=false`. The
  approved/negative-X/PCA hypotheses are separate labelled experiments with distinct `up_axis`.
- **L05 frozen vs replay (independent).** All three real hypotheses have `sampled_fit_count`,
  `raw_candidates`, `candidates`, `competition_truncated` equal between the frozen fitter and the replay
  generator; replay counters sum to `iterations=861` exactly
  (approved: angle 828, sample_area 12, separation 19, height 2, qualified 0). Thus the frozen
  `ground_degenerate` label is shown to be dominated by angle rejection, not SVD collapse; native
  validation ran in none of the real fits (`native_validation_executed=false` for all three).
- **L03/L04 recompute (independent).** Streamed all 351255 sidecar rows: pooled/frame/ordinal/seq mapping
  exact; recomputed `RMS/P95/support` from source points for all 356 box×frame records with 0 mismatches;
  bins (`floor(xyz/0.25)`) partition every record's rows with 0 mismatches; display rows are a stride
  subset and `display_count ≤ 40`; statistics are budget-invariant. Real data has 0 empty and 0 non-finite
  selected rows; the explicit empty case is covered by a fresh synthetic probe (`count=0`, `rms=null`,
  `reason="no_finite_selected_points"`, `stats` identical at display budgets 1 and 99).
- **Prototype safety (independent).** `search_events`: 40 exact duplicates → closed with 39
  `merged_exact` and 1 retained; offset chain (1.00/1.04/1.08) and angular chain (0/6/12°) → unresolved
  with the genuine A–C distinct pair and `similarity_envelope_not_closed`, never merged via a moving
  representative; late distinct (1.14 m) → unresolved with 2 witnesses; close/low-support distinct →
  unresolved. Certificate half-angle (5°) and offset-span (0.05 m) boundaries merge just inside and stay
  unresolved just outside. All candidate/refine/trace/iteration budgets of 0 and 1 → unresolved with the
  expected reason; count conservation `qualified=refined+unprocessed`,
  `refined=rejected+retained+merged_exact+merged_certified+unstored`,
  `draws_seen=len(trace)+trace_unrecorded` holds; invalid budgets (-1/True/1.5/out-of-ceiling) refused.
  `closure_scope` states closure covers only the supplied finite seen sequence.
- **Positive usefulness (R03, the required non-rejection check).** Fresh synthetic planes: clean and
  8 mm-noise close **6/6** each (3 seeds × original/permuted) while the frozen baseline also returns
  `valid`; 35 mm-noise stays unresolved 6/6 (safe, not a bug). No reliance on the author ledger.
- **S01 layering (independent).** `ast.parse(feature_version=(3,8))` PASS on all five new/research files;
  `core/ground_diagnostics.py` imports only `math`, `numpy`, and local `.ground`/`.capture_input` — no
  ROS/UI/yaml; the CLI's yaml use is confined to the pre-existing constrained-config loader.
- **Q10.** `27_service_probe_meta.json` records one ≤1 min no-tool probe: model
  `opencode-go/deepseek-v4.1-flash`, `db=default`, `probe_ok=true`, exit 0, elapsed 12.7 s, text
  `PROBE_OK`, no tool/error events. This review is the authorized read-only second pass.

## 5. Acceptance results (reviewer conclusion)

| ID | Result | Independent basis |
|---|---|---|
| L01 | PASS | probe_cli refusals + not-calibration + exclusive output + protected capture path |
| L02 | PASS | probe_report rotation math; separate approved/WHAT_IF/unknown; physical=false |
| L03 | PASS | 4×89 full coverage, sidecar mapping exact, no pooled fit, explicit empty case |
| L04 | PASS | hand residual stats, bins partition, display/stat separation, non-finite defined |
| L05 | PASS | frozen/replay parity, counters=861, early returns, holdout separated, no false SVD claim |
| L06 | PASS | independent rerun byte-identical; JSON/MD/sidecar/SVG; input/settings/seed/hashes present |
| R01 | PASS | baseline parity on fresh scenes; oracle limited to seen sequence |
| R02 | PASS | per-hypothesis traces, count closure, non-transitive chain not merged |
| R03 | PASS | clean+noise 6/6 closure, seeds/permutations, repeat equality |
| R04 | PASS | close/late/duplicate/chain semantics all unresolved where required |
| R05 | PASS | explicit budgets, exhaustion → unresolved, count conservation, ceilings |
| R06 | PASS | decision doc; prototype confined to evidence, not imported by core/runtime |
| S01 | PASS | scope/frozen anchors/baselines, 3.8 AST, imports, regressions 423+2, this review |
| B01 | BLOCKED | original bag/layout identity gap persists; no new evidence |
| B02 | BLOCKED | recording-bound extrinsic/world-up identity missing; no new evidence |
| D01 | NOT_RUN | no device/deploy/capture/network/GL05 performed |
| D02 | NOT_RUN | no real GL04 DPR / formal UI; the diagnostic SVG is not DPR proof |

### Q sub-rows

| Row | Result | Basis |
|---|---|---|
| Q01 | PASS | legal adapted+approved draft+explicit variant; defaults/labels/setting origin; refusals |
| Q02 | PASS | repeat determinism, same-path re-read (no cache), tamper refusal, caller mutation isolated, output collision |
| Q03 | PASS | per-frame × 4 boxes, empty/alias/cross-group, display budget vs full stats, traceable mapping |
| Q04 | PASS | approved vs negative-X vs PCA normal; extrinsic unknown; R vs Rᵀ; no mixed eligibility |
| Q05 | PASS | early returns/angle-height/degeneracy/competition; actual vs replay vs holdout separated |
| Q06 | PASS | low/high noise × seeds/orders; baseline valid; positive not via always-reject |
| Q07 | PASS | close/late/dup/chain × ordering; genuine distinct preserved |
| Q08 | PASS | candidate/refine/trace/iteration exhaustion; unprocessed never upgrades at terminal |
| Q09 | PASS | real capture 4×89 reproducible, no physical/calibration; external tree diffs classified (§6) |
| Q10 | PASS | ≤1 min probe PROBE_OK (defaults DB) → this read-only second review |

## 6. Defects and observations (grouped by root cause)

**Software defects found: none.** No false acceptance, no failure to close the required clean/noisy
positive, no safety-semantic violation. Non-blocking observations:

1. **External shared-tree additions (Q09 classification — not a GL-I04 defect).**
   - Source: shared `D:/Code/ldiar` tree, deliberately dirty.
   - Trigger: `pc_apps/human_limb/` untracked files; 3 appeared during the window
     (`limb_v2.py`, `run_limb_v2.py`, `synth_bend_session.py`) and two were modified after
     `23_submission_baseline.json` (22:43).
   - Actual: manifest `old_tree_changes=[]` (correct: no pre-existing file changed) plus
     `scope_note="outside-scope shared changes retained, not rolled back"`.
   - Expected: GL-I04 production scope is only the 3 `src/human_fall_detection` files.
   - Assessment: unrelated (human-limb rendering), outside scope, does not affect GL-I04 artifacts.
   - Minimal remedy: none required for acceptance; optionally enumerate off-scope *new* files in the
     Q09 classification so `old_tree_changes=[]` is not read as "no tree change at all".

2. **`residual_stats` empty-selection reason wording (cosmetic, L03).** A truly empty box reports
   `reason="no_finite_selected_points"`. Explicit `count=0`/`rms=null` are present, so the contract
   (`空区显式count0/null+reason`) is met. Minimal remedy if desired: distinguish `no_selected_points`
   from `no_finite_selected_points` (not acceptance-blocking).

3. **Frozen `ground_degenerate` label vs replay cause (known limitation, disclosed).** The approved real
   fit carries the frozen reason `ground_degenerate` although replay shows 828 angle rejections and only
   31 degenerate draws. GL-I04 does not launder this: it stores the frozen reason intact and exposes the
   separate replay counters, and `15_COORDINATE_EVIDENCE.md` states it explicitly. This satisfies L05's
   "must not assert SVD degeneracy from `reason=degenerate`".

## 7. Boundaries and adoption recommendation

- B01/B02 remain **BLOCKED**; D01/D02 remain **NOT_RUN**. No new authorized evidence exists for them.
  Software completion here does **not** prove a physical calibration or a real second ground.
- The diagnostic CLI (diagnostics only, never calibration) is **independently verified and recommended
  for offline observation use**.
- The `search_prototype.py` is **not recommended for runtime integration** in this item: independent
  probes confirm it is safety-conservative (never false-accepts, closes clean/noisy positives) but it is
  deliberately more conservative and costs >2× the frozen baseline, and the real approved input stays
  unresolved. Keep it as bounded research evidence only; any decision to adopt requires the bounded
  discrimination experiment described in `19_PLAN_REVISION_AND_DECISION.md`, under a new reviewed
  selection version and without using FIT residuals to pick validation points.
- Next physical action remains evidence collection of a recording-window extrinsic/config snapshot;
  do not tune sampling or auto-switch priors/gates.

## 8. Final

SECOND_REVIEW_SUBMITTED / STOPPED. All software items L01–L06, R01–R06, S01 and Q01–Q10 are
independently PASS; B01/B02 BLOCKED; D01/D02 NOT_RUN. No production writer spawned, no prototype
integrated, no acceptance/status document modified, no ACCEPTED claim. Reviewer's artifacts live only
under `opencode_second_review_01/`.
