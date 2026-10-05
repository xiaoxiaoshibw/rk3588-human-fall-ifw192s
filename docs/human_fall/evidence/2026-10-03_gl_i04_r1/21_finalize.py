"""Freeze self-submission manifest/return; no production mutations."""
import collections
import hashlib
import json
from pathlib import Path
import statistics
import sys

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
from snapshot import snapshot


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    ledger = json.loads((OUT / "research_01/experiment_results_final.json").read_text(encoding="utf-8"))
    summary = {}
    for kind in ("clean", "noise", "high_noise", "dual", "close"):
        rows = [row for row in ledger["synthetic"] if row["case"].startswith(kind + "_")]
        summary[kind] = {"prototype": dict(collections.Counter(row["prototype"]["status"] for row in rows)),
                         "oracle": dict(collections.Counter(row["oracle"]["status"] for row in rows)),
                         "prototype_median_s": statistics.median(row["prototype"]["elapsed_s"] for row in rows),
                         "baseline_median_s": statistics.median(row["baseline_elapsed_s"] for row in rows),
                         "peak_retained": max(row["prototype"]["counts"]["peak_retained"] for row in rows)}
    with (OUT / "22_final_research_summary.json").open("x", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=2)
    snapshot("23_submission_baseline.json")
    start = json.loads((OUT / "03_start_baseline.json").read_text(encoding="utf-8"))
    end = json.loads((OUT / "23_submission_baseline.json").read_text(encoding="utf-8"))
    assert start["head"] == end["head"] == "cbd0be1c86a1051a9a5800dfb7263f842896e1e6"
    new_source = ["src/human_fall_detection/core/ground_diagnostics.py",
                  "src/human_fall_detection/scripts/diagnose_gli04_geometry.py",
                  "src/human_fall_detection/tests/test_gli04_geometry.py"]
    for path in new_source:
        assert path not in start["files"]
    changes = [path for path, value in start["files"].items() if end["files"].get(path) != value]
    protected_prefixes = ("src/human_fall_detection/", "src/inno_", "webui/", "config/", "captures/",
                          "docs/human_fall/evidence/2026-10-03_gl_i02_r1/", "docs/human_fall/evidence/2026-10-03_gl_i03_r1/")
    assert not [path for path in changes if path.startswith(protected_prefixes)], changes
    anchors = {"src/human_fall_detection/scripts/evaluate_gli02_candidate.py": "fddeeee0b4c6e014b608b64d8805b90997977b0e6eee357d6cc28f02726322c8",
               "src/human_fall_detection/config/geometry_constrained_gli03_r1.yaml": "16c9d983c0202bb122be300db6faf70e7415300756392569acafa7d444cd49aa",
               "src/human_fall_detection/tests/test_gli03_candidate_override.py": "6433fa21200d1cbae0236c3701e31a5ec7b96d6d34549279909cacb6d948eccb",
               "src/human_fall_detection/core/ground.py": "2d25ccfd9b41b4e16b36c07eec5b243ac50a63bf15230445d942e0f1bcebc4d3",
               "src/human_fall_detection/core/calibration.py": "d29519a1cdb5e495d23115bc89886e9071e4f2055ff529285e933cebdb7c58a3",
               "src/human_fall_detection/core/capture_input.py": "56355e9594433d91c871685f58c6ae9f8fe0e47d2b3ad7d07f9b5b8050b85f16",
               "captures/remote/cap_20261002_163621/meta.json": "675c23ded9dcee82e6e985f17665469a487d34520408582708601eb188b1d692",
               "captures/remote/cap_20261002_163621/points.bin": "b81797f9825792655e5930edeb39c15275eb64e01999984884da61d252c599ff"}
    for path, expected in anchors.items():
        assert sha(ROOT / path) == expected, path
    mappings = {"L01": "08_diagnostic_tests.txt: source/schema/units/frame/group/config/output/capture/legacy refusal; loader reconstruction + CLI exclusive mkdir",
                "L02": "HandFixtures.test_rotation_hand_inverse; 15_COORDINATE_EVIDENCE.md; final JSON approved/WHAT_IF/unknown",
                "L03": "14_audit_results.json: all351255 rows and356 box/frame records; empty/mapping fixture",
                "L04": "hand RMS/P95/tails/bins/display fixture + independent full source recomputation14",
                "L05": "frozen/replay parity final12, actual early returns/degeneracy fixture08, experiment baseline parity18; no native validation in real runs",
                "L06": "12_real_final_run.txt exit0; final report/sidecar/SVG; 14 reproducibility and input SHA",
                "R01": "18_experiment_final_run.txt exit0; same sequence digest/sample/RNG/settings + frozen raw/refined/count parity",
                "R02": "research_01/experiment_results_final.json counts/events; fixed certificate/offset+angular chain all orders",
                "R03": "final30 synthetic cases:3seeds x2orders x5scenes; clean/noise closures6each; repeat equality",
                "R04": "close/dual/late/distinct/duplicate/chain + all-seen oracle and refinement rejection semantic cases",
                "R05": "candidate0/1, refine0/1, trace0/1, iterations0/1 terminal exhaustion; count conservation; explicit ceilings/cost22",
                "R06": "19_PLAN_REVISION_AND_DECISION.md and final22cost; prototype only evidence; no runtime adoption",
                "S01": "LOCAL PASS: frozen anchors/full tree23 vs03, AST14, regressions10(423)/13(2); independent OpenCode PENDING",
                "B01": "BLOCKED original bag/layout identity gap", "B02": "BLOCKED recording extrinsic/ground identity missing15",
                "D01": "NOT_RUN no device/deploy/capture/network/GL05", "D02": "NOT_RUN no real GL04 DPR/formal UI"}
    q = {"Q01": "L01/L05/L06", "Q02": "L01/L03/S01 (repeat/new output, source same-path tamper/caller copy/hash reload)",
         "Q03": "L03/L04", "Q04": "L02/L05/L06/B02", "Q05": "L05/R01", "Q06": "R01/R03",
         "Q07": "R02/R04", "Q08": "R02/R05", "Q09": "L06/R06/S01/B01/B02", "Q10": "PENDING independent review/probe"}
    commands = [
        {"command": "python -B -W error -m unittest discover -s src/human_fall_detection/tests -p test_gli04_geometry.py -v", "log": "08_diagnostic_tests.txt", "exit": 0},
        {"command": "python -B -W error -m unittest discover -s src/human_fall_detection/tests -v", "log": "10_fall_regression.txt", "exit": 0},
        {"command": "python -B -W error -m unittest discover -s src/human_follow_calibration/tests -v", "log": "13_follow_regression.txt", "exit": 0},
        {"command": "python -B -W error src/human_fall_detection/scripts/diagnose_gli04_geometry.py --prepared-npz docs/human_fall/evidence/2026-10-03_gl_i02_r1/08_real/real_candidate.adapted.npz --draft docs/human_fall/evidence/2026-10-03_gl_i02_r1/codex_review_01/work/filled_real_draft.json --constrained-config src/human_fall_detection/config/geometry_constrained_gli03_r1.yaml --output-dir docs/human_fall/evidence/2026-10-03_gl_i04_r1/12_real_final --display-budget 40", "log": "12_real_final_run.txt", "exit": 0},
        {"command": "python -B -W error docs/human_fall/evidence/2026-10-03_gl_i04_r1/14_audit.py", "log": "14_audit_run.txt", "exit": 0},
        {"command": "python -B -W error docs/human_fall/evidence/2026-10-03_gl_i04_r1/research_01/experiment.py", "log": "18_experiment_final_run.txt", "exit": 0},
        {"command": "initial experiment.py (exact witness hypothesis)", "log": "06_experiment_run.txt", "exit": 1},
        {"command": "initial diagnostic tests (insufficient replay ordering)", "log": "07_diagnostic_tests.txt", "exit": 1}]
    sources = {path: sha(ROOT / path) for path in new_source}
    text = ["\n## GL-I04 R1 Codex self-submission / 2026-10-03", "",
            "Status SUBMITTED; Codex sole production writer, now STOPPED. No independent acceptance claim.",
            "Acceptance GLI04_ACCEPTANCE.md v1 SHA=" + sha(ROOT / "docs/human_fall/GLI04_ACCEPTANCE.md"),
            "ponytail read: C:/Users/30680/.codex/skills/ponytail/SKILL.md.",
            "Branch/HEAD master/cbd0be1; full tracked+untracked before03/after23. Frozen approved input/oldcore/config/GL-I03/data/UI unchanged.",
            "Design/limitations/rejected hypotheses: 00_diag.md, original failures06/07, revised plan19, final ledger18 and summary22.", "",
            "| ID | self result | evidence |", "|---|---|---|"]
    for key, value in mappings.items():
        status = "BLOCKED" if key.startswith("B") else "NOT_RUN" if key.startswith("D") else "LOCAL PASS / review NOT_RUN" if key == "S01" else "PASS (self)"
        text.append("| %s | %s | %s |" % (key, status, value))
    text.extend(["", "Q subrows: " + json.dumps(q), "", "New source SHA:", "```json", json.dumps(sources, indent=2), "```",
                 "", "Raw commands/exit/logs:", "```json", json.dumps(commands, indent=2), "```", "",
                 "All evidence paths relative to docs/human_fall/evidence/2026-10-03_gl_i04_r1/. Manifest11 provides all relevant hashes. Local Python3.12.10/NumPy1.26.4 and Python3.8 AST only; board NOT_RUN.",
                 "Recommend offline diagnostic use; prototype NOT adopted into runtime, pending independent review. Obtain recording-bound coordinate/extrinsic evidence and independent fixed-box tail identity next, without residual-selected validation.",
                 "Next: one <=1min Go Flash/defaultDB no-tool probe, then read-only independent second review. No concurrent source writer."])
    returns = ROOT / "docs/human_fall/returns/GL-I04.md"
    with returns.open("a", encoding="utf-8") as handle:
        handle.write("\n".join(text) + "\n")
    relevant = {str(path.relative_to(ROOT)).replace("\\", "/"): sha(path)
                for path in (ROOT / "src/human_fall_detection").rglob("*")
                if path.is_file() and "__pycache__" not in path.parts}
    for path in OUT.rglob("*"):
        if path.is_file() and "__pycache__" not in path.parts:
            relevant[str(path.relative_to(ROOT)).replace("\\", "/")] = sha(path)
    for rel in ["docs/human_fall/GLI04_TASK.md", "docs/human_fall/GLI04_ACCEPTANCE.md", "docs/human_fall/WORKFLOW.md",
                "docs/human_fall/AI_PROMPT_GLI04_CODEX_R1.md", "docs/human_fall/AI_PROMPT_GLI04_OPENCODE_SECOND_REVIEW_R1.md",
                "docs/human_fall/returns/GL-I04.md", "docs/human_fall/evidence/2026-10-03_gl_i02_r1/08_real/real_candidate.adapted.npz",
                "docs/human_fall/evidence/2026-10-03_gl_i02_r1/codex_review_01/work/filled_real_draft.json"] + list(anchors):
        relevant[rel] = sha(ROOT / rel)
    payload = {"item": "GL-I04", "round": "R1", "status": "SUBMITTED_STOPPED", "writer": "Codex",
               "run_root": str(OUT), "acceptance": "docs/human_fall/GLI04_ACCEPTANCE.md", "acceptance_version": 1,
               "start_baseline": "03_start_baseline.json", "end_baseline": "23_submission_baseline.json",
               "files": relevant, "new_production_source": sources, "frozen_anchors": anchors,
               "old_tree_changes": changes, "scope_note": "outside-scope shared changes retained, not rolled back",
               "self_evidence": mappings, "Q_evidence": q, "commands": commands,
               "independent_review": "NOT_RUN", "physical_verified": False}
    with (OUT / "11_submission_manifest.json").open("x", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
    print(json.dumps({"status": payload["status"], "files": len(relevant), "old_tree_changes": changes,
                      "new_production_source": sources}))


if __name__ == "__main__":
    main()
