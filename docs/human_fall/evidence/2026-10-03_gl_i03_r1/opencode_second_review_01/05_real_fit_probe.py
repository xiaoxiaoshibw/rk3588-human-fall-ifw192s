"""Independent reproduction of the real-审 single-group fit diagnostics."""
import json
import sys
from pathlib import Path

ROOT = Path(r"D:\Code\ldiar")
PKG = ROOT / "src/human_fall_detection"
sys.path[:0] = [str(PKG), str(PKG / "scripts")]

from core.capture_input import gate_selection, load_adapted
from core.ground import fit_ground_plane_constrained
from evaluate_gli02_candidate import _draft_region, _load_constrained_settings

real = ROOT / "docs/human_fall/evidence/2026-10-03_gl_i02_r1/08_real/real_candidate.adapted.npz"
draft_path = ROOT / "docs/human_fall/evidence/2026-10-03_gl_i02_r1/codex_review_01/work/filled_real_draft.json"
variant = PKG / "config/geometry_constrained_gli03_r1.yaml"

draft = json.loads(draft_path.read_text(encoding="utf-8"))
manifest, points = load_adapted(str(real))
fit = _draft_region(draft["fit_region"], "fit")
regions = []
for region in draft["validation_regions"]:
    item = _draft_region(region, "validation")
    item["region_id"] = region["region_id"]
    regions.append(item)
indices, validation = gate_selection(points, manifest, fit, None,
                                     fit["frame_group"], regions)
out = {}
for label, cfg in (("default", None), ("variant", str(variant))):
    result = fit_ground_plane_constrained(
        points, settings=_load_constrained_settings(cfg), frame="innolidar",
        up_axis=draft["up_axis"],
        sensor_height_interval_m=draft["sensor_height_interval_m"],
        fit_indices=indices, fit_frame_group=fit["frame_group"],
        validation_regions=validation)
    out[label] = {
        "status": result["status"], "valid": result["valid"],
        "reason": result["reason"], "fit_index_count": result["fit_index_count"],
        "sampled_fit_count": result["sampled_fit_count"],
        "degenerate_samples": result["degenerate_samples"],
        "complex_count": len(result.get("candidates", [])),
        "up_axis_gate_deg": result.get("roi_angle_deg"),
    }
print(json.dumps(out, indent=2))
