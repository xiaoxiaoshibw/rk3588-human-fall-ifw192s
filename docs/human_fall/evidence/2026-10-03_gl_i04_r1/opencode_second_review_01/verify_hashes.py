"""Independent reviewer hash verification (read-only). No production writes."""
import hashlib
import json
from pathlib import Path

ROOT = Path(r"D:/Code/ldiar")
RUN = ROOT / "docs/human_fall/evidence/2026-10-03_gl_i04_r1"


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


manifest = json.loads((RUN / "11_submission_manifest.json").read_text(encoding="utf-8"))
addendum = json.loads((RUN / "25_manifest_addendum.json").read_text(encoding="utf-8"))
add = addendum["sha_addendum"]

mismatch, missing, ok = {}, [], 0
for rel, expected in manifest["files"].items():
    p = ROOT / rel
    if not p.exists():
        missing.append(rel)
        continue
    actual = sha(p)
    if rel in add:
        if actual != add[rel]["actual"] or expected != add[rel]["old"]:
            mismatch[rel] = {"expected_manifest": expected, "addendum": add[rel], "actual": actual}
        else:
            ok += 1
    elif actual != expected:
        mismatch[rel] = {"expected": expected, "actual": actual}
    else:
        ok += 1

print(json.dumps({
    "manifest_declared_files": len(manifest["files"]),
    "matched_or_addendum_resolved": ok,
    "mismatches": mismatch,
    "missing": missing,
    "manifest_sha256_actual": sha(RUN / "11_submission_manifest.json"),
    "manifest_sha256_addendum": addendum.get("manifest_sha256"),
    "source_drift_addendum": addendum.get("source_drift"),
}, indent=2))
