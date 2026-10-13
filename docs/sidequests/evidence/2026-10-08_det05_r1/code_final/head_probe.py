"""Read-only checkpoint heads before top100/NMS; no threshold or weight changes."""
import argparse
import json
from pathlib import Path

import numpy as np
import torch
from cpu_pointpillars import load_model

p=argparse.ArgumentParser()
p.add_argument("--foreground",type=Path,required=True)
p.add_argument("--truth",type=Path,required=True)
p.add_argument("--out",type=Path,required=True)
a=p.parse_args()
mf=json.loads((a.foreground/"manifest.json").read_text(encoding="utf-8"))
truth={s["session"]:s for s in json.loads(a.truth.read_text(encoding="utf-8"))["sessions"]}
up=Path(__file__).resolve().parent/"artifacts/upstream"
model=load_model(up/"epoch_160.pth",up);torch.set_num_threads(4)
captured=[]
handle=model.head.register_forward_hook(lambda _m,_i,out:captured.append(out[0].detach().clone()))
rows=[]
try:
    for session in mf["sessions"]:
        sid=session["sid"];xy=truth[sid]["xy_m"];frame=session["frames"][len(session["frames"])//2]
        for v in ["B_workspace","E_cleanup"]:
            pts=np.fromfile(a.foreground/sid/frame["variants"][v]["file"],dtype="<f4").reshape(-1,4)
            pts[:,2]-=np.float32(1.73);pts[:,3]/=np.float32(1023)
            with torch.inference_mode():
                model([torch.from_numpy(pts)],mode="test")
                cls=captured.pop()[0];scores=cls.permute(1,2,0).reshape(-1,3).sigmoid()
                anchors=model.anchors_generator.get_multi_anchors(torch.tensor(list(cls.shape[-2:]))).reshape(-1,7)
                local=((anchors[:,:2]-torch.tensor(xy)).square().sum(1)<=.55**2)
                selected=scores.max(1).values.topk(model.nms_pre).indices
                rows.append(dict(sid=sid,index=frame["index"],variant=v,
                    local_anchor_max_pedestrian_before_topk=float(scores[local,0].max()),
                    local_anchors_with_pedestrian_gt_01=int((scores[local,0]>.1).sum()),
                    local_anchors_selected_by_top100=int(local[selected].sum()),
                    interpretation="Anchor center within approximate location radius, not matched decoded box; diagnostic only"))
finally:handle.remove()
with a.out.open("x",encoding="utf-8") as out:json.dump(rows,out,indent=2)
print(json.dumps(rows,indent=2))
