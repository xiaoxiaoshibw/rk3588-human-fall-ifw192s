# GL-I02 real 163621 read-only reload evidence.
# Runs the wrapper --emit-draft (prepare + load-adapted only, NO fit), then an
# independent load_adapted recount. The capture directory is never written; its
# two file digests must be identical before and after.
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import numpy as np

REPO = Path(os.getcwd())
PKG = REPO / "src" / "human_fall_detection"
WRAPPER = PKG / "scripts" / "evaluate_gli02_candidate.py"
CAP = REPO / "captures" / "remote" / "cap_20261002_163621"
EV = REPO / "docs" / "human_fall" / "evidence" / "2026-10-03_gl_i02_r1"
WORK = EV / "08_real"
WORK.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(PKG))
from core.capture_input import load_adapted

EXPECT_POINTS = 4372400
EXPECT_FRAMES = 89
EXPECT_GROUPS = 89
EXPECT_ZERO = 673315
CHECKS = []


def digest(path):
    h = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def check(name, ok, detail=""):
    CHECKS.append(ok)
    print("%-56s %s %s" % (name, "PASS" if ok else "FAIL", detail))


def main():
    meta_before = digest(CAP / "meta.json")
    bin_before = digest(CAP / "points.bin")
    listing_before = sorted(os.listdir(CAP))
    print("capture meta before: %s" % meta_before)
    print("capture bin  before: %s" % bin_before)

    output = WORK / "real_candidate.json"
    template = WORK / "real_draft.json"
    completed = subprocess.run(
        [sys.executable, str(WRAPPER), "--capture-dir", str(CAP),
         "--frame", "innolidar", "--units", "m", "--output", str(output),
         "--emit-draft", "--draft-out", str(template),
         "--source-kind", "capture_export"], capture_output=True, text=True)
    print("$ wrapper --emit-draft rc=%d stdout=%s stderr=%s" %
          (completed.returncode, completed.stdout.strip(), completed.stderr.strip()))
    check("real prepare+emit-draft exit 0 (no fit)", completed.returncode == 0)

    adapted = WORK / "real_candidate.adapted.npz"
    manifest, points = load_adapted(str(adapted))
    total = int(manifest["points"]["shape"][0])
    frames = len(manifest.get("frames") or [])
    groups = len(manifest.get("frame_groups") or {})
    zero_rows = int(np.count_nonzero(np.all(points == 0, axis=1)))
    print("points=%d frames=%d groups=%d zero_rows=%d" %
          (total, frames, groups, zero_rows))
    check("points == 4372400", total == EXPECT_POINTS, str(total))
    check("frames == 89", frames == EXPECT_FRAMES, str(frames))
    check("frame_groups == 89", groups == EXPECT_GROUPS, str(groups))
    check("zero_rows == 673315", zero_rows == EXPECT_ZERO, str(zero_rows))

    draft = json.loads(template.read_text(encoding="utf-8"))
    check("draft frame_scope total_points 4372400",
          draft["frame_scope"]["total_points"] == EXPECT_POINTS)
    check("draft frame_scope frames 89",
          draft["frame_scope"]["frames"] == EXPECT_FRAMES)
    check("draft frame_scope 89 groups",
          len(draft["frame_scope"]["frame_groups"]) == EXPECT_GROUPS)
    check("draft status pending_human_review",
          draft["status"] == "pending_human_review")

    meta_after = digest(CAP / "meta.json")
    bin_after = digest(CAP / "points.bin")
    check("capture meta.json unchanged", meta_after == meta_before, meta_after)
    check("capture points.bin unchanged", bin_after == bin_before, bin_after)
    check("capture dir has no new file",
          sorted(os.listdir(CAP)) == listing_before)

    passed = sum(1 for ok in CHECKS if ok)
    print("real checks: %d/%d" % (passed, len(CHECKS)))
    return 0 if passed == len(CHECKS) else 1


if __name__ == "__main__":
    sys.exit(main())
