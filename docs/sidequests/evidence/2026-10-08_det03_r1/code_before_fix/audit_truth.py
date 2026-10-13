"""Match cached model boxes to user-supplied location seeds; not box-IoU or recall GT."""
import argparse
import json
import math
from pathlib import Path
import statistics

from experiment import sha


def covers_xy(box, xy):
    x,y,z,w,l,h,yaw=box
    if not all(math.isfinite(v) for v in box) or min(w,l,h)<=0:
        raise ValueError("invalid predicted box")
    dx,dy=xy[0]-x,xy[1]-y
    c,s=math.cos(yaw),math.sin(yaw)
    return abs(c*dx+s*dy)<=w/2 and abs(-s*dx+c*dy)<=l/2


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--results",type=Path)
    parser.add_argument("--truth",type=Path)
    parser.add_argument("--out",type=Path)
    parser.add_argument("--self-check",action="store_true")
    args=parser.parse_args()
    if args.self_check:
        box=[0,0,0,4,.2,2,0]
        assert covers_xy(box,[1,0]) and not covers_xy(box,[0,1])
        box[-1]=math.pi/2
        assert covers_xy(box,[0,1]) and not covers_xy(box,[1,0])
        try:
            covers_xy([0,0,0,-1,1,1,0],[0,0])
        except ValueError:pass
        else:raise AssertionError("negative box size accepted")
        print("PASS: rotated location containment / invalid size")
        return
    if any(v is None for v in [args.results,args.truth,args.out]):
        parser.error("--results --truth --out required")
    args.out.mkdir(parents=True,exist_ok=False)
    truth=json.loads(args.truth.read_text(encoding="utf-8"))
    summary=[]
    for seed in truth["sessions"]:
        sid=seed["session"]
        source_path=args.results/(sid+"_predictions.json")
        pred=json.loads(source_path.read_text(encoding="utf-8"))
        frames=[];all_scores=[];peak=None;tops=[]
        for frame in pred["frames"]:
            people=[d for d in frame["detections"] if d["label"]=="Pedestrian"]
            hits=[]
            for d in people:
                box=d["box_xyz_bottom_wlh_yaw"]
                if peak is None or d["score"]>peak["score"]:
                    peak=dict(index=frame["index"],score=d["score"],xy=box[:2],
                              seed_distance_m=math.dist(box[:2],seed["xy_m"]))
                if covers_xy(box,seed["xy_m"]):
                    # Inverse of model input z = leveled z + model_z.
                    bottom=box[2]-pred["model_z"]
                    hits.append(dict(score=d["score"],xy=box[:2],bottom_ground_m=bottom,
                                     top_ground_m=bottom+box[5],box_model=box))
            best=max(hits,key=lambda h:h["score"]) if hits else None
            if best:
                all_scores.append(best["score"]);tops.append(best["top_ground_m"])
            frames.append(dict(index=frame["index"],seq=frame["seq"],seed_xy=seed["xy_m"],
                               containing_boxes=hits,best=best))
        row=dict(session=sid,pose=seed["pose"],frames=len(frames),
                 frames_with_seed_inside_box=len(all_scores),
                 seed_max_score=max(all_scores,default=0),
                 seed_ge_03_frames=sum(s>=.3 for s in all_scores),
                 seed_ge_05_frames=sum(s>=.5 for s in all_scores),
                 matched_box_top_min_m=min(tops,default=None),
                 matched_box_top_median_m=statistics.median(tops) if tops else None,
                 matched_box_top_max_m=max(tops,default=None),
                 global_peak=peak,
                 prediction_sha256=sha(source_path),transform_sha256=pred["transform_sha256"])
        summary.append(row)
        (args.out/(sid+"_location_audit.json")).write_text(json.dumps(dict(summary=row,frames=frames),indent=2),encoding="utf-8")
    (args.out/"summary.json").write_text(json.dumps(dict(truth_sha256=sha(args.truth),
        criterion="provided XY point inside rotated predicted pedestrian footprint",
        limitation="Approximate user location seed, no exact per-frame 3D boxes; montage transform not independently verified; not precision/recall",
        sessions=summary),indent=2),encoding="utf-8")
    print(json.dumps(summary,indent=2))


if __name__=="__main__":main()
