#!/usr/bin/env python3
"""GL-03 R7 final source/data manifest (written after all tests)."""
import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
FILES = [
    "docs/human_fall/GL03_ACCEPTANCE.md",
    "src/human_fall_detection/core/calibration.py",
    "src/human_fall_detection/core/node_runtime.py",
    "src/human_fall_detection/core/lidar_candidates.py",
    "src/human_fall_detection/tests/test_gl03_candidates_geometry.py",
    "docs/human_fall/evidence/2026-10-02_gl03_r6/codex_review_01/input_matrix_checks.py",
    "docs/human_fall/evidence/2026-10-02_gl03_r7/run_r7.py",
    "docs/human_fall/evidence/2026-10-02_gl03_r7/20_ast38_check.py",
    "docs/human_fall/evidence/2026-10-02_gl03_r7/21_scope_check.py",
    "docs/human_fall/evidence/2026-10-02_gl03_r7/23_make_diff.py",
    "docs/human_fall/evidence/2026-10-02_gl03_r7/24_o01_planes_ablation_r7.py",
]
DATA = [
    "docs/human_fall/evidence/2026-10-01_gl00_r1/14_current_sample.csv.tgz",
    "docs/human_fall/evidence/2026-10-01_gl00_r1/14_current_roi_points.csv",
    "docs/human_fall/evidence/2026-10-01_gl00_r1/14_current_planes.json",
]


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git(*args):
    return subprocess.run(("git",) + args, cwd=str(ROOT),
                          capture_output=True, text=True).stdout.strip()


result = {
    "round": "GL-03 R7 / 2026-10-02",
    "branch": git("branch", "--show-current"),
    "head": git("rev-parse", "HEAD"),
    "acceptance": {path: sha256(ROOT / path)
                   for path in FILES if path.endswith("GL03_ACCEPTANCE.md")},
    "sources": {path: sha256(ROOT / path) for path in FILES
                if path.endswith(".py")},
    "data": {path: sha256(ROOT / path) for path in DATA},
    "o01_evidence_applicability": {
        "r3_report": "docs/human_fall/evidence/2026-10-02_gl03_r3/21_o01_planes_ablation_r3.json",
        "r7_report": "docs/human_fall/evidence/2026-10-02_gl03_r7/24_o01_planes_ablation_r7.json",
        "depends_on": "src/human_fall_detection/core/lidar_candidates.py",
        "note": ("R7 changed calibration.py, the GL03 test file and a "
                 "coordinate-metadata safety read in lidar_candidates.py; "
                 "node_runtime.py keeps the R5 passed logic. Because the "
                 "lidar_candidates dependency SHA changed, the R3 O01 "
                 "ablation script was rerun into R7 (read-only inputs, R7 "
                 "output path) and its JSON is byte-identical (same SHA) to "
                 "the R3 report; candidate geometry/indices are unaffected."),
    },
    "not_modified_frozen": ("no config/default.yaml, geometry.yaml, "
                            "geometry_constrained.yaml, human_fall.yaml, "
                            "human_fall_prod.yaml, perception.yaml, driver, "
                            "webui, raw data, historical evidence"),
    "no_git_actions": "no commit/push/reset/checkout/clean",
}
(HERE / "22_source_manifest.json").write_text(
    json.dumps(result, indent=1, sort_keys=True), encoding="utf-8")
print(json.dumps(result, indent=1, sort_keys=True))
