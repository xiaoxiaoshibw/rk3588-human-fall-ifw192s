"""Choose one shared planar domain from FIT only; never read holdout outcomes."""
import argparse
import copy
import itertools
from pathlib import Path

import numpy as np
import run as E
from floor_sheet import _roi_metrics
from leveling_estimators import ESTIMATORS
from leveling_quality import statistics


def rank_candidates(keys, data):
    candidates = []
    for combo in itertools.combinations(keys, 4):
        geometry = _roi_metrics([{"key": key} for key in combo])
        if not geometry["ok"]:
            continue
        rows, scores = {}, []
        for sid, cells in zip(E.SESSIONS, data):
            normal, offset = ESTIMATORS["tls"](np.concatenate([cells[key] for key in combo]))
            measures = [statistics(cells[key], normal, offset) for key in combo]
            rows[sid] = measures
            scores.extend(m["rms_m"] for m in measures)
        candidates.append({"keys": combo, "worst_fit_region_rms_m": max(scores),
                           "fit_regions": rows, "fit_quality_pass": all(
                               m["status"] == "PASS" for measures in rows.values() for m in measures)})
    eligible = [c for c in candidates if c["fit_quality_pass"]]
    winner = min(eligible, key=lambda c: (c["worst_fit_region_rms_m"], c["keys"])) if eligible else None
    return candidates, eligible, winner


def select(discovery_path, out):
    out.mkdir()
    discovery = E.read(discovery_path)
    keys = sorted(tuple(k) for k in discovery["shared_keys"])
    data = []
    reports = E.original_reports()
    for sid, report in zip(E.SESSIONS, reports):
        directory, meta, binding = E.leveling.source(E.ROOT / "captures/remote", sid)
        if binding != discovery[sid]["source"]:
            raise ValueError("Source changed since common-cell discovery")
        records = np.memmap(directory / "points.bin", dtype="u1", mode="r")
        xyz = np.ndarray((meta["total_points"], 3), dtype="<f4", buffer=records, strides=(28, 4))
        cells = {key: [] for key in keys}
        initial = E.rotation(report["config"]["pitch_deg"], report["config"]["roll_deg"])
        held = set(discovery[sid]["excluded_holdout_ordinals"])
        for ordinal, frame in enumerate(meta["frames"]):
            if ordinal in held:
                continue
            points = xyz[frame["offset_points"]:frame["offset_points"] + frame["count_points"]].astype("f8")
            good = np.isfinite(points).all(axis=1) & np.any(points != 0, axis=1) & (np.abs(points) <= 100).all(axis=1)
            points = points[good]
            cell_ids = np.floor((points @ initial.T)[:, :2] / .25).astype("i4")
            for key in keys:
                cells[key].append(points[np.all(cell_ids == key, axis=1)])
        data.append({key: np.concatenate(chunks) for key, chunks in cells.items()})
    candidates, eligible, winner = rank_candidates(keys, data)
    E.dump(out / "FIT_SELECTION.json", {"type": "FIT_ONLY_NOT_HUMAN_GT", "discovery": str(discovery_path),
        "discovery_sha256": E.leveling.sha(discovery_path), "candidates": candidates, "winner": winner,
        "policy": "unchanged cell/spread/quality gates; minimise worst FIT regional TLS RMS; holdouts not read"})
    if winner:
        config = copy.deepcopy(E.plan(reports)["original_patches"][0])
        config.update(regions=[[x*.25,(x+1)*.25,y*.25,(y+1)*.25] for x,y in winner["keys"]],
            mode="fit_only_common_planar_selection",
            basis="Shared clean cells, minimax FIT regional TLS RMS; no holdout tuning; physical identity UNKNOWN")
        E.dump(out / "CONFIG.json", {"shared_planar_fit_only": [copy.deepcopy(config), copy.deepcopy(config)]})
    print("FEASIBLE_GEOMETRY",len(candidates),"FIT_QUALITY_PASS",len(eligible),"WINNER",winner and winner["keys"],flush=True)


if __name__ == "__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--discovery",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    args=p.parse_args()
    select(args.discovery.resolve(),args.out.resolve())
