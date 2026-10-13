"""Bind and level a confirmed empty template and four human sessions; original captures are read-only."""
import argparse
import json
from pathlib import Path
import sys

import numpy as np
from experiment import adapt, read_frame, sha
from batch_static import SESSIONS


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--data-root",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--empty-template-confirmed",action="store_true",required=True)
    a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False)
    repo=Path(__file__).resolve().parents[2];sys.path.insert(0,str(repo/"pc_apps/human_replay"))
    import leveling
    records=[]
    for sid in ["cap_20261007_233658"]+SESSIONS:
        directory,meta,binding=leveling.source(a.data_root,sid)
        print("BEGIN",sid,flush=True)
        previous=Path(__file__).resolve().parent/"artifacts/static_four_r2/leveling"/sid
        reuse=False
        if (previous/"tls/transform.json").is_file():
            report=json.loads((previous/"report.json").read_text(encoding="utf-8"))
            manifest=json.loads((previous/"manifest.json").read_text(encoding="utf-8"))
            tf=previous/"tls/transform.json"
            reuse=report["source"]==binding and manifest["report_sha256"]==sha(previous/"report.json") and manifest["artifacts"]["tls"]["transform.json"]==sha(tf)
        if not reuse:
            req=leveling.validate_request(dict(schema=1,sid=sid,source=binding,
                config=dict(mode="auto",pitch_deg=26,roll_deg=0,physical_height_m=1.1)))
            report,_=leveling.run_job(a.data_root,a.out/"leveling",req,sid,lambda msg:print(sid,msg,flush=True))
            tf=a.out/"leveling"/sid/"tls/transform.json"
        if not report["estimators"]["tls"]["valid"]:
            raise ValueError("TLS quality failed: "+sid)
        transform=json.loads(tf.read_text(encoding="utf-8"))
        if transform["source"]!=binding:raise ValueError("transform source changed")
        target=a.out/sid;target.mkdir()
        frames=[]
        for index,f in enumerate(meta["frames"]):
            points,_=read_frame(directory,index)
            valid=np.any(points[:,:3]!=0,axis=1)
            cloud=adapt(points,transform,0,1)
            name="frame_%06d.bin"%index
            cloud.astype("<f4").tofile(target/name)
            rows=np.flatnonzero(valid).astype("<i8")+f["offset_points"]
            rows.tofile(target/(name+".rows"))
            frames.append(dict(index=index,seq=f["seq"],file=name,points=len(cloud),
                source_points=len(points),sha256=sha(target/name),rows_sha256=sha(target/(name+".rows"))))
        if leveling.source(a.data_root,sid)[2]!=binding:raise ValueError("input changed during preparation")
        records.append(dict(sid=sid,role="empty_reference" if sid.endswith("233658") else "human_target",
            source=binding,raw_directory=str(directory),transform_path=str(tf.resolve()),transform_sha256=sha(tf),
            leveling_reused=reuse,leveling_recommended=report.get("recommended"),tls_valid=True,
            R=transform["R"],t=transform["t"],physical_verified=False,frames=frames))
        print("END",sid,"frames",len(frames),"reused",reuse,flush=True)
    (a.out/"manifest.json").write_text(json.dumps(dict(empty_template_confirmed=True,
        user_confirmation="unoccupied, person has left",sessions=records),indent=2),encoding="utf-8")


if __name__=="__main__":main()
