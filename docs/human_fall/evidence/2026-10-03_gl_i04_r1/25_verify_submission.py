"""Resolve the submission runner's open stdout hash without replacing evidence."""
import hashlib
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
manifest = json.loads((OUT / "11_submission_manifest.json").read_text(encoding="utf-8"))
changes = {}
for rel, expected in manifest["files"].items():
    actual = hashlib.sha256((ROOT / rel).read_bytes()).hexdigest()
    if actual != expected:
        changes[rel] = {"old": expected, "actual": actual}
allowed = "docs/human_fall/evidence/2026-10-03_gl_i04_r1/24_submission_run.txt"
assert set(changes).issubset({allowed}), changes
payload = {"status": "SUBMITTED_STOPPED", "manifest": "11_submission_manifest.json",
           "manifest_sha256": hashlib.sha256((OUT / "11_submission_manifest.json").read_bytes()).hexdigest(),
           "sha_addendum": changes, "source_drift": False,
           "reason": "24_submission_run.txt was open stdout of21_finalize during manifest snapshot; now closed. Only this log SHA superseded; original manifest/evidence preserved."}
with (OUT / "25_manifest_addendum.json").open("x", encoding="utf-8") as handle:
    json.dump(payload, handle, indent=2)
print(json.dumps(payload))
