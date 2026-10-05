#!/usr/bin/env python3
"""GL-03 R5 scope check against the pre-R5 full manifest.

Classifies changed/new package files so a concurrent external writer stays
visible: ``declared_changed`` are the source/test files this round wrote,
anything else is reported and never touched. Exits 1 when an undeclared
package change or a missing file exists.
"""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
MANIFEST = json.loads(
    (HERE / "00_before_manifest.json").read_text(encoding="utf-8"))["files"]
DECLARED = {
    "src/human_fall_detection/core/calibration.py",
    "src/human_fall_detection/core/lidar_candidates.py",
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
    if isinstance(before, str) and before.startswith("UNREADABLE"):
        continue
    path = ROOT / relative
    try:
        exists = path.exists()
    except OSError:
        continue
    if not exists:
        missing.append(relative)
        continue
    after = sha256(path)
    if after != before:
        changed.append({"path": relative, "before": before, "after": after})

declared = [entry for entry in changed if entry["path"] in DECLARED]
package_prefix = "src/human_fall_detection/"
in_package = [entry for entry in changed if entry["path"].startswith(package_prefix)]
unexpected = [entry for entry in in_package if entry["path"] not in DECLARED]
external = [entry for entry in changed
            if not entry["path"].startswith(package_prefix)]
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
    "external_changed_outside_gl03": external,
    "new_files": new_files,
    "missing": missing,
    "clean_within_declared_scope": not unexpected and not missing and not new_files,
}
print(json.dumps(result, indent=1, sort_keys=True))
if not result["clean_within_declared_scope"]:
    sys.exit(1)
