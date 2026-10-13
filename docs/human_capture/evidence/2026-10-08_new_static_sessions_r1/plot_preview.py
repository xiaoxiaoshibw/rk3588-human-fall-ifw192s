"""Metric plots and sampled point clouds; no interpolation or inferred labels."""
import json
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

OUT = Path(__file__).resolve().parent
LABELS = {"114205": "Central standing", "114254": "Right desk", "114340": "Left divider", "114422": "Central / left arm raised"}
results = json.loads((OUT / "registration_results.json").read_text(encoding="utf-8"))
valid = [r for r in results if "gate" in r]
fig, axes = plt.subplots(2, len(valid), figsize=(4.3*len(valid), 8), constrained_layout=True)
axes = np.asarray(axes).reshape(2, len(valid))
for col, row in enumerate(valid):
    p = json.loads((OUT / (row["sid"] + "_preview.json")).read_text(encoding="utf-8"))
    sample = p["samples"][1]
    ref = np.asarray(p["reference_points"])
    cur = np.asarray(sample["raw"])
    rem = np.asarray(sample["remaining"])
    for ax, dim in zip(axes[:, col], (1, 2)):
        ax.scatter(ref[:, 0], ref[:, dim], s=.5, c="#999999", alpha=.35, label="Empty reference")
        ax.scatter(cur[:, 0], cur[:, dim], s=.5, c="#0072B2", alpha=.35, label="Registered session")
        ax.scatter(rem[:, 0], rem[:, dim], s=2, c="#D55E00", alpha=.8, label="Reference residual")
        ax.set_xlim(0, 5)
        ax.set_ylim((-2.5, 2.5) if dim == 1 else (0, 2.5))
        ax.set_xlabel("X (m)"); ax.set_ylabel("Y (m)" if dim == 1 else "Z (m)")
        ax.grid(alpha=.15); ax.set_aspect("equal")
    axes[0, col].set_title(LABELS[row["sid"][-6:]] + "\n" + row["sid"][-6:] + "  gate=" + row["gate"])
axes[0, 0].legend(loc="lower left", fontsize=7, markerscale=3)
fig.suptitle("Offline diagnostic: reference residuals can contain people AND furniture; sampled middle frame")
assert not (OUT / "pointcloud_preview.png").exists()
fig.savefig(OUT / "pointcloud_preview.png", dpi=150)
plt.close(fig)

fig, axes = plt.subplots(1, 3, figsize=(13, 4), constrained_layout=True)
names = [r["sid"][-6:] for r in valid]
for ax, key, threshold, title in zip(axes, ("inlier_ratio", "coverage_xy", "fit_p50"), (.5, .5, .02),
    ("Post-trim correspondence / source", "XY coverage", "Point-to-plane fit median (m)")):
    values = [r["support"][key] if key != "fit_p50" else r["residual"]["fit"]["p50"] for r in valid]
    ax.bar(names, values, color="#0072B2")
    ax.axhline(threshold, color="#D55E00", linestyle="--", label="PASS threshold")
    for i, value in enumerate(values): ax.annotate(f"{value:.4f}", (i,value), xytext=(0,4), textcoords="offset points", ha="center")
    ax.set_title(title); ax.set_ylim(0,max(max(values),threshold)*1.25); ax.legend(fontsize=8)
fig.suptitle("Frozen reg_gate_v1; individual metrics do not replace the aggregate gate")
assert not (OUT / "registration_metrics.png").exists()
fig.savefig(OUT / "registration_metrics.png", dpi=150)
plt.close(fig)
