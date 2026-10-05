#!/usr/bin/env python3
"""GL-03 R3 scope check against the frozen pre-R3 manifest (00_before_manifest.json).

Classifies differences so an external concurrent writer stays visible instead of
being absorbed or reverted:

- ``declared_changed``: the four files this R3 round wrote;
- ``coordinator_docs``: docs already modified by the coordinator before this
  session (git status at session start) - not production code;
- ``unexpected_changed`` / ``new_files``: anything else, reported but never
  touched by this round. Exits 1 when these exist so the review sees them.
"""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
MANIFEST = json.loads(
    (HERE / "00_before_manifest.json").read_text(encoding="utf-8-sig"))

DECLARED = {
    "src/human_fall_detection/core/calibration.py",
    "src/human_fall_detection/core/lidar_candidates.py",
    "src/human_fall_detection/core/node_runtime.py",
    "src/human_fall_detection/tests/test_gl03_candidates_geometry.py",
}
COORDINATOR_DOCS = {
    "docs/human_fall/GL03_ACCEPTANCE.md",
    "docs/human_fall/returns/GL-03.md",
}
SUFFIXES = (".py", ".yaml", ".xml", ".sh", ".launch")


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


changed = []
missing = []
for relative, before in sorted(MANIFEST.items()):
    path = ROOT / relative
    if not path.exists():
        missing.append(relative)
        continue
    after = sha256(path)
    if after != before:
        changed.append({"path": relative, "before": before, "after": after})

declared = [e for e in changed if e["path"] in DECLARED]
coordinator = [e for e in changed if e["path"] in COORDINATOR_DOCS]
unexpected = [e for e in changed
              if e["path"] not in DECLARED and e["path"] not in COORDINATOR_DOCS]

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
    "coordinator_docs": coordinator,
    "unexpected_changed": unexpected,
    "new_files_not_in_pre_r3_manifest": new_files,
    "missing": missing,
    "clean_within_declared_scope": not unexpected and not missing,
}
print(json.dumps(result, indent=1, sort_keys=True))
if unexpected or missing:
    sys.exit(1)
