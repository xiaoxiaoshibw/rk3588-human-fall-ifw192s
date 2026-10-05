#!/usr/bin/env python3
"""Render LI-DATA synthetic point-cloud frames to a multi-panel PNG.

Reads frames straight from the dataset zip (read-only), reuses the same axis
mapping as lidata_to_replay (ros_x = slant depth, ros_y = -X, ros_z = Z).
Color encodes semantic role, not raw categoryID:
  human  (categoryID 5 or 6)            -> orange (categorical slot 2)
  near-ground (z <= 0.15, non-human)    -> blue   (categorical slot 1)
  environment (everything else)         -> neutral gray (non-data ink)
Palette validated all-pairs: #eb6834 vs #2a78d6.
"""
import csv
import io
import os
import zipfile
from collections import OrderedDict

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ZIP = r"D:\Code\ldiar\ML\LI-DATA\Dataset (Blender+LiDAR)1000poses.zip"
ROOT = "Dataset (Blender+LiDAR)1000poses"
OUT = r"D:\Code\ldiar\docs\sidequests\lidata_pointcloud.png"

C_HUMAN = "#eb6834"   # categorical slot 2 (orange)
C_GROUND = "#2a78d6"  # categorical slot 1 (blue)
C_ENV = "#b9b7ae"     # recessive neutral for non-data structure
INK = "#0b0b0b"
INK2 = "#52514e"
SURF = "#fcfcfb"
GRID = "#e1e0d9"

SEQS = OrderedDict([
    ("fall", ROOT + "/Fall Data 500 poses/50FallData_PoseSet_part2/Pose_021_arms_back_arms_front_bent_straight"),
    ("no-fall", ROOT + "/No Fall Data 500 poses/50 Walking 7/Pose_004_LeaningForward"),
])
SNAP_IDX = [0, 0.5, 0.8, 0.999]  # normalized timeline: start, mid, falling, end


def role_of(cat, z):
    if cat in (5.0, 6.0):
        return "human"
    if z <= 0.15:
        return "ground"
    return "env"


ROLE_COLOR = {"human": C_HUMAN, "ground": C_GROUND, "env": C_ENV}
ROLE_SIZE = {"human": 28.0, "ground": 20.0, "env": 8.0}
ROLE_ORDER = {"env": 0, "ground": 1, "human": 2}


def load_frames(zip_path, prefix):
    with zipfile.ZipFile(zip_path) as archive:
        names = sorted(
            (n for n in archive.namelist()
             if n.startswith(prefix + "/") and n.lower().endswith(".csv")),
            key=lambda n: int(n.rsplit("_frame_", 1)[-1].split(".")[0]))
        frames = []
        for name in names:
            rows = []
            with archive.open(name) as handle:
                reader = csv.reader(io.TextIOWrapper(handle, encoding="utf-8",
                                                     errors="replace"),
                                    delimiter=";")
                next(reader, None)
                for p in reader:
                    if len(p) < 6:
                        continue
                    try:
                        cat = float(p[0])
                        x, y, z = float(p[2]), float(p[3]), float(p[4])
                    except ValueError:
                        continue
                    depth = (x * x + y * y + z * z) ** 0.5
                    rows.append((depth, -x, z, cat))
            frames.append(np.asarray(rows, dtype=np.float64))
    return frames


def draw_cloud(ax, frame, view):
    # frame rows: (depth, lateral, up, cat). view: 'side' -> x=depth,y=up ; 'top' -> x=depth,y=lateral
    xi = {"side": 0, "top": 0}[view]
    yi = {"side": 2, "top": 1}[view]
    order = sorted(range(len(frame)), key=lambda i: ROLE_ORDER[role_of(frame[i, 3], frame[i, 2])])
    for i in order:
        r = role_of(frame[i, 3], frame[i, 2])
        ax.scatter(frame[i, xi], frame[i, yi], s=ROLE_SIZE[r], c=ROLE_COLOR[r],
                   linewidths=0, rasterized=True)
    ax.set_facecolor(SURF)


def main():
    data = {k: load_frames(ZIP, p) for k, p in SEQS.items()}
    ncols = len(SNAP_IDX)
    fig, axes = plt.subplots(len(SEQS), ncols, figsize=(13, 6.2),
                             facecolor=SURF)
    for row, label in enumerate(SEQS):
        frames = data[label]
        for col, frac in enumerate(SNAP_IDX):
            idx = min(len(frames) - 1, int(frac * (len(frames) - 1)))
            ax = axes[row][col]
            draw_cloud(ax, frames[idx], "side")
            ax.set_xlim(0, 18)
            ax.set_ylim(-0.3, 2.2)
            for spine in ("top", "right"):
                ax.spines[spine].set_visible(False)
            for spine in ("left", "bottom"):
                ax.spines[spine].set_color(GRID)
            ax.grid(True, color=GRID, linewidth=0.6, zorder=0)
            ax.tick_params(colors=INK2, labelsize=8, length=0)
            if row == len(SEQS) - 1:
                ax.set_xlabel("depth (m)", color=INK2, fontsize=9)
            if col == 0:
                ax.set_ylabel(label + "\nheight (m)", color=INK, fontsize=10)
            t_label = "f{}".format(idx)
            ax.set_title("frame {}".format(idx), color=INK, fontsize=10) if row == 0 else None

    # legend: semantic roles, text in ink with colored swatch
    import matplotlib.lines as mlines
    handles = [
        mlines.Line2D([], [], marker="o", color="none", markerfacecolor=C_HUMAN,
                      markersize=8, label="human"),
        mlines.Line2D([], [], marker="o", color="none", markerfacecolor=C_GROUND,
                      markersize=8, label="near ground"),
        mlines.Line2D([], [], marker="o", color="none", markerfacecolor=C_ENV,
                      markersize=7, label="environment"),
    ]
    leg = fig.legend(handles=handles, loc="lower center", ncol=3, frameon=False,
                     fontsize=10, bbox_to_anchor=(0.5, 0.005))
    for txt in leg.get_texts():
        txt.set_color(INK)
    fig.suptitle("LI-DATA synthetic scan — side view (sensor at origin, z up)",
                 color=INK, fontsize=13)
    fig.tight_layout(rect=(0, 0.05, 1, 0.95))
    fig.savefig(OUT, dpi=150, facecolor=SURF)
    print("wrote", os.path.abspath(OUT))


if __name__ == "__main__":
    main()
