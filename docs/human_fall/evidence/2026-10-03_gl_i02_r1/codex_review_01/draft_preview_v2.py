"""Real ground preview, v2 (after user clarified sensor mount)."""
import sys
sys.path.insert(0, "src/human_fall_detection")

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

from core.capture_input import load_adapted

manifest, points = load_adapted(
    "docs/human_fall/evidence/2026-10-03_gl_i01_r1/prepared/cap_20261002_163621.npz")
nz = points[np.any(points != 0.0, axis=1)].astype(np.float64)

# Candidate regions on the TRUE ground ring (Z~1.4, X 2~5m, Y mostly -2~0.5)
FIT = (2.5, 3.5, -1.6, -0.4, 0.8, 2.5)
V1 = (2.0, 2.5, -1.6, -0.4, 0.8, 2.5)
V2 = (2.5, 3.5, -2.4, -1.6, 0.8, 2.5)
V3 = (3.5, 4.5, -1.0, 0.4, 0.8, 2.5)

fig, axes = plt.subplots(1, 2, figsize=(16, 8), dpi=110)

ax = axes[0]
sub = nz[::6]
sc = ax.scatter(sub[:, 0], sub[:, 1], c=sub[:, 2], cmap="viridis",
                s=1, alpha=0.4, linewidths=0)
plt.colorbar(sc, ax=ax, label="Z (m)")
for name, (xmin, xmax, ymin, ymax, _, _), color in [
        ("F fit", FIT, "red"),
        ("V1", V1, "orange"),
        ("V2", V2, "deepskyblue"),
        ("V3", V3, "magenta")]:
    ax.add_patch(Rectangle((xmin, ymin), xmax - xmin, ymax - ymin,
                           fill=False, edgecolor=color, linewidth=2.5))
    cx, cy = (xmin + xmax) / 2, (ymin + ymax) / 2
    ax.text(cx, cy, name, color=color, fontsize=13, weight="bold",
            ha="center", va="center",
            bbox=dict(boxstyle="round,pad=0.3", facecolor="white",
                      edgecolor=color, alpha=0.95))
ax.set_xlim(0.2, 7)
ax.set_ylim(-4, 3)
ax.set_xlabel("X forward (m)  →  机器人正前方")
ax.set_ylabel("Y left (m)  →  机器人左")
ax.set_title("Top-down (v2): regions on the TRUE ground ring (Z~1.4m)")
ax.grid(True, alpha=0.3)
ax.set_aspect("equal")

ax = axes[1]
sub = nz[::6]
sc = ax.scatter(sub[:, 0], sub[:, 2], c=sub[:, 1], cmap="plasma",
                s=1, alpha=0.4, linewidths=0)
plt.colorbar(sc, ax=ax, label="Y (m)")
for name, (xmin, xmax, ymin, ymax, zmin, zmax), color in [
        ("F fit", FIT, "red"),
        ("V1", V1, "orange"),
        ("V2", V2, "deepskyblue"),
        ("V3", V3, "magenta")]:
    ax.add_patch(Rectangle((xmin, zmin), xmax - xmin, zmax - zmin,
                           fill=False, edgecolor=color, linewidth=2.5))
    cx, cz = (xmin + xmax) / 2, (zmin + zmax) / 2
    ax.text(cx, cz, name, color=color, fontsize=12, weight="bold",
            ha="center", va="center",
            bbox=dict(boxstyle="round,pad=0.3", facecolor="white",
                      edgecolor=color, alpha=0.95))
ax.set_xlim(0.2, 7)
ax.set_ylim(-2, 6)
ax.set_xlabel("X forward (m)")
ax.set_ylabel("Z — LiDAR's 'down' axis (m)")
ax.set_title("Side view: true ground ring vs the table/flower surface (Z<0, X<2)")
ax.grid(True, alpha=0.3)

fig.suptitle("GL-I02 draft regions v2 — true ground (user confirmed X=forward, tilted-down mount)",
             fontsize=12)
fig.tight_layout()
out = "docs/human_fall/evidence/2026-10-03_gl_i02_r1/codex_review_01/draft_preview_v2.png"
fig.savefig(out)
print("wrote", out)

# Stats
def stat(b):
    xmin, xmax, ymin, ymax, zmin, zmax = b
    m = (nz[:, 0] >= xmin) & (nz[:, 0] < xmax) & (nz[:, 1] >= ymin) & (nz[:, 1] < ymax) & (nz[:, 2] >= zmin) & (nz[:, 2] <= zmax)
    sel = nz[m]
    return len(sel), (sel[:, 2].min(), np.median(sel[:, 2]), sel[:, 2].max()) if len(sel) else None

print()
for nm, b in [("FIT", FIT), ("V1", V1), ("V2", V2), ("V3", V3)]:
    n, z = stat(b)
    print("%s  %s  n=%7d  Z=[%+.2f, %+.2f, %+.2f]" % (nm, b, n, z[0], z[1], z[2]))
