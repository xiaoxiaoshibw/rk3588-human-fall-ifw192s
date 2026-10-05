#!/usr/bin/env python3
"""GL-03 R4 scope check against the pre-R4 human_fall_detection manifest.

Classifies changed/new package files so a concurrent external writer stays
visible: ``declared_changed`` are the three source files this round wrote (plus
the test file), anything else is reported and never touched. Exits 1 when an
undeclared package change or a missing file exists.
"""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
MANIFEST = json.loads(
    (HERE / "00_before_manifest.json").read_text(encoding="utf-8"))
DECLARED = {
    "src/human_fall_detection/core/calibration.py",
    "src/human_fall_detection/core/node_runtime.py",
    "src/human_fall_detection/tests/test_gl03_candidates_geometry.py",
}
SUFFIXES = (".py", ".yaml", ".xml", ".sh", ".launch")


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


changed, missing = [], []
for relative, before in sorted(MANIFEST.items()):
    path = ROOT / relative
    if not path.exists():
        missing.append(relative)
        continue
    after = sha256(path)
    if after != before:
        changed.append({"path": relative, "before": before, "after": after})

declared = [entry for entry in changed if entry["path"] in DECLARED]
unexpected = [entry for entry in changed if entry["path"] not in DECLARED]
package = ROOT / "src/human_fall_detection"
current = {
    str(path.relative_to(ROOT)).replace("\\", "/")
    for path in package.rglob("*")
    if path.is_file() and path.suffix in SUFFIXES
    and "__pycache__" not in path.parts
}
new_files = sorted(current - set(MANIFEST))
result = {
    "manifest_entries": len(MANIFEST),
    "declared_changed": declared,
    "unexpected_changed": unexpected,
    "new_files": new_files,
    "missing": missing,
    "clean_within_declared_scope": not unexpected and not missing and not new_files,
}
print(json.dumps(result, indent=1, sort_keys=True))
if not result["clean_within_declared_scope"]:
    sys.exit(1)
