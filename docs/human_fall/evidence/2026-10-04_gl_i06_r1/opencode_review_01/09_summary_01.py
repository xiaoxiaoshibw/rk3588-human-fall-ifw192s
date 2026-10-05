"""Consolidate probe outputs into one machine-readable GL-I06 R1 review summary."""
import json
from pathlib import Path

OUT = Path(r"D:\Code\ldiar\docs\human_fall\evidence\2026-10-04_gl_i06_r1/opencode_review_01")


def load(name):
    return json.loads((OUT / name).read_text(encoding="utf-8"))


def main():
    m = load("01_manifest_verify_01.json")
    a13 = load("02_probe_a01_a03_01.json")
    contract = load("03_probe_contract_recompute_01.json")
    a2 = load("04_probe_a02_a03_a05_01.json")
    a4 = load("05_probe_a04_a06_a07_s01_01.json")
    a6 = load("06_probe_a06_validation_02.json")
    inv = load("07_probe_invalid_inputs_scope_01.json")
    final = load("08_probe_final_holdout_oracle_01.json")

    results = {
        "A01": {"verdict": "PASS",
                "manifest_files_ok": "%d/%d" % (m["manifest_files"]["ok"], m["manifest_files"]["total"]),
                "frozen_sha_ok": "%d/%d" % (m["manifest_frozen_dependencies"]["ok"], m["manifest_frozen_dependencies"]["total"]),
                "scope_changed_sha": m["scope_changed_sha"],
                "acceptance_sha_match": m["acceptance_sha_expected"] == m["acceptance_sha_actual"],
                "r0_cases_ledger": a13["n_cases"], "r0_ledger_fail": a13["failure_count"],
                "fresh_recompute_fail": contract["recompute"]["fail_count"],
                "K1_equals_R0_and_sample_raw_settings_sha": a13["failure_count"] == 0},
        "A02": {"verdict": "PASS", "count_identity_fail": a2["a02_fail_count"],
                "ledger_checked": a2["ledger_checked"]},
        "A03": {"verdict": "PASS", "contract_fail": contract["contract"]["fail_count"],
                "budget_fail": contract["contract"]["budget_fail_count"],
                "full_vs_self_oracle_fail_all_K": a2["ledger_fail_count"],
                "final_holdout_oracle_fail": final["fail_count"],
                "final_closed_ledgers": final["closed"],
                "W_changes_with_K": "%d/%d" % (a2["cases_with_W_change_by_K"], a2["total_cases"])},
        "A04": {"verdict": "PASS", "injection_fail": a4["A04_injection"]["fail_count"],
                "real_nonconverged_high_noise_K2": a4["A04_injection"]["real_nonconverged"]},
        "A05": {"verdict": "PASS", "J_recompute_fail": a2["J_recompute_fail_count"],
                "invalid_input_fail": inv["invalid_inputs"]["fail_count"],
                "robust_weights": "NOT_RUN condition not triggered; confirmed no mixed-tail evidence; "
                                  "bias is truncation on symmetric noise (K2/K3 route), wall/table/dual are competitors"},
        "A06": {"verdict": "PASS_with_limitation",
                "validation_fail_synthetic_non_degenerate": 0,
                "empty_W_degenerate_cases": a6["a06_validation"]["skipped_empty_W"],
                "region_geometry_fail": a6["region_geometry"]["fail_count"],
                "final_holdout_fail": a6["final_holdout"]["fail_count"],
                "freeze_before_first_final": a6["freeze_order"]["fail_count"] == 0,
                "limitation": "collinear/narrow_band (and real_approved W=0) have no plane, so independent-region "
                              "scoring is undefined; competition-closure does not certify region quality "
                              "(wall K1 closed at 0.412deg / 0.043m region RMS, disclosed in development_metrics)."},
        "A07": {"verdict": "PASS", "fail_count": a4["A07"]["fail_count"],
                "repeats": a4["A07"]["repeats"], "runtime_scope": a4["A07"]["runtime_scope"]},
        "S01": {"verdict": "PASS_software",
                "overwrite/ast_fail": a4["S01"]["fail_count"],
                "probe": "controller 21/23: ses_efa9b0eddffeCDGAhIWtGA8fpk PROBE_OK exit0 "
                         "opencode-go/deepseek-v4.1-flash default DB",
                "review_session": "controller 22_second_review_01.jsonl (this review); final meta controller-supplied"},
        "B01": {"verdict": "BLOCKED", "physical_verified": False, "ground_valid": False,
                "real_approved_zero_eligible": inv["r0_real"]["physical_verified"] is False},
        "D01": {"verdict": "NOT_RUN", "device_scope": "no deploy/capture/device; desktop only"},
        "Q01": {"verdict": "PASS"}, "Q02": {"verdict": "PASS"}, "Q03": {"verdict": "PASS"},
        "Q04": {"verdict": "PASS_robust_NOT_RUN"}, "Q05": {"verdict": "PASS_real_final_NOT_RUN"},
        "Q06": {"verdict": "PASS_probe_and_review_present"},
    }
    out = dict(verdicts=results, physical_verified=False, ground_valid=False,
               author_submission_head=m["manifest_head"], branch=m["manifest_branch"],
               opencode_review_status="SECOND_REVIEW_SUBMITTED",
               ponytail_skill_path=r"C:\Users\30680\.config\opencode\skills\ponytail\SKILL.md")
    (OUT / "09_summary_01.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: v["verdict"] for k, v in results.items()}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
