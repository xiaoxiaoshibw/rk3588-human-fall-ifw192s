"""DET-02 five fixed-input variants, all human frames; cached data never changes model settings."""
import argparse
import json
from pathlib import Path
import time

import numpy as np
import torch
from cpu_pointpillars import load_model
from experiment import sha
from audit_truth import covers_xy

VARIANTS=["A_full","B_workspace","C_reference","D_registered","E_cleanup"]


def region_count(cloud,xy):
    mask=np.sum((cloud[:,:2]-xy)**2,axis=1)<=.55**2
    mask&=(cloud[:,2]>=.05)&(cloud[:,2]<=2.30)
    return dict(total=int(mask.sum()),upper=int((mask&(cloud[:,2]>=1.5)).sum()),
                top=float(cloud[mask,2].max()) if mask.any() else None)


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--prepared",type=Path,required=True)
    p.add_argument("--foreground",type=Path,required=True)
    p.add_argument("--truth",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False)
    mf=json.loads((a.foreground/"manifest.json").read_text(encoding="utf-8"))
    rawmf=json.loads((a.prepared/"manifest.json").read_text(encoding="utf-8"))
    if mf["input_manifest_sha256"]!=sha(a.prepared/"manifest.json"):raise ValueError("prepared manifest changed")
    truth={s["session"]:s for s in json.loads(a.truth.read_text(encoding="utf-8"))["sessions"]}
    root=Path(__file__).resolve().parent;upstream=root/"artifacts/upstream"
    model=load_model(upstream/"epoch_160.pth",upstream);torch.set_num_threads(4)
    for v in VARIANTS:(a.out/v).mkdir()
    summary=[]
    for session in mf["sessions"]:
        sid=session["sid"];seed=truth[sid]["xy_m"]
        rawsession=next(s for s in rawmf["sessions"] if s["sid"]==sid)
        results={v:[] for v in VARIANTS}
        print("BEGIN",sid,flush=True)
        for f in session["frames"]:
            raw=np.fromfile(a.prepared/sid/rawsession["frames"][f["index"]]["file"],dtype="<f4").reshape(-1,4)
            for variant in VARIANTS:
                record=f["variants"][variant];file=a.foreground/sid/record["file"]
                if sha(file)!=record["sha256"] or sha(Path(str(file)+".ids"))!=record["ids_sha256"]:
                    raise ValueError("foreground input changed")
                cloud=np.fromfile(file,dtype="<f4").reshape(-1,4)
                ids=np.fromfile(str(file)+".ids",dtype="<u4")
                if not np.array_equal(cloud,raw[ids]):raise ValueError("source coordinate/intensity identity lost")
                model_input=cloud.copy();model_input[:,2]-=np.float32(1.73);model_input[:,3]/=np.float32(1023)
                begin=time.perf_counter();detections=[]
                inside_range=((model_input[:,:3]>=np.array([0,-39.68,-3]))&
                              (model_input[:,:3]<np.array([69.12,39.68,1]))).all(axis=1)
                if inside_range.any():
                    with torch.inference_mode():pred=model([torch.from_numpy(model_input)],mode="test")[0]
                    if isinstance(pred,dict):
                        detections=[dict(source="model",label=["Pedestrian","Cyclist","Car"][int(l)],score=float(s),
                            box_xyz_bottom_wlh_yaw=b.tolist()) for b,l,s in zip(pred["lidar_bboxes"],pred["labels"],pred["scores"])]
                persons=[d for d in detections if d["label"]=="Pedestrian"]
                hits=[d for d in persons if covers_xy(d["box_xyz_bottom_wlh_yaw"],seed)]
                results[variant].append(dict(index=f["index"],seq=f["seq"],seconds=time.perf_counter()-begin,
                    input_points=len(cloud),input_sha256=record["sha256"],source_ids_sha256=record["ids_sha256"],
                    region=region_count(cloud,seed),target_max_score=max([d["score"] for d in hits],default=0),
                    target_location_covered=bool(hits),detections=detections))
            if f["index"]%10==0:print(sid,"frame",f["index"],{v:round(results[v][-1]["target_max_score"],3) for v in VARIANTS},flush=True)
        for variant,frames in results.items():
            (a.out/variant/(sid+"_predictions.json")).write_text(json.dumps(dict(session=sid,variant=variant,source="model",
                source_hashes=session["source"],transform_sha256=session["transform_sha256"],model_z=-1.73,
                intensity_divisor=1023,checkpoint_sha256=sha(upstream/"epoch_160.pth"),template_sha256=mf["template_sha256"],
                registration_gate=session["registration_gate"],formal_production_eligible=False,
                accuracy_status="NOT_RUN: approximate user location seeds, not exact 3D boxes",frames=frames),indent=2),encoding="utf-8")
            scores=[f["target_max_score"] for f in frames]
            summary.append(dict(session=sid,variant=variant,frames=len(frames),
                target_location_covered_frames=sum(f["target_location_covered"] for f in frames),
                target_max_score=max(scores,default=0),target_ge_03_frames=sum(s>=.3 for s in scores),
                target_ge_05_frames=sum(s>=.5 for s in scores),
                median_input_points=float(np.median([f["input_points"] for f in frames])),
                median_region_points=float(np.median([f["region"]["total"] for f in frames])),
                median_upper_region_points=float(np.median([f["region"]["upper"] for f in frames])),
                mean_seconds=float(np.mean([f["seconds"] for f in frames]))))
        (a.out/"summary.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
        print("END",sid,flush=True)


if __name__=="__main__":main()
