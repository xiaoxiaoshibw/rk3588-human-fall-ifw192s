#!/usr/bin/env python3
"""GL-03 R4 baseline manifest before any R4 write.

Records HEAD, branch, and SHA256 of every human_fall_detection source file
(py/yaml/xml/sh/launch) plus the R3 manifest cross-check, so the R4 diff and
range stay auditable. Read-only; never touches the tree.
"""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
PACKAGE = ROOT / "src/human_fall_detection"
R3_MANIFEST = json.loads(
    (ROOT / "docs/human_fall/evidence/2026-10-02_gl03_r3/22_source_manifest.json")
    .read_text(encoding="utf-8"))
SUFFIXES = (".py", ".yaml", ".xml", ".sh", ".launch")


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git(*args):
    return subprocess.run(("git",) + args, cwd=str(ROOT),
                          capture_output=True, text=True).stdout.strip()


manifest = {}
for path in sorted(PACKAGE.rglob("*")):
    if path.is_file() and path.suffix in SUFFIXES and "__pycache__" not in path.parts:
        manifest[str(path.relative_to(ROOT)).replace("\\", "/")] = sha256(path)

r3_cross_check = {}
for entry in R3_MANIFEST.get("changed", []):
    relative = entry["path"]
    current = manifest.get(relative)
    r3_cross_check[relative] = {
        "r3_sha256": entry["sha256"],
        "r4_start_sha256": current,
        "matches": current == entry["sha256"],
    }

result = {
    "round": "GL-03 R4 / 2026-10-02",
    "branch": git("branch", "--show-current"),
    "head": git("rev-parse", "HEAD"),
    "status_porcelain": git("status", "--porcelain=v1").splitlines(),
    "source_files": len(manifest),
    "r3_manifest_cross_check": r3_cross_check,
}
(HERE / "00_before_manifest.json").write_text(
    json.dumps(manifest, indent=1, sort_keys=True), encoding="utf-8")
print(json.dumps(result, indent=1, sort_keys=True))
sys.exit(0 if all(item["matches"] for item in r3_cross_check.values()) else 1)
