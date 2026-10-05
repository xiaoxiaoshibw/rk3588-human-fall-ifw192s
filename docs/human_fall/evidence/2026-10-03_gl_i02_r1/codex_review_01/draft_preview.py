"""Draft region preview on the real 163621 capture (read-only, synthetic view)."""
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

FIT = (0.50, 1.00, -1.0, 1.0, -1.5, -0.5)
V1 = (1.00, 1.50, 0.3, 2.0, -1.5, -0.5)
V2 = (1.00, 1.50, -2.0, -0.3, -1.5, -0.5)
V3 = (1.50, 2.00, -0.3, 0.3, -1.5, -0.5)

fig, axes = plt.subplots(1, 2, figsize=(16, 8), dpi=110)

# ---------- Left: top-down (X forward, Y left), colored by Z height ----------
ax = axes[0]
sub = nz[::8]  # decimate for speed
sc = ax.scatter(sub[:, 0], sub[:, 1], c=sub[:, 2], cmap="viridis",
                s=1, alpha=0.45, linewidths=0)
plt.colorbar(sc, ax=ax, label="Z (m)")
for name, (xmin, xmax, ymin, ymax, _, _), color in [
        ("F fit", FIT, "red"),
        ("V1", V1, "orange"),
        ("V2", V2, "deepskyblue"),
        ("V3", V3, "magenta")]:
    ax.add_patch(Rectangle((xmin, ymin), xmax - xmin, ymax - ymin,
                           fill=False, edgecolor=color, linewidth=2.0))
    cx, cy = (xmin + xmax) / 2, (ymin + ymax) / 2
    ax.text(cx, cy, name, color=color, fontsize=13, weight="bold",
            ha="center", va="center",
            bbox=dict(boxstyle="round,pad=0.3", facecolor="white",
                      edgecolor=color, alpha=0.9))
ax.set_xlim(0.2, 6.5)
ax.set_ylim(-3.5, 3.5)
ax.set_xlabel("X forward (m)")
ax.set_ylabel("Y left (m)")
ax.set_title("Top-down (robot view): points colored by Z height")
ax.grid(True, alpha=0.3)
ax.set_aspect("equal")

# ---------- Right: side view (X forward, Z up), colored by point-count ----------
ax = axes[1]
sub = nz[::8]
sc = ax.scatter(sub[:, 0], sub[:, 2], c=sub[:, 1], cmap="plasma",
                s=1, alpha=0.4, linewidths=0)
plt.colorbar(sc, ax=ax, label="Y (m)")
for name, (xmin, xmax, ymin, ymax, zmin, zmax), color in [
        ("F fit", FIT, "red"),
        ("V1", V1, "orange"),
        ("V2", V2, "deepskyblue"),
        ("V3", V3, "magenta")]:
    ax.add_patch(Rectangle((xmin, zmin), xmax - xmin, zmax - zmin,
                           fill=False, edgecolor=color, linewidth=2.0))
    cx, cz = (xmin + xmax) / 2, (zmin + zmax) / 2
    ax.text(cx, cz, name, color=color, fontsize=12, weight="bold",
            ha="center", va="center",
            bbox=dict(boxstyle="round,pad=0.3", facecolor="white",
                      edgecolor=color, alpha=0.9))
ax.set_xlim(0.2, 6.5)
ax.set_ylim(-1.8, 3.5)
ax.set_xlabel("X forward (m)")
ax.set_ylabel("Z up (m)")
ax.set_title("Side view: the floor sits in the band Z∈[-1.5,-0.5] at X<2m")
ax.grid(True, alpha=0.3)
ax.axhline(y=-1.5, color="gray", linestyle="--", linewidth=0.7)
ax.axhline(y=-0.5, color="gray", linestyle="--", linewidth=0.7)

fig.suptitle(
    "GL-I02 draft region preview (real 163621, read-only)\n"
    f"F={FIT}  V1={V1}  V2={V2}  V3={V3}",
    fontsize=11)
fig.tight_layout()
out = "docs/human_fall/evidence/2026-10-03_gl_i02_r1/codex_review_01/draft_preview.png"
fig.savefig(out)
print("wrote", out)
