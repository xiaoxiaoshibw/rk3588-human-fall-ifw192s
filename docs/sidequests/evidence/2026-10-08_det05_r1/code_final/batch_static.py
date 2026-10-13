"""Four user-selected static sessions: existing offline leveling, then full-frame CPU trial."""
import argparse
import json
from pathlib import Path
import sys
import time

import numpy as np
import torch

from experiment import adapt, read_frame, sha
from cpu_pointpillars import load_model

SESSIONS = ["cap_20261007_215540", "cap_20261007_215607", "cap_20261007_215623", "cap_20261007_215643"]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--data-root", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--intensity-divisor", type=float, default=1023)
    a = p.parse_args()
    a.out.mkdir(parents=True, exist_ok=False)
    repo = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(repo / "pc_apps/human_replay"))
    import leveling
    torch.set_num_threads(4)
    upstream = Path(__file__).resolve().parent / "artifacts/upstream"
    model = load_model(upstream / "epoch_160.pth", upstream)
    summary = []
    for sid in SESSIONS:
        print("BEGIN", sid, flush=True)
        directory, meta, binding = leveling.source(a.data_root, sid)
        # Existing nominal values are only a floor search seed/reference, not physical calibration.
        request = leveling.validate_request(dict(schema=1,sid=sid,source=binding,
            config=dict(mode="auto",pitch_deg=26,roll_deg=0,physical_height_m=1.1)))
        try:
            report, artifacts = leveling.run_job(a.data_root,a.out/"leveling",request,sid,
                                                lambda s:print(sid,s,flush=True))
            if not report["estimators"]["tls"]["valid"]:
                raise ValueError("TLS did not pass existing leveling quality gates")
            transform_path = a.out/"leveling"/sid/"tls/transform.json"
            transform = json.loads(transform_path.read_text(encoding="utf-8"))
            if transform["source"] != binding:
                raise ValueError("source binding changed")
            records = []
            for index, frame in enumerate(meta["frames"]):
                points, _ = read_frame(directory,index)
                pts = adapt(points,transform,-1.73,a.intensity_divisor)
                low = np.array([0,-39.68,-3]); high=np.array([69.12,39.68,1])
                in_range = ((pts[:,:3]>=low)&(pts[:,:3]<high)).all(axis=1)
                begin=time.perf_counter()
                with torch.inference_mode():
                    result=model([torch.from_numpy(pts)],mode="test")[0]
                detections=[] if not isinstance(result,dict) else [dict(source="model",
                    label=["Pedestrian","Cyclist","Car"][int(l)],score=float(s),
                    box_xyz_bottom_wlh_yaw=b.tolist()) for b,l,s in zip(result["lidar_bboxes"],result["labels"],result["scores"])]
                persons=[d for d in detections if d["label"]=="Pedestrian"]
                row=dict(index=index,seq=frame["seq"],source_points=len(points),input_points=len(pts),
                         dropped_zero_xyz=len(points)-len(pts),in_model_range=int(in_range.sum()),
                         seconds=time.perf_counter()-begin,detections=detections)
                records.append(row)
                if index%10==0:
                    print(sid,"frame",index,"persons",len(persons),"max",max([d["score"] for d in persons],default=0),flush=True)
            if leveling.source(a.data_root,sid)[2]!=binding:
                raise ValueError("source modified during trial")
            result=dict(session=sid,model="PointPillars / zhulf0804",source="model",source_hashes=binding,
                        transform_sha256=sha(transform_path),model_z=-1.73,intensity_divisor=a.intensity_divisor,
                        checkpoint_sha256=sha(upstream/"epoch_160.pth"),device="cpu",threads=4,
                        physical_verified=False,accuracy_status="NOT_RUN: no human boxes",frames=records)
            (a.out/(sid+"_predictions.json")).write_text(json.dumps(result,indent=2),encoding="utf-8")
            person_scores=[d["score"] for r in records for d in r["detections"] if d["label"]=="Pedestrian"]
            summary.append(dict(session=sid,status="PASS: inference only",frames=len(records),
                point_bytes=(directory/"points.bin").stat().st_size,
                pitch_deg=transform["pitch_deg"],roll_deg=transform["roll_deg"],tz_m=transform["observed_tz_m"],
                leveling_recommended=report.get("recommended"),tls_valid=True,
                pedestrian_candidates=len(person_scores),pedestrian_ge_03=sum(s>=.3 for s in person_scores),
                pedestrian_ge_05=sum(s>=.5 for s in person_scores),max_person_score=max(person_scores,default=0),
                mean_seconds=float(np.mean([r["seconds"] for r in records]))))
        except Exception:
            import traceback
            error=traceback.format_exc()
            (a.out/(sid+"_BLOCKED.txt")).write_text(error,encoding="utf-8")
            summary.append(dict(session=sid,status="BLOCKED",error=error))
            print(error,flush=True)
        (a.out/"summary.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
        print("END",sid,flush=True)


if __name__=="__main__":
    main()
