"""HF-12 probe: synthetic drop counts + 60k-scale runtime for denoise_mask.

Read-only diagnostic; not a calibration or real-data claim.
"""

import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "src" / "human_fall_detection"))

from core.lidar_candidates import build_snapshot, denoise_mask, resolve_settings

rng = np.random.RandomState(11)
floor = np.column_stack([
    rng.uniform(-6.0, 6.0, 58000),
    rng.uniform(-6.0, 6.0, 58000),
    np.full(58000, -1.5) + rng.randn(58000) * 0.004])
objects = np.vstack([rng.normal(center, 0.18, (500, 3))
                     for center in ((3.0, 0.0, -0.9), (3.0, 2.0, -1.0),
                                    (-2.0, 1.0, -1.2))])
# Sparse singles on a 0.4 m grid jittered inside 0.05 m: > 0.3 m apart.
grid = np.stack(np.meshgrid(np.arange(-5.5, 5.6, 0.4),
                            np.arange(4.0, 6.1, 0.4),
                            np.array([-1.0])), axis=-1).reshape(-1, 3)
grid = grid + rng.uniform(-0.05, 0.05, grid.shape)
points = np.vstack((floor, objects, grid[:250]))

mask = denoise_mask(points, 0.1, 2)
started = time.perf_counter()
for _ in range(5):
    denoise_mask(points, 0.1, 2)
per_call = (time.perf_counter() - started) / 5.0
print("scene points:", len(points))
print("kept:", int(mask.sum()), "dropped:", int((~mask).sum()))
print("denoise_mask per-call seconds (5-run mean): %.4f" % per_call)

settings_off = resolve_settings(None)
settings_on = dict(settings_off)
settings_on["denoise_enabled"] = True
started = time.perf_counter()
for _ in range(3):
    build_snapshot(points, settings_off, session_id="probe", time_epoch=0,
                   snapshot_id="p0")
off_s = (time.perf_counter() - started) / 3.0
started = time.perf_counter()
for _ in range(3):
    snap = build_snapshot(points, settings_on, session_id="probe", time_epoch=0,
                          snapshot_id="p1")
on_s = (time.perf_counter() - started) / 3.0
print("build_snapshot disabled: %.4f s" % off_s)
print("build_snapshot enabled : %.4f s (delta %.4f s)" % (on_s, on_s - off_s))

stage = snap["quality"]["denoise"]
print("snapshot denoise:", stage)
print("candidates:", len(snap["candidates"]),
      "first point_count:", snap["candidates"][0]["point_count"]
      if snap["candidates"] else None)
