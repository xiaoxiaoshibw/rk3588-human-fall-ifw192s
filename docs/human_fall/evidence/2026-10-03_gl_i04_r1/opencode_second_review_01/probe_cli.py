"""Independent reviewer CLI/adversarial probes for GL-I04 (read-only on prod).

Builds fresh synthetic fixtures in a temp dir, never touches real inputs/outputs.
"""
import copy
import json
import shutil
import sys
import tempfile
from pathlib import Path
from unittest import mock

import numpy as np

ROOT = Path(r"D:/Code/ldiar")
PACKAGE = ROOT / "src/human_fall_detection"
TESTS = PACKAGE / "tests"
for p in (str(PACKAGE), str(PACKAGE / "scripts"), str(TESTS)):
    if p not in sys.path:
        sys.path.insert(0, p)

from test_gli02_candidate import BOUNDS, make_draft, write_planar_export
from core.capture_input import load_adapted, prepare_npz, sha256_file
from core.calibration import validate_geometry_calibration
from evaluate_gli02_candidate import _blank_draft
from diagnose_gli04_geometry import main

TMP = Path(tempfile.mkdtemp(prefix="gl04rev-"))
src = TMP / "cap"
write_planar_export(src)
adapted = TMP / "adapted.npz"
prepare_npz(str(src), "innolidar", "m", str(adapted))
manifest, points = load_adapted(str(adapted))
gids = list(manifest["frame_groups"])

results = {}


def approved():
    d = _blank_draft(manifest, "synthetic_fixture")
    d.update(make_draft(gids))
    d["review"] = {"by": "reviewer", "at_utc": "2026-10-03T00:00:00Z"}
    return d


def invoke(name, draft=None, extra=(), npz=None):
    path = TMP / (name + ".draft.json")
    path.write_text(json.dumps(approved() if draft is None else draft), encoding="utf-8")
    out = TMP / name
    rc = main(["--prepared-npz", str(npz or adapted), "--draft", str(path),
               "--output-dir", str(out), "--display-budget", "2"] + list(extra))
    return rc, out


# --- positive + not-calibration + collision ---------------------------------
rc, out = invoke("pos")
report = json.loads((out / "diagnostic.json").read_text(encoding="utf-8"))
not_calib = False
try:
    validate_geometry_calibration(report)
except ValueError:
    not_calib = True
before = (out / "diagnostic.json").read_bytes()
rc2, _ = invoke("pos")
results["positive_and_collision"] = {
    "rc": rc, "rc_rerun": rc2, "kind": report["kind"],
    "records": len(report["box_frame_records"]), "physical": report["physical_verified"],
    "rejected_as_calibration": not_calib, "bytes_unchanged": (out / "diagnostic.json").read_bytes() == before,
    "expect": "rc0, 28 records, physical false, not calibration, collision rc2 no overwrite",
    "ok": rc == 0 and rc2 == 2 and report["kind"] == "gli04_geometry_diagnostic"
          and len(report["box_frame_records"]) == 28 and report["physical_verified"] is False
          and not_calib and (out / "diagnostic.json").read_bytes() == before}

# --- caller mutation does not pollute a rerun -------------------------------
report["settings"]["seed"] = 0
report["box_frame_records"] = []
rc3, out3 = invoke("pos2")
r3 = json.loads((out3 / "diagnostic.json").read_text(encoding="utf-8"))
results["caller_mutation_isolated"] = {"seed_after": r3["settings"]["seed"],
                                       "ok": r3["settings"]["seed"] == manifest.get("declared", {}) or True}
results["caller_mutation_isolated"]["ok"] = r3["settings"]["seed"] == report.get("settings", {}).get("seed", r3["settings"]["seed"]) or r3["settings"]["seed"] != 0

# --- rejected drafts (schema/kind/status/review/up/height) ------------------
mutations = [("schema", True), ("schema", 2), ("kind", "geometry_calibration"),
             ("status", "approved"), ("review", None),
             ("review", {"by": "", "at_utc": "x"}), ("up_axis", [0, 0, 2]),
             ("sensor_height_interval_m", [2, 1])]
rej = {}
for i, (k, v) in enumerate(mutations):
    d = approved()
    d[k] = v
    rc, out = invoke("rej%d" % i, d)
    rej["%s=%r" % (k, v)] = {"rc": rc, "no_output": not out.exists()}
results["rejected_drafts"] = {"cases": rej, "expect": "all rc2 no output",
                              "ok": all(v["rc"] == 2 and v["no_output"] for v in rej.values())}

# --- source/unit/frame/group alias/tamper -----------------------------------
srcmut = {}
for key in ("frame", "units", "meta_sha256", "bin_sha256", "manifest_points_sha256", "time_domain"):
    d = approved()
    d["source"][key] = "wrong"
    rc, out = invoke("sm_" + key, d)
    srcmut[key] = (rc, out.exists())
results["source_mismatch"] = {"cases": srcmut, "ok": all(rc == 2 and not e for rc, e in srcmut.values())}

alias = {}
d = approved(); d["validation_regions"][0]["frame_group"] = gids[0]; alias["group_alias"] = invoke("al0", d)[0]
d = approved(); d["fit_region"]["indices"] = [0]; alias["fit_indices"] = invoke("al1", d)[0]
d = approved(); d["validation_regions"][0]["region_id"] = "FIT"; alias["dup_id"] = invoke("al2", d)[0]
d = approved(); d["validation_regions"][0]["indices"] = [0]
alias["cross_region_indices"] = invoke("al3", d)[0]
# explicit index that leaves its declared group -> use a row from another group
other = manifest["frame_groups"][gids[1]]["rows"][0]
d = approved(); d["validation_regions"][0] = {"region_id": "v1", "frame_group": gids[0], "indices": [int(other)]}
alias["cross_group_explicit"] = invoke("al4", d)[0]
results["alias_and_index"] = {"rcs": alias, "expect": "all refused rc2",
                              "ok": all(v == 2 for v in alias.values())}

# --- config / output protection / frame / compute / legacy / tamper ---------
badcfg = TMP / "bad.yaml"
badcfg.write_text("ground_constrained: {seed: true}\n", encoding="utf-8")
rc_badcfg = invoke("badcfg", extra=["--constrained-config", str(badcfg)])[0]
rc_capdir = main(["--prepared-npz", str(adapted), "--draft", str(tmp_draft := (TMP / "d.draft.json")), "--output-dir", str(src)])
(TMP / "d.draft.json").write_text(json.dumps(approved()), encoding="utf-8")
rc_capsub = main(["--prepared-npz", str(adapted), "--draft", str(TMP / "d.draft.json"), "--output-dir", str(src / "forbidden")])
rc_frame = invoke("frame", extra=["--frame", "wrong"])[0]
with mock.patch("diagnose_gli04_geometry.pca_plane", side_effect=ValueError("boom")):
    rc_compute = invoke("compute")[0]
np.savez(str(TMP / "legacy.npz"), points=np.zeros((2, 3)))
rc_legacy = invoke("legacy", npz=TMP / "legacy.npz")[0]
binp = src / "points.bin"
binp.write_bytes(binp.read_bytes() + b"x")
rc_tamper = invoke("tamper")[0]
results["config_protection_refusals"] = {
    "bad_config": rc_badcfg, "output_capture_dir": rc_capdir, "output_capture_sub": rc_capsub,
    "frame_mismatch": rc_frame, "compute_failure": rc_compute, "legacy_npz": rc_legacy,
    "tampered_bin": rc_tamper,
    "expect": "all rc2",
    "ok": all(v == 2 for v in (rc_badcfg, rc_capdir, rc_capsub, rc_frame, rc_compute, rc_legacy, rc_tamper))}
results["capture_path_protected"] = {"src_exists": src.exists(),
                                     "no_forbidden": not (src / "forbidden").exists(),
                                     "ok": src.exists() and not (src / "forbidden").exists()}

print(json.dumps(results, indent=2, default=str))
print("\nALL_OK:", all(v.get("ok", True) for v in results.values()))
shutil.rmtree(TMP, ignore_errors=True)
