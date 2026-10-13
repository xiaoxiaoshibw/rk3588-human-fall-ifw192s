"""Diagnostic BEV views: strongest pedestrian candidate frame, model output not ground truth."""
import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon
import numpy as np

from experiment import read_frame, adapt
from batch_static import SESSIONS

p=argparse.ArgumentParser()
p.add_argument("--results",type=Path,required=True)
p.add_argument("--data-root",type=Path,required=True)
p.add_argument("--out",type=Path,required=True)
a=p.parse_args()
fig,axes=plt.subplots(2,2,figsize=(12,10),layout="constrained")
for sid,ax in zip(SESSIONS,axes.flat):
    result=json.loads((a.results/(sid+"_predictions.json")).read_text(encoding="utf-8"))
    strongest=max(result["frames"],key=lambda f:max([d["score"] for d in f["detections"] if d["label"]=="Pedestrian"],default=0))
    transform=json.loads((a.results/"leveling"/sid/"tls/transform.json").read_text(encoding="utf-8"))
    points,_=read_frame(a.data_root/sid,strongest["index"])
    cloud=adapt(points,transform,result["model_z"],result["intensity_divisor"])
    # Same ROI for all panels, visualization only; full clouds were used in inference.
    mask=(cloud[:,0]>=0)&(cloud[:,0]<=14)&(np.abs(cloud[:,1])<10)
    visible=cloud[mask][::3]
    ax.scatter(visible[:,0],visible[:,1],s=.25,c="#808994",alpha=.3,rasterized=True)
    persons=[d for d in strongest["detections"] if d["label"]=="Pedestrian"]
    for d in persons:
        x,y,z,w,l,h,yaw=d["box_xyz_bottom_wlh_yaw"]
        c,s=np.cos(yaw),np.sin(yaw)
        corners=np.array([[-w/2,-l/2],[w/2,-l/2],[w/2,l/2],[-w/2,l/2]]) @ np.array([[c,s],[-s,c]])+[x,y]
        color="#D55E00" if d["score"]>=.3 else "#0072B2"
        ax.add_patch(Polygon(corners,fill=False,edgecolor=color,linewidth=1))
        ax.text(x,y,"%.2f"%d["score"],fontsize=7,color=color)
    ax.set(xlim=(0,14),ylim=(-10,10),xlabel="Forward x (m)",ylabel="Left y (m)",
           title=sid+" | frame "+str(strongest["index"]))
    ax.set_aspect("equal")
    ax.grid(alpha=.15)
fig.suptitle("Leveled PointPillars CPU trial | strongest candidate per session\nBlue: 0.1-0.3 | Orange: >=0.3 | No candidates >=0.5 | No human GT",fontsize=12)
a.out.parent.mkdir(parents=True,exist_ok=True)
fig.savefig(a.out,dpi=150)
plt.close(fig)
