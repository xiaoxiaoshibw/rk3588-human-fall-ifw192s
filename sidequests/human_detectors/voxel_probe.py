"""Diagnostic only: exact checkpoint-compatible first-seen max32 pillar sampling, no changes."""
import argparse
import json
from pathlib import Path

import numpy as np
import torch
from cpu_pointpillars import Voxelization


def summary(points,xy):
    p=points.copy();p[:,2]+=np.float32(1.73)
    valid=(np.sum((p[:,:2]-xy)**2,axis=1)<=.55**2)&(p[:,2]>=.05)&(p[:,2]<=2.30)
    local=p[valid]
    return dict(points=len(local),upper_ge_15=int((local[:,2]>=1.5).sum()),
        top_ground_m=float(local[:,2].max()) if len(local) else None)


p=argparse.ArgumentParser()
p.add_argument("--foreground",type=Path,required=True)
p.add_argument("--truth",type=Path,required=True)
p.add_argument("--out",type=Path,required=True)
a=p.parse_args()
mf=json.loads((a.foreground/"manifest.json").read_text(encoding="utf-8"))
truth={s["session"]:s for s in json.loads(a.truth.read_text(encoding="utf-8"))["sessions"]}
op=Voxelization([.16,.16,4],[0,-39.68,-3,69.12,39.68,1],32,(16000,40000)).eval()
rows=[]
for session in mf["sessions"]:
    sid=session["sid"];xy=truth[sid]["xy_m"];f=session["frames"][len(session["frames"])//2]
    for v in ["A_full","B_workspace","C_reference","D_registered","E_cleanup"]:
        pts=np.fromfile(a.foreground/sid/f["variants"][v]["file"],dtype="<f4").reshape(-1,4)
        pts[:,2]-=np.float32(1.73);pts[:,3]/=np.float32(1023)
        vox,coords,counts=op(torch.from_numpy(pts))
        selected=np.concatenate([arr[:n] for arr,n in zip(vox.numpy(),counts.numpy())])
        rows.append(dict(sid=sid,index=f["index"],variant=v,before=summary(pts,xy),
                         after_max32=summary(selected,xy),scope="approximate user cylinder, not point GT"))
with a.out.open("x",encoding="utf-8") as out:json.dump(rows,out,indent=2)
print(json.dumps(rows,indent=2))
