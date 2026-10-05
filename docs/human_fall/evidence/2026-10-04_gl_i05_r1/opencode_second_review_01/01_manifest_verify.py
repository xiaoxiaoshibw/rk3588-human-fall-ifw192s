"""GL-I05 R1 second review: verify author submission manifest SHAs.

Read-only. Compares the submitted 11_submission_manifest.json hashes and sizes
against the actual files on disk, and against the pre-review baseline recorded
in ../00_before_baseline.json. Writes only into this review directory.
"""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUN = HERE.parents[1] / "2026-10-03_gl_i05_r1" / "research_01"
MANIFEST = RUN / "11_submission_manifest.json"
BASELINE = HERE.parent / "00_before_baseline.json"
ROOT = HERE.parents[4]


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def rel(path):
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def main():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))["files"]
    entries = manifest["files"]
    actual = {}
    missing = []
    mismatch = []
    for name, expected in entries.items():
        path = ROOT / name
        if not path.is_file():
            missing.append(name)
            continue
        got = sha256(path)
        size = path.stat().st_size
        actual[name] = {"sha256": got, "size": size}
        if got != expected:
            mismatch.append({"file": name, "expected": expected, "actual": got})
    # baseline comparison: safe baseline is the reference before the review.
    baseline_missing = []
    baseline_mismatch = []
    for name, expected in actual.items():
        base = baseline.get(name)
        if base is None:
            baseline_missing.append(name)
        elif base["sha256"] != expected["sha256"]:
            baseline_mismatch.append({"file": name, "baseline": base["sha256"],
                                       "actual": expected["sha256"]})
    result = {
        "kind": "gli05_second_review_manifest_verify",
        "manifest": rel(MANIFEST),
        "manifest_entry_count": len(entries),
        "actual_present": len(actual),
        "missing": missing,
        "sha_mismatch": mismatch,
        "baseline_present": sum(1 for n in actual if n in baseline),
        "baseline_missing": baseline_missing,
        "baseline_mismatch": baseline_mismatch,
        "all_manifest_match": not missing and not mismatch,
        "all_match_baseline": not baseline_missing and not baseline_mismatch,
        "new_files": manifest.get("new_files"),
        "head": manifest.get("head"),
    }
    out = HERE / "01_manifest_verify.json"
    with out.open("x", encoding="utf-8") as handle:
        json.dump(result, handle, ensure_ascii=False, allow_nan=False, indent=2)
    print(json.dumps({"out": str(out),
                      "manifest_entries": len(entries),
                      "missing": len(missing),
                      "sha_mismatch": len(mismatch),
                      "baseline_missing": len(baseline_missing),
                      "baseline_mismatch": len(baseline_mismatch),
                      "all_manifest_match": result["all_manifest_match"],
                      "all_match_baseline": result["all_match_baseline"]},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
