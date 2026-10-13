"""Show equal representative frames before/after background deletion in side view."""
import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
import numpy as np

from audit_truth import covers_xy

p=argparse.ArgumentParser()
p.add_argument("--foreground",type=Path,required=True)
p.add_argument("--results",type=Path,required=True)
p.add_argument("--truth",type=Path,required=True)
p.add_argument("--out",type=Path,required=True)
a=p.parse_args()
mf=json.loads((a.foreground/"manifest.json").read_text(encoding="utf-8"))
truth={s["session"]:s for s in json.loads(a.truth.read_text(encoding="utf-8"))["sessions"]}
columns=["B_workspace","C_reference","E_cleanup"]
fig,axes=plt.subplots(4,3,figsize=(13,12),layout="constrained")
for row,session in enumerate(mf["sessions"]):
    sid=session["sid"];index=len(session["frames"])//2;frame=session["frames"][index];xy=truth[sid]["xy_m"]
    for col,v in enumerate(columns):
        ax=axes[row,col]
        cloud=np.fromfile(a.foreground/sid/frame["variants"][v]["file"],dtype="<f4").reshape(-1,4)
        mask=(cloud[:,0]>=1)&(cloud[:,0]<=5)&(np.abs(cloud[:,1]-xy[1])<=.85)
        visible=cloud[mask]
        local=np.sum((visible[:,:2]-xy)**2,axis=1)<=.55**2
        ax.scatter(visible[~local,0],visible[~local,2],s=.5,color="#989EA8",alpha=.4,rasterized=True)
        ax.scatter(visible[local,0],visible[local,2],s=1,color="#0072B2",alpha=.65,rasterized=True)
        pred=json.loads((a.results/v/(sid+"_predictions.json")).read_text(encoding="utf-8"))["frames"][index]
        for d in pred["detections"]:
            if d["label"]!="Pedestrian" or not covers_xy(d["box_xyz_bottom_wlh_yaw"],xy):continue
            x,y,z,w,l,h,yaw=d["box_xyz_bottom_wlh_yaw"]
            span=abs(w*np.cos(yaw))+abs(l*np.sin(yaw))
            ax.add_patch(Rectangle((x-span/2,z+1.73),span,h,fill=False,color="#D55E00",linewidth=1.3))
        ax.set(xlim=(1,5),ylim=(0,2.5),xlabel="Forward x (m)",ylabel="Ground height (m)",
               title=sid[-6:]+" "+v+" | score="+"%.3f"%pred["target_max_score"])
        ax.grid(alpha=.2)
fig.suptitle("Same midpoint frame per session | fixed PointPillars weights\nBlue: user location neighborhood (not point GT); orange: predicted pedestrian box covering location",fontsize=12)
fig.savefig(a.out,dpi=160)
plt.close(fig)
