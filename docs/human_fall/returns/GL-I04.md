
## GL-I04 R1 Codex self-submission / 2026-10-03

Status SUBMITTED; Codex sole production writer, now STOPPED. No independent acceptance claim.
Acceptance GLI04_ACCEPTANCE.md v1 SHA=8a447f99cd8d36fa1df3057c6f4d4663d51e4f2d9a1b017ec4287d02b96159ab
ponytail read: C:/Users/30680/.codex/skills/ponytail/SKILL.md.
Branch/HEAD master/cbd0be1; full tracked+untracked before03/after23. Frozen approved input/oldcore/config/GL-I03/data/UI unchanged.
Design/limitations/rejected hypotheses: 00_diag.md, original failures06/07, revised plan19, final ledger18 and summary22.

| ID | self result | evidence |
|---|---|---|
| L01 | PASS (self) | 08_diagnostic_tests.txt: source/schema/units/frame/group/config/output/capture/legacy refusal; loader reconstruction + CLI exclusive mkdir |
| L02 | PASS (self) | HandFixtures.test_rotation_hand_inverse; 15_COORDINATE_EVIDENCE.md; final JSON approved/WHAT_IF/unknown |
| L03 | PASS (self) | 14_audit_results.json: all351255 rows and356 box/frame records; empty/mapping fixture |
| L04 | PASS (self) | hand RMS/P95/tails/bins/display fixture + independent full source recomputation14 |
| L05 | PASS (self) | frozen/replay parity final12, actual early returns/degeneracy fixture08, experiment baseline parity18; no native validation in real runs |
| L06 | PASS (self) | 12_real_final_run.txt exit0; final report/sidecar/SVG; 14 reproducibility and input SHA |
| R01 | PASS (self) | 18_experiment_final_run.txt exit0; same sequence digest/sample/RNG/settings + frozen raw/refined/count parity |
| R02 | PASS (self) | research_01/experiment_results_final.json counts/events; fixed certificate/offset+angular chain all orders |
| R03 | PASS (self) | final30 synthetic cases:3seeds x2orders x5scenes; clean/noise closures6each; repeat equality |
| R04 | PASS (self) | close/dual/late/distinct/duplicate/chain + all-seen oracle and refinement rejection semantic cases |
| R05 | PASS (self) | candidate0/1, refine0/1, trace0/1, iterations0/1 terminal exhaustion; count conservation; explicit ceilings/cost22 |
| R06 | PASS (self) | 19_PLAN_REVISION_AND_DECISION.md and final22cost; prototype only evidence; no runtime adoption |
| S01 | LOCAL PASS / review NOT_RUN | LOCAL PASS: frozen anchors/full tree23 vs03, AST14, regressions10(423)/13(2); independent OpenCode PENDING |
| B01 | BLOCKED | BLOCKED original bag/layout identity gap |
| B02 | BLOCKED | BLOCKED recording extrinsic/ground identity missing15 |
| D01 | NOT_RUN | NOT_RUN no device/deploy/capture/network/GL05 |
| D02 | NOT_RUN | NOT_RUN no real GL04 DPR/formal UI |

Q subrows: {"Q01": "L01/L05/L06", "Q02": "L01/L03/S01 (repeat/new output, source same-path tamper/caller copy/hash reload)", "Q03": "L03/L04", "Q04": "L02/L05/L06/B02", "Q05": "L05/R01", "Q06": "R01/R03", "Q07": "R02/R04", "Q08": "R02/R05", "Q09": "L06/R06/S01/B01/B02", "Q10": "PENDING independent review/probe"}

New source SHA:
```json
{
  "src/human_fall_detection/core/ground_diagnostics.py": "80ef45ae59d0fbb4e01bd7fb334043d6bcde0f58e86aec057e42561e4c974e66",
  "src/human_fall_detection/scripts/diagnose_gli04_geometry.py": "85a83b8835d00e186840071c2eec0e7a7860970243823779dab06d13ba517b9e",
  "src/human_fall_detection/tests/test_gli04_geometry.py": "7a3df86ae6386cdd476429b3ac54b0b3fcead8e0e6fbce1ddd2baf4af8ffcb7c"
}
```

Raw commands/exit/logs:
```json
[
  {
    "command": "python -B -W error -m unittest discover -s src/human_fall_detection/tests -p test_gli04_geometry.py -v",
    "log": "08_diagnostic_tests.txt",
    "exit": 0
  },
  {
    "command": "python -B -W error -m unittest discover -s src/human_fall_detection/tests -v",
    "log": "10_fall_regression.txt",
    "exit": 0
  },
  {
    "command": "python -B -W error -m unittest discover -s src/human_follow_calibration/tests -v",
    "log": "13_follow_regression.txt",
    "exit": 0
  },
  {
    "command": "python -B -W error src/human_fall_detection/scripts/diagnose_gli04_geometry.py --prepared-npz docs/human_fall/evidence/2026-10-03_gl_i02_r1/08_real/real_candidate.adapted.npz --draft docs/human_fall/evidence/2026-10-03_gl_i02_r1/codex_review_01/work/filled_real_draft.json --constrained-config src/human_fall_detection/config/geometry_constrained_gli03_r1.yaml --output-dir docs/human_fall/evidence/2026-10-03_gl_i04_r1/12_real_final --display-budget 40",
    "log": "12_real_final_run.txt",
    "exit": 0
  },
  {
    "command": "python -B -W error docs/human_fall/evidence/2026-10-03_gl_i04_r1/14_audit.py",
    "log": "14_audit_run.txt",
    "exit": 0
  },
  {
    "command": "python -B -W error docs/human_fall/evidence/2026-10-03_gl_i04_r1/research_01/experiment.py",
    "log": "18_experiment_final_run.txt",
    "exit": 0
  },
  {
    "command": "initial experiment.py (exact witness hypothesis)",
    "log": "06_experiment_run.txt",
    "exit": 1
  },
  {
    "command": "initial diagnostic tests (insufficient replay ordering)",
    "log": "07_diagnostic_tests.txt",
    "exit": 1
  }
]
```

All evidence paths relative to docs/human_fall/evidence/2026-10-03_gl_i04_r1/. Manifest11 provides all relevant hashes. Local Python3.12.10/NumPy1.26.4 and Python3.8 AST only; board NOT_RUN.
Recommend offline diagnostic use; prototype NOT adopted into runtime, pending independent review. Obtain recording-bound coordinate/extrinsic evidence and independent fixed-box tail identity next, without residual-selected validation.
Next: one <=1min Go Flash/defaultDB no-tool probe, then read-only independent second review. No concurrent source writer.

## Codex二审接回附记 / 2026-10-03

状态记录SUBMITTED/STOPPED；实际OpenCode独立二审已完成（不以自验冒充）。L01–L06/R01–R06/S01/Q01–Q10独审PASS，B01/B02 BLOCKED、D01/D02 NOT_RUN。session ses_efdc5ab31ffeBwyoFXmoG3GmHX/Go Flash/defaultDB/exit0/finish stop，提交源码SHA全部保持。完整证据与对审查报告的事实补正见evidence/2026-10-03_gl_i04_r1/32_CLOSEOUT.md；无ACCEPTED声明、无源码返工/原型接入。
