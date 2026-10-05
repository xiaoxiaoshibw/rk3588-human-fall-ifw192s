"""GL-I05 R1 second review: closing (last) manifest/scope verification.

Re-hashes the submitted manifest file set after all review work, confirms no
author file changed during the review, records HEAD and the CLI_RECOVERY
administrative delta, and extracts the real-case evidence numbers. New
numbered output; does not overwrite 01_manifest_verify.json.
"""
import hashlib
import json
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
MANIFEST = ROOT / "docs" / "human_fall" / "evidence" / "2026-10-03_gl_i05_r1" / "research_01" / "11_submission_manifest.json"
BASELINE = HERE.parent / "00_before_baseline.json"


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))["files"]
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT,
                                   text=True).strip()
    branch = subprocess.check_output(["git", "branch", "--show-current"], cwd=ROOT,
                                     text=True).strip()
    mismatch = []
    baseline_mismatch = []
    for name, expected in manifest["files"].items():
        actual = sha256(ROOT / name)
        if actual != expected and name != "docs/human_fall/CLI_RECOVERY.md":
            mismatch.append({"file": name, "expected": expected, "actual": actual})
        if name in baseline and baseline[name].get("sha256") not in (None, actual):
            baseline_mismatch.append(name)
    # ledger real-case evidence
    ledger = json.loads((MANIFEST.parent / "experiment_results_final.json").read_text(encoding="utf-8"))
    real = {e["case"]: {"status": e["prototype"]["status"],
                        "witness_unique": e["witness_count_unique"],
                        "best_support": e["prototype"]["best_support"],
                        "near_pool_distinct": e["prototype"]["metrics"]["NEAR"]["distinct_pair_count"],
                        "all_distinct": e["prototype"]["metrics"]["ALL"]["distinct_pair_count"],
                        "qualified_draws": e["qualified_draws"],
                        "physical_verified": e.get("physical_verified"),
                        "origin": e.get("origin")}
            for e in ledger["real_WHAT_IF"]}
    cli_baseline = baseline.get("docs/human_fall/CLI_RECOVERY.md", {}).get("sha256")
    cli_now = sha256(ROOT / "docs/human_fall/CLI_RECOVERY.md")
    result = {
        "kind": "gli05_second_review_last_verify",
        "head": head, "branch": branch,
        "manifest_expected_head": manifest.get("head"),
        "author_file_mismatch_excluding_admin": mismatch,
        "baseline_mismatch": baseline_mismatch,
        "cli_recovery": {
            "manifest_expected": manifest["files"].get("docs/human_fall/CLI_RECOVERY.md"),
            "baseline": cli_baseline,
            "now": cli_now,
            "admin_only_delta": cli_now == cli_baseline
            and cli_now != manifest["files"].get("docs/human_fall/CLI_RECOVERY.md"),
        },
        "real_WHAT_IF": real,
        "all_author_files_unchanged_since_baseline": not baseline_mismatch,
    }
    with (HERE / "08_last_manifest_verify.json").open("x", encoding="utf-8") as handle:
        json.dump(result, handle, ensure_ascii=False, allow_nan=False, indent=2)
    print(json.dumps({"head": head, "author_mismatch": mismatch,
                      "baseline_mismatch": baseline_mismatch,
                      "cli_admin_only": result["cli_recovery"]["admin_only_delta"],
                      "real": real}, ensure_ascii=False)[:2000])


if __name__ == "__main__":
    main()
