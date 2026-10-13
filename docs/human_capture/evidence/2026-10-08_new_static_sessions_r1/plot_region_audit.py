"""Visual check of the fixed ROI: keep geometry and deleted geometry share exact axes."""
import json
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle
import numpy as np

OUT = Path(__file__).resolve().parent
audit = json.loads((OUT / "region_audit.json").read_text(encoding="utf-8"))
fig, axes = plt.subplots(2, 4, figsize=(15, 7), constrained_layout=True)
for col, item in enumerate(audit["sessions"]):
    row = item["rows"][1]
    center, radius = item["center"], item["radius"]
    for ax, dim in zip(axes[:, col], (1, 2)):
        for name, color, label in (("keptROI", "#0072B2", "Reference kept"), ("lostROI", "#D55E00", "Reference removed")):
            points = np.asarray(row[name])
            if len(points): ax.scatter(points[:, 0], points[:, dim], s=2, c=color, label=label)
        ax.set_xlim(center[0]-radius-.05, center[0]+radius+.05)
        ax.set_ylim((center[1]-radius-.05,center[1]+radius+.05) if dim==1 else (0,2.3))
        ax.set_xlabel("X (m)"); ax.set_ylabel("Y (m)" if dim==1 else "Z (m)")
        ax.grid(alpha=.15); ax.set_aspect("equal")
    axes[0,col].add_patch(Circle(center,radius,fill=False,ls="--",lw=.8,color="#666666"))
    axes[0,col].set_title(item["sid"][-6:]+f"  raw={len(row['rawROI'])}, removed={len(row['lostROI'])}")
axes[0,0].legend(fontsize=7)
fig.suptitle("Fixed spatial proxy, not person GT: side furniture can enter the cylinder (middle frame)")
assert not (OUT / "region_audit.png").exists()
fig.savefig(OUT / "region_audit.png", dpi=150)
plt.close(fig)
