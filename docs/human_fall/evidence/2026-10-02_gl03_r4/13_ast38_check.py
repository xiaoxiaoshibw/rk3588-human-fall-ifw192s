#!/usr/bin/env python3
"""Python 3.8 grammar check for the R4-touched files (board target)."""
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
FILES = [
    "src/human_fall_detection/core/calibration.py",
    "src/human_fall_detection/core/node_runtime.py",
    "src/human_fall_detection/core/lidar_candidates.py",
    "src/human_fall_detection/tests/test_gl03_candidates_geometry.py",
    "docs/human_fall/evidence/2026-10-02_gl03_r4/06_r4_checks.py",
]
for relative in FILES:
    source = (ROOT / relative).read_text(encoding="utf-8")
    ast.parse(source, filename=relative, feature_version=(3, 8))
    print("py38 AST ok:", relative)
