"""Choose XY cells from FIT frames only; freeze all heights in each final cell."""
import json
from pathlib import Path
import sys
import uuid
import numpy as np

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "pc_apps" / "human_replay"))
import leveling as W
from leveling_quality import rotation

evidence = Path(__file__).resolve().parent
remote = ROOT / "captures" / "remote"
outroot = ROOT / "captures" / "leveled"
jobs = {"cap_20261004_203349": "53f8deae343a4bc498fc240a145f8ba8",
        "cap_20261004_203135": "10a28e0607a24264aa60478bcc3c89c7"}
for sid, original_job in jobs.items():
    prior = json.loads((outroot / original_job / "report.json").read_text(encoding="utf-8"))
    directory, meta, binding = W.source(remote, sid)
    records = np.memmap(directory / "points.bin", dtype="u1", mode="r")
    xyz = np.ndarray((meta["total_points"], 3), dtype="<f4", buffer=records, strides=(28, 4))
    held = set(prior["holdout_ordinals"])
    normal = np.array(prior["estimators"]["ransac"]["normal_source"])
    offset = prior["estimators"]["ransac"]["offset_source_m"]
    points = np.concatenate([xyz[f["offset_points"]:f["offset_points"]+f["count_points"]].astype("f8")
                             for ordinal, f in enumerate(meta["frames"]) if ordinal not in held])
    points = points[np.isfinite(points).all(axis=1) & np.any(points != 0, axis=1)]
    display = points @ rotation(26, 0).T
    residual = np.abs(points @ normal + offset)
    cells = []
    # This broad XY search envelope is a declared scene prior, not a residual point crop.
    for ix in range(3, 14):
        for iy in range(-5, 3):
            bounds = [ix*.25, (ix+1)*.25, iy*.25, (iy+1)*.25]
            mask = (display[:,0] >= bounds[0]) & (display[:,0] < bounds[1]) & (display[:,1] >= bounds[2]) & (display[:,1] < bounds[3])
            r = residual[mask]
            if len(r) < 500:
                continue
            stats = {"count": len(r), "rms_m": float(np.sqrt(np.mean(r*r))),
                     "p95_m": float(np.percentile(r, 95)), "support_ratio": float(np.mean(r <= .05))}
            if stats["rms_m"] <= .02 and stats["p95_m"] <= .035 and stats["support_ratio"] >= .98:
                cells.append({"bounds": bounds, **stats})
    if len(cells) < 4:
        raise RuntimeError(sid + " has fewer than four clean FIT XY cells")
    selected = [min(cells, key=lambda c: (c["rms_m"], -c["count"]))]
    center = lambda c: np.array([(c["bounds"][0]+c["bounds"][1])/2, (c["bounds"][2]+c["bounds"][3])/2])
    while len(selected) < 4:
        remaining = [c for c in cells if c not in selected]
        selected.append(max(remaining, key=lambda c: (min(float(np.linalg.norm(center(c)-center(s))) for s in selected), -c["rms_m"])))
    selection = {"sid": sid, "basis_job": original_job, "basis_plane": "RANSAC from prior FIT domain, never holdouts",
                 "excluded_ordinals": sorted(held), "cell_m": .25, "envelope": [.75,3.5,-1.25,.75],
                 "all_heights_per_cell": True, "selection_gates": {"min_count": 500, "rms_max_m": .02, "p95_max_m": .035, "support_min": .98},
                 "candidate_cells": cells, "selected_cells": selected,
                 "validation_exposure": "holdouts previously used diagnostically; not unexposed physical truth"}
    W.dump(evidence / (sid + "_fit_roi_selection.json"), selection)
    config = {"pitch_deg":26., "roll_deg":0., "physical_height_m":1.14,
              "regions":[c["bounds"] for c in selected], "ground_confirmed":True,
              "basis":"离线FIT帧自动选择四个完整XY网格：以原FIT RANSAC作选区参考，排除3留出帧，选区内保留全高度；地面身份/物理高度未独立核验，既有失败及留帧曝光保持。"}
    request = W.validate_request({"schema":1, "sid":sid, "source":binding, "config":config})
    job_id = uuid.uuid4().hex
    print(sid, job_id, config["regions"], flush=True)
    report, artifacts = W.run_job(remote, outroot, request, job_id, lambda m: print(m, flush=True))
    summary = {"sid":sid, "job_id":job_id, "recommended":report["recommended"], "artifacts":list(artifacts),
               "methods":{n:{"valid":a["valid"], "reject_reasons":a["reject_reasons"], "full":a.get("full")} for n,a in report["estimators"].items()}}
    W.dump(evidence / (sid + "_refined_result.json"), summary)
    print(json.dumps(summary, ensure_ascii=False), flush=True)
