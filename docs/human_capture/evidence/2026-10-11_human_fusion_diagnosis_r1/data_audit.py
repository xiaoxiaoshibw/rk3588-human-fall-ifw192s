"""Audit current GT and selected raw rows; no classifier or annotation mutations."""
import collections
import hashlib
import json
import sys
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "pc_apps/human_ml"))
from frozen_gt import audit_session, decode_indices, SIDS, R, T
from audit_fusion_sessions import EXPECTED

def save(name, data):
    with (OUT / name).open("x", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, allow_nan=False)

def quant(values):
    return dict(zip(("min", "p10", "median", "p90", "max"), np.percentile(values, [0,10,50,90,100]).tolist())) if values else None

def main():
    rows, geometry = [], []
    for sid, name, expected in EXPECTED:
        rec, doc, meta = audit_session(sid, ROOT / "pc_apps/human_replay/gt_store", ROOT / "captures/remote")
        raw = np.memmap(ROOT / "captures/remote" / sid / "points.bin", dtype="<f4", mode="r").reshape(-1, 7)
        end = 0
        for f in meta["frames"]:
            assert f["offset_points"] == end
            end += f["count_points"]
        assert end == meta["total_points"] == len(raw) and len(meta["frames"]) == expected
        times = [f["bag_time_sec"] for f in meta["frames"]]
        rec.update(activity=name, duration_s=times[-1]-times[0], median_dt_s=float(np.median(np.diff(times))),
                   source_by_class={}, manual_frames=[], propagated_frames=[], person_geometry_summary={}, stricter_index_issues=[])
        sourcecounts = collections.Counter()
        for fi_s, ids in doc["frames_objects"].items():
            fi = int(fi_s)
            f = meta["frames"][fi]
            seg = raw[f["offset_points"]:f["offset_points"]+f["count_points"], :4]
            valid = np.isfinite(seg[:,:3]).all(axis=1) & np.any(seg[:,:3] != 0, axis=1)
            compact_to_raw = np.flatnonzero(valid)
            src = set()
            for oid in ids:
                o = doc["objects"][oid]
                sourcecounts[(o["class_name"], o.get("source", "UNKNOWN"))] += 1
                src.add(o.get("source"))
                idx = decode_indices(o["raw_point_indices"])
                if len(idx) != o["point_count"] or idx.max() >= len(compact_to_raw):
                    rec["stricter_index_issues"].append(oid)
                    continue
                if rec["eligible"] and o["class_name"] == "PERSON":
                    xyz = seg[compact_to_raw[idx], :3].astype(float)
                    lv = xyz @ R.T + T
                    zlo, zhi = np.percentile(lv[:,2], [5,95])
                    geometry.append({"sid":sid,"frame":fi,"object":oid,"source":o.get("source"),"track_id":o.get("track_id"),
                        "point_count":len(idx),"unique_xyz":int(len(np.unique(xyz,axis=0))),"compact_raw_diff_count":int((idx!=compact_to_raw[idx]).sum()),
                        "sensor_range_median":float(np.median(np.linalg.norm(xyz,axis=1))),"height_p90_m":float(zhi-zlo),
                        "z_p05":float(zlo),"z_p95":float(zhi),"xy_span_p90_m":(np.percentile(lv[:,:2],95,axis=0)-np.percentile(lv[:,:2],5,axis=0)).tolist(),
                        "occupied_5cm_voxels":int(len(np.unique(np.floor(lv/.05),axis=0))),
                        "within_z_01_23":int(((lv[:,2]>.1)&(lv[:,2]<2.3)).sum())})
            if "human" in src: rec["manual_frames"].append(fi)
            if "propagated" in src: rec["propagated_frames"].append(fi)
        rec["source_by_class"] = {c:{s:n for (cc,s),n in sourcecounts.items() if cc==c} for c in sorted({c for c,s in sourcecounts})}
        gs = [g for g in geometry if g["sid"] == sid]
        rec["person_geometry_summary"] = {k:quant([g[k] for g in gs]) for k in ("point_count","height_p90_m","sensor_range_median","occupied_5cm_voxels")}
        rec["annotated_fraction"] = rec["annotated_frames"]/rec["total_frames"] if rec["eligible"] else 0
        rows.append(rec)
        print(name, "eligible=", rec["eligible"], "frames=", rec["annotated_frames"], "sources=", rec["source_by_class"], flush=True)
    totals={"frames":sum(r["total_frames"] for r in rows),"qualified_annotated_frames":sum(r["annotated_frames"] for r in rows if r["eligible"]),
            "qualified_manual_frames":sum(len(r["manual_frames"]) for r in rows if r["eligible"]),"person_observations":len(geometry),
            "qualified_person_manual_observations":sum(g["source"]=="human" for g in geometry),
            "qualified_person_propagated_observations":sum(g["source"]=="propagated" for g in geometry)}
    save("data_audit.json", {"sessions":rows,"totals":totals,"limits":"reviewed is a provenance claim, not independent human accuracy; indices are compact despite field name; no unlabelled negatives"})
    save("person_geometry.json", geometry)
    # Count actual training rows and held-out negative coverage, without refitting any model.
    a=json.loads((ROOT/"sidequests/human_fusion_lab/results/AUDIT.json").read_text(encoding="utf-8"))
    candidates={}
    for split,sids in a["splits"].items():
        stats=collections.Counter(); allrows=[]
        for sid in sids:
            p=ROOT/"sidequests/human_fusion_lab/results"/(sid+".jsonl")
            if not p.exists():continue
            with p.open(encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        r=json.loads(line);stats["positive" if r["label"]==1 else "negative" if r["label"]==0 else "UNKNOWN"]+=1
                        if r["label"] is not None:allrows.append(r)
        candidates[split]={"counts":dict(stats),"positive_point_count":quant([r["point_count"] for r in allrows if r["label"]==1]),
                           "negative_point_count":quant([r["point_count"] for r in allrows if r["label"]==0])}
    save("candidate_data_audit.json", {"splits":candidates,"fixed_threshold":a["threshold"],"holdout_status":a["holdout_status"]})
    print(json.dumps({"totals":totals,"candidate_splits":candidates}, ensure_ascii=False),flush=True)

if __name__ == "__main__":
    main()
