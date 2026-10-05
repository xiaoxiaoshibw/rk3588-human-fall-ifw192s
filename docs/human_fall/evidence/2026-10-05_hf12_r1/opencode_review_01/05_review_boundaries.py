"""HF-12 independent review boundary checks (read-only, desktop).

Reviewer session, not the writer session. Every result is re-derived here from
the current tree and the HEAD baseline blob; nothing is written outside this
review evidence directory.
"""
import copy
import hashlib
import importlib.util
import subprocess
import sys
from pathlib import Path

import numpy as np

REPO = Path(r"D:\Code\ldiar")
PKG = REPO / "src" / "human_fall_detection"
REVIEW = REPO / "docs" / "human_fall" / "evidence" / "2026-10-05_hf12_r1" / "opencode_review_01"
sys.path.insert(0, str(PKG))
sys.path.insert(0, str(PKG / "scripts"))

from core.lidar_candidates import (build_background, build_snapshot, denoise_mask,
                                   resolve_settings, validate_snapshot)
from sensor_health import dumps_strict, load_config

print("python:", sys.version.split()[0], "numpy:", np.__version__)

results = []


def run(name, fn):
    try:
        value = fn()
    except Exception as exc:  # noqa: BLE001 - report every failure instead of aborting
        results.append((name, False, "%s: %s" % (type(exc).__name__, exc)))
        print("FAIL", name, "--", type(exc).__name__, exc)
        return None
    ok = bool(value)
    results.append((name, ok, ""))
    print("PASS" if ok else "FAIL", name)
    return value


def brute_voxel_mask(pts, radius, mn):
    cells = np.floor(np.asarray(pts, dtype=np.float64) / radius).astype(np.int64)
    counts = {}
    for cell in map(tuple, cells.tolist()):
        counts[cell] = counts.get(cell, 0) + 1
    keep = np.zeros(len(cells), dtype=bool)
    for i, cell in enumerate(map(tuple, cells.tolist())):
        total = 0
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for dz in (-1, 0, 1):
                    total += counts.get((cell[0] + dx, cell[1] + dy, cell[2] + dz), 0)
        keep[i] = total >= mn
    return keep


VALID_GROUND = {"kind": "ground_plane", "status": "valid", "frame": "innolidar",
                "normal": [0.0, 0.0, 1.0], "offset_m": 1.5, "sensor_height_m": 1.5}

# ---- H01: default-off equivalence against the recorded pre-change baseline ----
head = subprocess.run(["git", "show", "HEAD:src/human_fall_detection/core/lidar_candidates.py"],
                      cwd=str(REPO), capture_output=True, check=True).stdout
head_path = REVIEW / "_head_lidar_candidates.py"
head_path.write_bytes(head)
head_sha = hashlib.sha256(head).hexdigest().upper()
run("H01 HEAD blob == writer pre-change SHA 447E4003...",
    lambda: head_sha == "447E4003C12E114BDCAC657FD980B302BF01DA473E4A285E66E1312772DB5373")

spec = importlib.util.spec_from_file_location("hf12_head_lidar_candidates", str(head_path))
baseline = importlib.util.module_from_spec(spec)
spec.loader.exec_module(baseline)

rng = np.random.RandomState(123)
blob01 = rng.normal((3.0, 0.0, -1.0), 0.2, (300, 3))
far01 = rng.uniform(-1.0, 1.0, (200, 3)) + np.array([20.0, 0.0, 0.0])
points01 = np.vstack([blob01, far01, [[0.1, 0.0, -1.4]],
                      [[np.nan, 0.0, -1.0], [np.inf, 0.0, -1.0], [0.0, np.nan, -1.0]]])
background01 = build_background([np.array([[5.0, 5.0, -1.5]])], frame_id="innolidar")
kw = dict(session_id="review", time_epoch=0, snapshot_id="r1",
          ground=VALID_GROUND, background=background01)
common = {"max_points": 1000}
cur = build_snapshot(points01, common, **kw)
base = baseline.build_snapshot(points01, common, **kw)


def strip_new(obj):
    out = copy.deepcopy(obj)
    for key in ("denoise_enabled", "denoise_radius_m", "denoise_min_neighbors"):
        out["settings"].pop(key, None)
    out["quality"].pop("denoise", None)
    return out


run("H01 default-off current == HEAD after stripping the added keys",
    lambda: dumps_strict(strip_new(cur)) == dumps_strict(base))
stage01 = cur["quality"]["denoise"]
run("H01 default-off stage is a no-op record", lambda: (
    stage01["enabled"] is False and stage01["radius_m"] is None
    and stage01["min_neighbors"] is None and stage01["dropped_point_count"] == 0
    and stage01["input_point_count"] == stage01["kept_point_count"]))

# ---- H02: mask semantics vs exact voxel counting ----
cloud = np.random.RandomState(7).uniform(-2.5, 2.5, (2500, 3))
for radius in (0.05, 0.1, 0.3, 0.7):
    run("H02 dense path == brute-force voxel count (r=%s)" % radius,
        lambda r=radius: np.array_equal(denoise_mask(cloud, r, 2),
                                        brute_voxel_mask(cloud, r, 2)))

packed = np.vstack([
    np.column_stack([np.random.RandomState(8).uniform(0.0, 30.0, 600),
                     np.random.RandomState(9).uniform(0.0, 30.0, 600),
                     np.zeros(600)]),
    [[10.0, 10.0, 0.0], [10.006, 10.0, 0.0]]])
run("H02 packed fallback == brute force (span 30 m, r=0.01)",
    lambda: np.array_equal(denoise_mask(packed, 0.01, 2),
                           brute_voxel_mask(packed, 0.01, 2)))

pair = np.array([[2.999, 0.0, 0.0], [3.002, 0.0, 0.0], [5.0, 5.0, 0.0]])
run("H02 cross-voxel pair supports, far single dropped",
    lambda: denoise_mask(pair, 0.1, 2).tolist() == [True, True, False])
run("H02 min_neighbors=1 keeps a single point",
    lambda: denoise_mask(np.array([[3.0, 0.0, 0.0]]), 0.1, 1).tolist() == [True])
run("H02 min_neighbors=2 drops a single point",
    lambda: denoise_mask(np.array([[3.0, 0.0, 0.0]]), 0.1, 2).tolist() == [False])
run("H02 empty input returns an empty mask",
    lambda: len(denoise_mask(np.zeros((0, 3)), 0.1, 2)) == 0)
run("H02 deterministic over repeated runs",
    lambda: np.array_equal(denoise_mask(cloud, 0.3, 2), denoise_mask(cloud, 0.3, 2)))
print("NOTE documented coarse semantics: two points 0.19 m apart (> 0.1 m radius),"
      " adjacent voxels ->",
      denoise_mask(np.array([[0.0, 0.0, 0.0], [0.19, 0.0, 0.0]]), 0.1, 2).tolist())

# ---- H03: settings validation ----
def rejected(settings):
    try:
        resolve_settings(settings)
    except ValueError:
        return True
    return False


for bad in ({"denoise_enabled": 1}, {"denoise_enabled": np.True_},
            {"denoise_radius_m": 0.0}, {"denoise_radius_m": float("nan")},
            {"denoise_min_neighbors": 0}, {"denoise_min_neighbors": True},
            {"denoise_min_neighbors": 2.5}, {"not_a_setting": 1}):
    key, value = next(iter(bad.items()))
    run("H03 reject %s=%r" % (key, value), lambda b=bad: rejected(b))
run("H03 np.int64 min_neighbors accepted",
    lambda: resolve_settings({"denoise_min_neighbors": np.int64(3)})["denoise_min_neighbors"] == 3)
old = {k: v for k, v in resolve_settings(None).items() if not k.startswith("denoise_")}


def old_roundtrip():
    resolved = resolve_settings(old)
    return (resolved["denoise_enabled"] is False
            and resolved["denoise_radius_m"] == 0.1
            and resolved["denoise_min_neighbors"] == 2)


run("H03 pre-change settings round-trip to defaults", old_roundtrip)
try:
    resolve_settings({"denoise_radius_m": None})
    print("NOTE radius=None accepted")
except Exception as exc:  # noqa: BLE001 - note only
    print("NOTE radius=None ->", type(exc).__name__,
          "(same float() conversion style as the other positive keys)")
try:
    denoise_mask(np.array([[0.0, 0.0, 0.0], [12.0, 12.0, 12.0]]), 1e-6, 2)
    print("NOTE radius=1e-6 did not raise")
except ValueError as exc:
    print("NOTE radius=1e-6 over an extreme extent -> runtime guard:", exc,
          "(positive finite radii pass resolve_settings; documented bounded fallback)")

# ---- H04: ordering (denoise before height gate and background) ----
settings_h = {"denoise_enabled": True, "denoise_radius_m": 0.15,
              "denoise_min_neighbors": 2, "min_cluster_points": 1,
              "preferred_cluster_points": 1}
pts_h = np.array([[2.0, 0.0, -1.74], [2.0, 0.0, -1.86]])
snap_h = build_snapshot(pts_h, settings_h, session_id="review", time_epoch=0,
                        snapshot_id="h", ground=VALID_GROUND)


def height_order_ok():
    stage = snap_h["quality"]["denoise"]
    return ((stage["input_point_count"], stage["kept_point_count"],
             stage["dropped_point_count"]) == (2, 2, 0)
            and len(snap_h["candidates"]) == 1
            and snap_h["candidates"][0]["point_count"] == 1)


run("H04 denoise precedes the height gate (below-band point supports)", height_order_ok)

background_h = build_background([np.array([[2.0, 0.0, 0.0]])], frame_id="innolidar")
settings_b = {"denoise_enabled": True, "denoise_radius_m": 0.2,
              "denoise_min_neighbors": 2, "min_cluster_points": 1,
              "preferred_cluster_points": 1}
pts_b = np.array([[2.0, 0.0, 0.0], [2.15, 0.0, 0.0]])
snap_b = build_snapshot(pts_b, settings_b, session_id="review", time_epoch=0,
                        snapshot_id="b", background=background_h)


def background_order_ok():
    return (snap_b["quality"]["denoise"]["dropped_point_count"] == 0
            and snap_b["quality"]["background_applied"] is True
            and len(snap_b["candidates"]) == 1
            and snap_b["candidates"][0]["point_count"] == 1)


run("H04 denoise precedes background removal", background_order_ok)

# ---- H05/H06: snapshot, evidence indices, quality, config ----
pts_q = np.vstack([
    np.random.RandomState(9).normal((3.0, 0.0, -1.0), 0.15, (300, 3)),
    np.column_stack([np.linspace(-4.0, 4.0, 17), np.full(17, 5.0),
                     np.full(17, -1.5)]),
])
settings_q = {"denoise_enabled": True, "denoise_radius_m": 0.15,
              "denoise_min_neighbors": 2}
snap_q1 = build_snapshot(pts_q, settings_q, session_id="review", time_epoch=0,
                         snapshot_id="q")
snap_q2 = build_snapshot(pts_q, settings_q, session_id="review", time_epoch=0,
                         snapshot_id="q")
text_q = dumps_strict(snap_q1)


def h05_ok():
    validate_snapshot(snap_q1)
    return (text_q == dumps_strict(snap_q2) and "NaN" not in text_q
            and "Infinity" not in text_q)


run("H05 validate_snapshot + deterministic + strict JSON", h05_ok)


def evidence_ok():
    candidate = snap_q1["candidates"][0]
    evidence = pts_q[np.asarray(candidate["evidence_indices"])]
    return (len(evidence) == candidate["point_count"]
            and np.all(np.linalg.norm(
                evidence - np.array([3.0, 0.0, -1.0]), axis=1) < 1.0))


run("H05 evidence indices map to original input points", evidence_ok)


def h06_counts_ok():
    stage = snap_q1["quality"]["denoise"]
    mask = denoise_mask(pts_q, stage["radius_m"], stage["min_neighbors"])
    return (stage["input_point_count"] == len(pts_q)
            and stage["kept_point_count"] == int(mask.sum())
            and stage["dropped_point_count"] == int((~mask).sum())
            and stage["kept_point_count"] + stage["dropped_point_count"] == len(pts_q))


run("H06 quality counts equal the recomputed mask", h06_counts_ok)


def h06_config_ok():
    config = load_config(str(PKG / "config" / "perception.yaml"))
    resolved = resolve_settings(config["candidates"])
    return (resolved["denoise_enabled"] is True
            and resolved["denoise_radius_m"] == 0.1
            and resolved["denoise_min_neighbors"] == 2)


run("H06 perception.yaml resolves to enabled/0.1/2", h06_config_ok)

snap_off = build_snapshot(pts_q, {"denoise_enabled": False}, session_id="review",
                          time_epoch=0, snapshot_id="off")


def h06_off_ok():
    stage = snap_off["quality"]["denoise"]
    return (stage["enabled"] is False and stage["dropped_point_count"] == 0
            and stage["input_point_count"] == len(pts_q)
            and stage["kept_point_count"] == len(pts_q))


run("H06 disabled stage dropped=0", h06_off_ok)

failed = [name for name, ok, _ in results if not ok]
print("checks:", len(results), "failed:", len(failed))
for name, ok, detail in results:
    if not ok:
        print("  FAIL:", name, detail)
sys.exit(1 if failed else 0)
