# GL-I02 negative cases (N02/N03/N06/N07) + SHA invariants (N05/J06).
# Reuses the synthetic adapted NPZ + filled draft from the 07 evidence run.
# Nothing here writes production sources or the capture directory.
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np

REPO = Path(os.getcwd())
PKG = REPO / "src" / "human_fall_detection"
WRAPPER = PKG / "scripts" / "evaluate_gli02_candidate.py"
EV = REPO / "docs" / "human_fall" / "evidence" / "2026-10-03_gl_i02_r1"
SYN = EV / "07_synthetic"
ADAPTED = SYN / "candidate.adapted.npz"
DRAFT = SYN / "draft_filled.json"
CAP = REPO / "captures" / "remote" / "cap_20261002_163621"

EXPECTED_SHA = {
    "src/human_fall_detection/core/capture_input.py":
        "56355e9594433d91c871685f58c6ae9f8fe0e47d2b3ad7d07f9b5b8050b85f16",
    "src/human_fall_detection/scripts/prepare_capture_input.py":
        "648a8da63a6656b02d169957cede2df4aca3a48e94dcc787c3c48c7f10c5d000",
    "src/human_fall_detection/scripts/calibrate_sensors.py":
        "3f30cf945d70b06f0fce22bdec9ba738f774f98dde2f9a33ce466eeaf9c6c785",
    "src/human_fall_detection/tests/test_gli01_capture_input.py":
        "50f615d7a5ffdc490f1011b316df30da1e65c958cce93f18ad4cf0c88547030e",
    "src/human_fall_detection/core/ground.py":
        "2d25ccfd9b41b4e16b36c07eec5b243ac50a63bf15230445d942e0f1bcebc4d3",
    "src/human_fall_detection/core/calibration.py":
        "d29519a1cdb5e495d23115bc89886e9071e4f2055ff529285e933cebdb7c58a3",
}
EXPECTED_CAPTURE = {
    "captures/remote/cap_20261002_163621/meta.json":
        "675c23ded9dcee82e6e985f17665469a487d34520408582708601eb188b1d692",
    "captures/remote/cap_20261002_163621/points.bin":
        "b81797f9825792655e5930edeb39c15275eb64e01999984884da61d252c599ff",
}
CHECKS = []


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def check(name, ok, detail=""):
    CHECKS.append(ok)
    print("%-56s %s %s" % (name, "PASS" if ok else "FAIL", detail))


def run(args):
    completed = subprocess.run([sys.executable, str(WRAPPER)] + args,
                               capture_output=True, text=True)
    print("$ %s\n  rc=%d stderr=%s" % (" ".join(args), completed.returncode,
                                       completed.stderr.strip()))
    return completed.returncode


def main():
    work = Path(tempfile.mkdtemp(prefix="gli02-neg-"))

    # N02: missing up_axis -> exit 2, no artifact.
    draft = json.loads(DRAFT.read_text(encoding="utf-8"))
    draft["up_axis"] = None
    bad = work / "draft_no_axis.json"
    bad.write_text(json.dumps(draft), encoding="utf-8")
    out = work / "n02.json"
    rc = run(["--prepared-npz", str(ADAPTED), "--draft", str(bad),
              "--output", str(out)])
    check("N02 missing up_axis exit 2", rc == 2, "rc=%d" % rc)
    check("N02 no artifact", not out.exists())

    # N03: same-name artifact exists -> exclusive refusal, old content kept.
    out3 = work / "n03.json"
    rc1 = run(["--prepared-npz", str(ADAPTED), "--draft", str(DRAFT),
               "--output", str(out3)])
    before = out3.read_bytes() if out3.exists() else b""
    rc2 = run(["--prepared-npz", str(ADAPTED), "--draft", str(DRAFT),
               "--output", str(out3)])
    check("N03 first candidate exit 0", rc1 == 0, "rc=%d" % rc1)
    check("N03 existing target exit 2", rc2 == 2, "rc=%d" % rc2)
    check("N03 old artifact preserved", out3.read_bytes() == before)

    # N06: legacy NPY/NPZ -> exit 2; damaged adapted -> exit 2 (no fallback).
    legacy = work / "legacy.npz"
    with open(legacy, "wb") as handle:
        np.savez(handle, points=np.zeros((3, 3), dtype="<f4"))
    out6 = work / "n06.json"
    rc = run(["--prepared-npz", str(legacy), "--draft", str(DRAFT),
              "--output", str(out6)])
    check("N06 legacy input exit 2", rc == 2, "rc=%d" % rc)
    check("N06 legacy no artifact", not out6.exists())

    with np.load(str(ADAPTED), allow_pickle=False) as loaded:
        points = loaded["points"]
        manifest = str(loaded["input_manifest"])
    damaged = work / "damaged.npz"
    with open(damaged, "wb") as handle:
        np.savez(handle, points=points, input_manifest=np.array(manifest),
                 extra=np.zeros(3))
    out6b = work / "n06b.json"
    rc = run(["--prepared-npz", str(damaged), "--draft", str(DRAFT),
              "--output", str(out6b)])
    check("N06 damaged adapted exit 2", rc == 2, "rc=%d" % rc)
    check("N06 damaged no artifact", not out6b.exists())

    # N07: emitted draft template fields.
    template = work / "template.json"
    rc = run(["--prepared-npz", str(ADAPTED), "--emit-draft",
              "--draft-out", str(template), "--output", str(work / "unused.json")])
    check("N07 emit-draft exit 0", rc == 0, "rc=%d" % rc)
    emitted = json.loads(template.read_text(encoding="utf-8"))
    check("N07 status pending_human_review",
          emitted["status"] == "pending_human_review")
    check("N07 default_refusal set",
          emitted["default_refusal"] == "no_auto_ground_selection")
    check("N07 required decision fields present",
          all(key in emitted for key in ("up_axis", "sensor_height_interval_m",
                                         "fit_region", "validation_regions")))
    rc = run(["--prepared-npz", str(ADAPTED), "--emit-draft",
              "--draft-out", str(template), "--output", str(work / "unused.json")])
    check("N07 draft exclusive (second emit exit 2)", rc == 2, "rc=%d" % rc)

    # N05 / J06: baseline SHAs unchanged (GL-I01 four + frozen + capture).
    for rel, expected in EXPECTED_SHA.items():
        actual = sha256(REPO / rel)
        check("SHA %s" % rel.split("/")[-1], actual == expected, actual[:16])
    for rel, expected in EXPECTED_CAPTURE.items():
        actual = sha256(REPO / rel)
        check("SHA %s" % Path(rel).name, actual == expected, actual[:16])
    check("captures/remote has no new file",
          sorted(os.listdir(CAP)) == ["meta.json", "points.bin"])

    passed = sum(1 for ok in CHECKS if ok)
    print("negative+sha checks: %d/%d" % (passed, len(CHECKS)))
    return 0 if passed == len(CHECKS) else 1


if __name__ == "__main__":
    sys.exit(main())
