"""Independent adversarial probe for GL-I03 R1 (review only; writes only here/temp)."""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(r"D:\Code\ldiar")
PKG = ROOT / "src/human_fall_detection"
sys.path[:0] = [str(PKG), str(PKG / "scripts"), str(PKG / "tests")]

from test_gli02_candidate import make_draft, write_planar_export
from core.capture_input import load_adapted, prepare_npz

tmp = Path(tempfile.mkdtemp(prefix="gli03-review-"))
cap = tmp / "cap"
write_planar_export(cap)
adapted = tmp / "adapted.npz"
prepare_npz(str(cap), "innolidar", "m", str(adapted))
manifest, _ = load_adapted(str(adapted))
draft = tmp / "draft.json"
draft.write_text(json.dumps(make_draft(list(manifest["frame_groups"]))),
                 encoding="utf-8")

SCRIPT = PKG / "scripts/evaluate_gli02_candidate.py"
PY = sys.executable


def run_case(name, text):
    cfg = tmp / (name + ".yaml")
    cfg.write_text(text, encoding="utf-8")
    out = tmp / (name + ".json")
    cmd = [PY, "-B", "-W", "error", str(SCRIPT), "--prepared-npz", str(adapted),
           "--draft", str(draft), "--output", str(out),
           "--source-kind", "synthetic_fixture",
           "--constrained-config", str(cfg)]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    tail = proc.stderr.strip().splitlines()[-1] if proc.stderr.strip() else ""
    return {"name": name, "exit": proc.returncode, "candidate": out.exists(),
            "stderr_tail": tail}


cases = {
    "float_overflow_cell": "ground_constrained: {spatial_cell_m: " + "9" * 400 + "}",
    "int_overflow_cell": "ground_constrained: {max_points_per_cell: " + "9" * 400 + "}",
    "int_overflow_min_inliers": "ground_constrained: {min_inliers: " + "9" * 400 + "}",
    "int_overflow_seed": "ground_constrained: {seed: " + "9" * 400 + "}",
    "int_overflow_fit_cap": "ground_constrained: {fit_point_cap: " + "9" * 400 + "}",
    "int_overflow_holdout_cap": "ground_constrained: {holdout_point_cap: " + "9" * 400 + "}",
    "seed_float": "ground_constrained: {seed: 1.0}",
    "bool_int": "ground_constrained: {min_inliers: true}",
    "nan_int": "ground_constrained: {min_inliers: .nan}",
    "inf_ratio": "ground_constrained: {support_fraction_min: .inf}",
    "angle_ge_90": "ground_constrained: {max_angle_rad: 1.6}",
    "one_key_change": "ground_constrained: {min_inliers: 200}",
    "extra_toplevel_key": "ground_constrained: {min_inliers: 200}\nother: 1",
}
results = [run_case(name, text) for name, text in cases.items()]
print(json.dumps(results, indent=2))
