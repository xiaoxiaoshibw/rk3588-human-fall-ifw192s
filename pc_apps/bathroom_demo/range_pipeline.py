"""Range-image front-end, tracking and fall-state demo for IFW192S.

Standalone PC-side demo (NumPy + optional Pillow for rendering). It does not
import ROS and does not touch the production pipeline. Python 3.8 compatible.

Core ideas (see docs/RADAR_DATA_FIT_PLAN_2026-10-23.md):
  - the IFW192S has a fixed 192 x 240 ray grid at 10 Hz;
  - a per-ray background model turns each frame into a residual range image;
  - foreground components are grown with a depth-continuity rule, not a fixed
    metric voxel;
  - a constant-velocity tracker keeps the target across frames;
  - an event state machine uses height-above-floor + span + hold time.

The demo is deliberately explicit about what it does not prove: it is not a
human-labelled fall detector and it does not replace a bathroom capture.
"""
import json
import math
import os
import time
import warnings
from collections import Counter, deque

import numpy as np

try:
    from fall_hmm import FallHMM
except ImportError:  # imported as a package
    from .fall_hmm import FallHMM

RINGS = 192
COLS = 240
AZ0 = -59.8
DAZ = 0.5
EL0 = -41.6
DEL = 0.469

POINT_DTYPE = np.dtype({
    "names": ["x", "y", "z", "intensity", "ring", "timestamp"],
    "formats": ["<f4", "<f4", "<f4", "<f4", "<u2", "<f4"],
    "offsets": [0, 4, 8, 12, 16, 20],
    "itemsize": 28,
})

DEFAULTS = dict(
    range_min=0.30, range_max=4.00, height_min=-0.20, height_max=2.50,
    background_prefix=100, fg_sigma=4.0, fg_floor=0.05, depth_jump=0.012,
    min_component=15, merge_gap=0.35, merge_size=1.0, merge_height=2.2,
    track_gate=0.60, track_max_speed=2.5, track_max_miss=1.5, min_track_hits=2,
    min_target_points=60, min_event_points=100, min_visible_ratio=0.25,
    fall_hold_s=0.30, low_height=0.80, low_span=1.10,
    upright_height=1.20, upright_span=0.80, drop_m=0.35, drop_rate=0.35,
    long_lie_s=30.0,
)


def load_session(session):
    with open(os.path.join(session, "meta.json"), encoding="utf-8") as fh:
        meta = json.load(fh)
    points = np.memmap(os.path.join(session, "points.bin"), dtype=POINT_DTYPE, mode="r")
    return meta, points


def read_raw(meta, points, index):
    frame = meta["frames"][index]
    return np.asarray(points[frame["offset_points"]:frame["offset_points"] + frame["count_points"]])


class RangeGrid(object):
    __slots__ = ("range", "valid", "x", "y", "z", "intensity", "ring", "col")

    def __init__(self, range_, valid, x, y, z, intensity, ring, col):
        self.range = range_
        self.valid = valid
        self.x = x
        self.y = y
        self.z = z
        self.intensity = intensity
        self.ring = ring
        self.col = col


def to_grid(x, y, z, ring, intensity=None):
    """Rasterise points into the fixed 192x240 ray grid.

    Duplicate cells keep the nearest return (smallest range), matching a
    depth image. Invalid/zero returns are dropped. The output arrays are
    float32/uint16 and share the grid shape.
    """
    x = np.asarray(x, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    z = np.asarray(z, dtype=np.float64)
    ring = np.asarray(ring, dtype=np.int64)
    r = np.sqrt(x * x + y * y + z * z)
    az = np.degrees(np.arctan2(y, x))
    col = np.rint((az - AZ0) / DAZ).astype(np.int64)
    ok = (r > 0.1) & (col >= 0) & (col < COLS) & (ring >= 0) & (ring < RINGS)

    rg = np.full((RINGS, COLS), np.nan, dtype=np.float32)
    vg = np.zeros((RINGS, COLS), dtype=bool)
    xg = np.full((RINGS, COLS), np.nan, dtype=np.float32)
    yg = np.full((RINGS, COLS), np.nan, dtype=np.float32)
    zg = np.full((RINGS, COLS), np.nan, dtype=np.float32)
    ig = np.full((RINGS, COLS), np.nan, dtype=np.float32)
    if intensity is None:
        intensity = np.full(len(x), 500.0)
    intensity = np.asarray(intensity, dtype=np.float64)

    idx = np.nonzero(ok)[0]
    if len(idx):
        order = idx[np.argsort(r[idx])[::-1]]
        rr = ring[order]
        cc = col[order]
        rg[rr, cc] = r[order].astype(np.float32)
        xg[rr, cc] = x[order].astype(np.float32)
        yg[rr, cc] = y[order].astype(np.float32)
        zg[rr, cc] = z[order].astype(np.float32)
        ig[rr, cc] = intensity[order].astype(np.float32)
        vg[rr, cc] = True
    return RangeGrid(rg, vg, xg, yg, zg, ig, ring, col)


def raw_to_grid(raw):
    return to_grid(raw["x"], raw["y"], raw["z"], raw["ring"], raw["intensity"])


class Ground(object):
    """Ground-relative height in metres.

    A transform JSON produced by the existing leveling tool maps raw points to
    a ground frame: p_ground = p_raw @ R.T + t, with the floor at z=0.
    A simpler fitted plane z = a*x + b*y + c is available when no transform
    exists; it is a development aid, not a physical calibration.
    """

    def __init__(self, R=None, t=None, plane=None, source="unknown"):
        self.R = None if R is None else np.asarray(R, dtype=np.float64)
        self.t = None if t is None else np.asarray(t, dtype=np.float64)
        self.plane = None if plane is None else np.asarray(plane, dtype=np.float64)
        self.source = source
        if self.R is not None:
            if self.R.shape != (3, 3) or self.t.shape != (3,):
                raise ValueError("ground transform must be R 3x3 and t 3")
        if self.plane is not None and self.plane.shape != (3,):
            raise ValueError("ground plane must have three coefficients")

    @classmethod
    def from_transform(cls, path):
        with open(path, encoding="utf-8") as fh:
            doc = json.load(fh)
        return cls(doc["R"], doc["t"], None, path)

    @classmethod
    def fit(cls, meta, points, prefix=100):
        cloud = []
        for i in range(min(prefix, len(meta["frames"]))):
            raw = read_raw(meta, points, i)
            r = np.sqrt(raw["x"].astype(np.float64) ** 2 + raw["y"].astype(np.float64) ** 2
                        + raw["z"].astype(np.float64) ** 2)
            ok = (r > 0.5) & (r < 8.0)
            if ok.any():
                cloud.append(np.column_stack((raw["x"][ok], raw["y"][ok], raw["z"][ok])))
        if not cloud:
            return cls(plane=[0.0, 0.0, 0.0], source="fit_empty")
        p = np.vstack(cloud).astype(np.float64)
        z = p[:, 2]
        keep = z <= np.percentile(z, 10.0)
        q = p[keep]
        A = np.column_stack((q[:, 0], q[:, 1], np.ones(len(q))))
        coef, _, _, _ = np.linalg.lstsq(A, q[:, 2], rcond=None)
        return cls(plane=coef, source="fit_lower10")

    def height(self, x, y, z):
        x = np.asarray(x, dtype=np.float64)
        y = np.asarray(y, dtype=np.float64)
        z = np.asarray(z, dtype=np.float64)
        if self.R is not None:
            return (x * self.R[2, 0] + y * self.R[2, 1] + z * self.R[2, 2]
                    + self.t[2])
        if self.plane is not None:
            return z - (self.plane[0] * x + self.plane[1] * y + self.plane[2])
        return z

    def to_ground(self, x, y, z):
        x = np.asarray(x, dtype=np.float64)
        y = np.asarray(y, dtype=np.float64)
        z = np.asarray(z, dtype=np.float64)
        if self.R is not None:
            p = np.stack((x, y, z), axis=-1)
            return p @ self.R.T + self.t
        h = self.height(x, y, z)
        return np.stack((x, y, h), axis=-1)

    def from_ground(self, p):
        p = np.asarray(p, dtype=np.float64)
        if self.R is not None:
            return (p - self.t) @ self.R
        if self.plane is not None:
            return np.column_stack((p[:, 0], p[:, 1],
                                    p[:, 2] + self.plane[0] * p[:, 0]
                                    + self.plane[1] * p[:, 1] + self.plane[2]))
        return p


class Background(object):
    def __init__(self, median, sigma, count):
        self.median = median.astype(np.float32)
        self.sigma = sigma.astype(np.float32)
        self.count = int(count)

    @classmethod
    def from_grids(cls, grids, sigma_floor=0.012):
        if not grids:
            raise ValueError("background needs at least one frame")
        arr = np.stack([g.range for g in grids])
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            med = np.nanmedian(arr, axis=0)
            mad = np.nanmedian(np.abs(arr - med), axis=0)
        sigma = 1.4826 * mad
        sigma = np.where(np.isfinite(sigma), sigma, 0.05)
        sigma = np.maximum(sigma, sigma_floor)
        return cls(med, sigma, len(grids))

    @classmethod
    def from_session(cls, meta, points, prefix=100):
        grids = []
        for i in range(min(prefix, len(meta["frames"]))):
            grids.append(raw_to_grid(read_raw(meta, points, i)))
        return cls.from_grids(grids)


def neighbor_count(mask):
    p = np.pad(mask.astype(np.uint8), 1, mode="constant")
    out = np.zeros(mask.shape, dtype=np.uint8)
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            if dx == 0 and dy == 0:
                continue
            out += p[1 + dy:1 + dy + RINGS, 1 + dx:1 + dx + COLS]
    return out


def foreground_mask(grid, background, ground, settings):
    s = settings
    r = grid.range
    valid = grid.valid & np.isfinite(r)
    with np.errstate(invalid="ignore"):
        residual = np.abs(r - background.median)
        mask = valid & np.isfinite(background.median)
        mask &= residual > np.maximum(s["fg_floor"], s["fg_sigma"] * background.sigma)
    mask &= (r >= s["range_min"]) & (r <= s["range_max"])
    h = ground.height(grid.x, grid.y, grid.z)
    mask &= np.isfinite(h) & (h >= s["height_min"]) & (h <= s["height_max"])
    mask &= neighbor_count(mask) >= 1
    return mask


def components(mask, rng, settings):
    s = settings
    labels = np.full(mask.shape, -1, dtype=np.int32)
    out = []
    ys, xs = np.nonzero(mask)
    for y0, x0 in zip(ys.tolist(), xs.tolist()):
        if labels[y0, x0] != -1:
            continue
        cid = len(out)
        labels[y0, x0] = cid
        stack = [(y0, x0)]
        pixels = []
        while stack:
            y, x = stack.pop()
            pixels.append((y, x))
            r0 = rng[y, x]
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    if dx == 0 and dy == 0:
                        continue
                    ny, nx = y + dy, x + dx
                    if ny < 0 or ny >= RINGS or nx < 0 or nx >= COLS:
                        continue
                    if not mask[ny, nx] or labels[ny, nx] != -1:
                        continue
                    r1 = rng[ny, nx]
                    if abs(float(r1) - float(r0)) <= max(0.05, s["depth_jump"] * float(r0)):
                        labels[ny, nx] = cid
                        stack.append((ny, nx))
        if len(pixels) >= s["min_component"]:
            out.append(np.asarray(pixels, dtype=np.int32))
    return out


def component_features(pixels, grid, ground):
    rows = pixels[:, 0]
    cols = pixels[:, 1]
    x = grid.x[rows, cols].astype(np.float64)
    y = grid.y[rows, cols].astype(np.float64)
    z = grid.z[rows, cols].astype(np.float64)
    h = ground.height(x, y, z)
    p3 = ground.to_ground(x, y, z)
    count = int(len(x))
    cx, cy, cz = float(p3[:, 0].mean()), float(p3[:, 1].mean()), float(p3[:, 2].mean())
    dx = float(np.ptp(p3[:, 0]))
    dy = float(np.ptp(p3[:, 1]))
    dh = float(np.ptp(p3[:, 2]))
    h10, h50, h90 = [float(v) for v in np.percentile(h, [10, 50, 90])]
    angle = None
    axis_valid = False
    if count >= 8:
        centred = p3 - p3.mean(axis=0)
        cov = centred.T @ centred / count
        values, vectors = np.linalg.eigh(cov)
        if values[-1] > 1e-12 and values[-1] >= 1.2 * max(values[-2], 1e-12):
            axis = vectors[:, -1]
            angle = float(math.degrees(math.acos(min(1.0, abs(float(axis[2]))))))
            axis_valid = True
    return dict(
        count=count, cx=cx, cy=cy, cz=cz,
        x_min=float(p3[:, 0].min()), x_max=float(p3[:, 0].max()),
        y_min=float(p3[:, 1].min()), y_max=float(p3[:, 1].max()),
        z_min=float(p3[:, 2].min()), z_max=float(p3[:, 2].max()),
        width=float(max(dx, dy)), depth=float(min(dx, dy)), dz=dh,
        range_m=float(math.sqrt(float(x.mean()) ** 2 + float(y.mean()) ** 2
                                + float(z.mean()) ** 2)),
        height_p10=h10, height_p50=h50, height_p90=h90, height_span=float(h90 - h10),
        inclination_deg=angle, axis_valid=axis_valid,
        pixel_bbox=(int(rows.min()), int(rows.max()), int(cols.min()), int(cols.max())),
        pixels=pixels,
    )


def merge_components(features, settings):
    """Merge fragments that are close in 3D and still fit one standing body."""
    s = settings
    n = len(features)
    if n < 2:
        return [f["pixels"] for f in features]
    parent = list(range(n))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(i, j):
        ri, rj = find(i), find(j)
        if ri != rj:
            parent[rj] = ri

    for i in range(n):
        for j in range(i + 1, n):
            a, b = features[i], features[j]
            d = math.hypot(a["cx"] - b["cx"], a["cy"] - b["cy"])
            low_pair = a["z_max"] < 0.60 and b["z_max"] < 0.60
            gap = max(s["merge_gap"], 0.90 if low_pair else 0.0)
            if d > max(gap, 0.10 * min(a["range_m"], b["range_m"])):
                continue
            zmin = min(a["z_min"], b["z_min"])
            zmax = max(a["z_max"], b["z_max"])
            max_height = 1.00 if low_pair else s["merge_height"]
            if zmax - zmin > max_height:
                continue
            if max(a["width"], b["width"]) > s["merge_size"]:
                continue
            union(i, j)
    groups = {}
    for i in range(n):
        groups.setdefault(find(i), []).append(i)
    if len(groups) == n:
        return [features[i]["pixels"] for i in range(n)]
    merged = []
    for members in groups.values():
        pixels = np.vstack([features[k]["pixels"] for k in members])
        merged.append(pixels)
    return merged


class Track(object):
    def __init__(self, track_id, features, stamp):
        self.id = track_id
        self.features = features
        self.x = features["cx"]
        self.y = features["cy"]
        self.vx = 0.0
        self.vy = 0.0
        self.stamp = stamp
        self.hits = 1
        self.misses = 0
        self.trail = [(features["cx"], features["cy"])]

    def update(self, features, stamp):
        dt = stamp - self.stamp
        if dt > 1e-6:
            vx = (features["cx"] - self.x) / dt
            vy = (features["cy"] - self.y) / dt
            self.vx = 0.6 * self.vx + 0.4 * vx
            self.vy = 0.6 * self.vy + 0.4 * vy
        self.features = features
        self.x = features["cx"]
        self.y = features["cy"]
        self.stamp = stamp
        self.hits += 1
        self.misses = 0
        self.trail.append((features["cx"], features["cy"]))
        if len(self.trail) > 120:
            self.trail = self.trail[-120:]


class Tracker(object):
    def __init__(self, settings):
        self.s = settings
        self.tracks = []
        self.next_id = 1
        self.id_switches = 0
        self.last_target = None

    def update(self, features, stamp):
        used = set()
        for feat in features:
            best = None
            best_d = 1e9
            for track in self.tracks:
                if track.id in used:
                    continue
                gate = self.s["track_gate"] + self.s["track_max_speed"] * max(0.0, stamp - track.stamp)
                d = math.hypot(feat["cx"] - track.x, feat["cy"] - track.y)
                if d <= gate and d < best_d:
                    best, best_d = track, d
            if best is not None:
                best.update(feat, stamp)
                used.add(best.id)
            else:
                track = Track(self.next_id, feat, stamp)
                self.next_id += 1
                self.tracks.append(track)
                used.add(track.id)
        for track in list(self.tracks):
            if track.id not in used:
                track.misses += 1
            if stamp - track.stamp > self.s["track_max_miss"]:
                self.tracks.remove(track)
        return list(self.tracks)

    def choose(self):
        best = None
        best_score = -1e9
        for track in self.tracks:
            if track.hits < self.s["min_track_hits"]:
                continue
            f = track.features
            if f["height_p90"] < 0.15:
                continue
            if f["count"] < self.s["min_target_points"]:
                continue
            score = f["count"] + 200.0 * min(f["height_p90"], 2.0) - 50.0 * f["range_m"]
            if score > best_score:
                best, best_score = track, score
        if best is None:
            return None
        if self.last_target is not None and best.id != self.last_target:
            self.id_switches += 1
        self.last_target = best.id
        return best


class EventState(object):
    def __init__(self, settings):
        self.s = settings
        self.history = deque()
        self.count_history = deque()
        self.low_since = None
        self.active = None
        self.upright_since = None
        self.max_height = 0.0

    def update(self, stamp, features):
        s = self.s
        if features is None:
            self.history.clear()
            self.count_history.clear()
            self.low_since = None
            self.active = None
            self.upright_since = None
            return "unknown"
        height = features["height_p90"]
        span = features["height_span"]
        count = features["count"]
        self.history.append((stamp, height))
        self.count_history.append((stamp, count))
        while self.history and stamp - self.history[0][0] > 2.0:
            self.history.popleft()
        while self.count_history and stamp - self.count_history[0][0] > 10.0:
            self.count_history.popleft()
        peak_count = max(c for _, c in self.count_history) if self.count_history else count
        visible_ratio = count / float(max(1, peak_count))
        if count < s["min_event_points"] or visible_ratio < s["min_visible_ratio"]:
            # A fragment or a partially visible limb is not evidence of a fall.
            self.low_since = None
            return "low_support"
        peak = max(h for _, h in self.history) if self.history else height
        if peak > self.max_height:
            self.max_height = peak
        drop = peak - height
        rate = 0.0
        if len(self.history) >= 2:
            t0, h0 = self.history[0]
            if stamp > t0:
                rate = (h0 - height) / (stamp - t0)
        upright = height >= s["upright_height"] and span >= s["upright_span"]
        low = height <= s["low_height"] and span <= s["low_span"]
        descent = drop >= s["drop_m"] and rate >= s["drop_rate"]
        if upright:
            self.upright_since = stamp if self.upright_since is None else self.upright_since
            self.low_since = None
            if self.active is not None and stamp - self.upright_since >= 1.0:
                self.active = None
                self.max_height = height
            return "upright"
        self.upright_since = None
        if low and (descent or self.active is not None):
            if self.low_since is None:
                self.low_since = stamp
            held = stamp - self.low_since
            if held + 1e-9 >= s["long_lie_s"]:
                self.active = "long_lie_suspected"
                return "long_lie_suspected"
            if held + 1e-9 >= s["fall_hold_s"]:
                self.active = "fall_suspected"
                return "fall_suspected"
            return "descending"
        if low:
            self.low_since = None
            return "low_no_descent"
        if self.active is not None:
            return self.active
        return "transition"


def iter_session(session, transform=None, settings=None, max_frames=None,
                 background=None, ground=None):
    s = dict(DEFAULTS)
    s.update(settings or {})
    meta, points = load_session(session)
    if background is None:
        background = Background.from_session(meta, points, s["background_prefix"])
    if ground is None:
        ground = (Ground.from_transform(transform) if transform
                  else Ground.fit(meta, points, s["background_prefix"]))
    tracker = Tracker(s)
    event = EventState(s)
    hmm = FallHMM(min_event_points=s["min_event_points"],
                  min_visible_ratio=s["min_visible_ratio"],
                  fall_hold_s=s["fall_hold_s"], long_lie_s=s["long_lie_s"])
    t0 = meta["frames"][0]["bag_time_sec"]
    total = len(meta["frames"]) if max_frames is None else min(max_frames, len(meta["frames"]))
    for i in range(total):
        started = time.perf_counter()
        raw = read_raw(meta, points, i)
        grid = raw_to_grid(raw)
        mask = foreground_mask(grid, background, ground, s)
        comps = components(mask, grid.range, s)
        feats = [component_features(p, grid, ground) for p in comps]
        merged = merge_components(feats, s)
        feats = [component_features(p, grid, ground) for p in merged]
        stamp = float(meta["frames"][i]["bag_time_sec"] - t0)
        tracks = tracker.update(feats, stamp)
        target = tracker.choose()
        state = event.update(stamp, target.features if target is not None else None)
        hmm_result = hmm.update(stamp, target.features if target is not None else None)
        yield dict(
            index=i, stamp=stamp, grid=grid, mask=mask, components=comps,
            features=feats, tracks=tracks, target=target, state=state,
            hmm_state=hmm_result["state"], hmm_probs=hmm_result["probabilities"],
            hmm_fall=hmm_result["fall_suspected"],
            hmm_long_lie=hmm_result["long_lie_suspected"],
            background=background, ground=ground, id_switches=tracker.id_switches,
            elapsed_ms=(time.perf_counter() - started) * 1000.0,
        )


def _target_features(target):
    if target is None:
        return None
    if hasattr(target, "features"):
        return target.features
    return target


def summarize(records, id_switches=None):
    states = Counter(r["state"] for r in records)
    target_frames = [r for r in records if _target_features(r.get("target")) is not None]
    lat = np.asarray([r.get("elapsed_ms", 0.0) for r in records], dtype=np.float64)
    if target_frames:
        feats = [_target_features(r["target"]) for r in target_frames]
        points = np.asarray([f["count"] for f in feats], dtype=np.float64)
        ranges = np.asarray([f["range_m"] for f in feats], dtype=np.float64)
        heights = np.asarray([f["height_p90"] for f in feats], dtype=np.float64)
        spans = np.asarray([f["height_span"] for f in feats], dtype=np.float64)
        comps = np.asarray([r.get("n_comp", len(r.get("features", []))) for r in records], dtype=np.float64)
        summary = dict(
            frames=len(records), target_frames=len(target_frames),
            target_ratio=round(len(target_frames) / max(1, len(records)), 4),
            target_points_median=int(np.median(points)),
            target_range_median_m=round(float(np.median(ranges)), 3),
            target_height_median_m=round(float(np.median(heights)), 3),
            target_span_median_m=round(float(np.median(spans)), 3),
            components_median=float(np.median(comps)),
        )
    else:
        summary = dict(frames=len(records), target_frames=0, target_ratio=0.0)
    summary.update(
        states=dict(states),
        hmm_states=dict(Counter(r.get("hmm_state", "unknown") for r in records)),
        hmm_fall_frames=int(sum(1 for r in records if r.get("hmm_fall"))),
        hmm_long_lie_frames=int(sum(1 for r in records if r.get("hmm_long_lie"))),
        latency_ms=dict(p50=round(float(np.percentile(lat, 50)), 2),
                        p95=round(float(np.percentile(lat, 95)), 2)),
        id_switches=id_switches,
    )
    return summary


def _record(fr):
    target = fr["target"]
    return dict(
        index=fr["index"], stamp=round(float(fr["stamp"]), 3),
        n_fg=int(fr["mask"].sum()), n_comp=len(fr["features"]),
        n_tracks=len(fr["tracks"]), state=fr["state"],
        elapsed_ms=round(float(fr["elapsed_ms"]), 3),
        id_switches=int(fr["id_switches"]),
        hmm_state=fr.get("hmm_state", "unknown"),
        hmm_p_lying=round(float(fr.get("hmm_probs", {}).get("lying", 0.0)), 4),
        hmm_fall=bool(fr.get("hmm_fall")),
        hmm_long_lie=bool(fr.get("hmm_long_lie")),
        target=None if target is None else dict(
            id=target.id, count=target.features["count"],
            range_m=round(target.features["range_m"], 3),
            height_p90=round(target.features["height_p90"], 3),
            height_span=round(target.features["height_span"], 3),
            inclination_deg=target.features["inclination_deg"],
            pixel_bbox=target.features["pixel_bbox"],
        ),
    )


def _collect(iterator):
    records = [_record(fr) for fr in iterator]
    switches = records[-1]["id_switches"] if records else 0
    return records, summarize(records, id_switches=switches)


def process_session(session, transform=None, settings=None, max_frames=None):
    return _collect(iter_session(session, transform=transform, settings=settings,
                                 max_frames=max_frames))


def _largest_person(meta, points, index, background, ground, settings):
    raw = read_raw(meta, points, index)
    grid = raw_to_grid(raw)
    mask = foreground_mask(grid, background, ground, settings)
    comps = components(mask, grid.range, settings)
    feats = [component_features(p, grid, ground) for p in comps]
    if not feats:
        raise ValueError("no foreground person in frame %d" % index)
    best = max(feats, key=lambda f: f["count"])
    rows = best["pixels"][:, 0]
    cols = best["pixels"][:, 1]
    return (grid.x[rows, cols].astype(np.float64),
            grid.y[rows, cols].astype(np.float64),
            grid.z[rows, cols].astype(np.float64))


def iter_synthetic_fall(session, transform=None, settings=None,
                        person_frame=183, empty_frame=50,
                        stand_frames=20, fall_frames=15, lie_frames=60,
                        recover_frames=15, after_frames=10):
    """Rigid-body fall built from a real standing person + a real empty frame.

    This is a controlled algorithm test, not a human fall and not evidence of
    fall performance. It exists so the demo can show the state machine firing
    on a height collapse, with the same range-image front-end.
    """
    s = dict(DEFAULTS)
    s.update(settings or {})
    meta, points = load_session(session)
    background = Background.from_session(meta, points, s["background_prefix"])
    ground = (Ground.from_transform(transform) if transform
              else Ground.fit(meta, points, s["background_prefix"]))
    base = read_raw(meta, points, empty_frame)
    bx = base["x"].astype(np.float64)
    by = base["y"].astype(np.float64)
    bz = base["z"].astype(np.float64)
    bring = base["ring"].astype(np.int64)
    bint = base["intensity"].astype(np.float64)

    px, py, pz = _largest_person(meta, points, person_frame, background, ground, s)
    pground = ground.to_ground(px, py, pz)
    pivot = np.array([pground[:, 0].mean(), pground[:, 1].mean(), pground[:, 2].min()])
    tracker = Tracker(s)
    event = EventState(s)
    hmm = FallHMM(min_event_points=s["min_event_points"],
                  min_visible_ratio=s["min_visible_ratio"],
                  fall_hold_s=s["fall_hold_s"], long_lie_s=s["long_lie_s"])
    total = stand_frames + fall_frames + lie_frames + recover_frames + after_frames
    for i in range(total):
        started = time.perf_counter()
        if i < stand_frames:
            theta = 0.0
        elif i < stand_frames + fall_frames:
            theta = (i - stand_frames + 1) / float(fall_frames) * (math.pi / 2.0)
        elif i < stand_frames + fall_frames + lie_frames:
            theta = math.pi / 2.0
        elif i < stand_frames + fall_frames + lie_frames + recover_frames:
            k = i - (stand_frames + fall_frames + lie_frames)
            theta = (1.0 - (k + 1) / float(recover_frames)) * (math.pi / 2.0)
        else:
            theta = 0.0
        c, sn = math.cos(theta), math.sin(theta)
        q = pground - pivot
        q2 = np.column_stack((q[:, 0], q[:, 1] * c - q[:, 2] * sn,
                              q[:, 1] * sn + q[:, 2] * c))
        p2 = q2 + pivot
        # A rigid rotation about the feet can put half the body below the
        # floor. Lift it so the lowest point sits just above the ground; this
        # is a synthetic-composition constraint, not a measurement.
        p2[:, 2] += 0.02 - p2[:, 2].min()
        raw_person = ground.from_ground(p2)

        x = np.concatenate((bx, raw_person[:, 0]))
        y = np.concatenate((by, raw_person[:, 1]))
        z = np.concatenate((bz, raw_person[:, 2]))
        el = np.degrees(np.arctan2(raw_person[:, 2], np.hypot(raw_person[:, 0], raw_person[:, 1])))
        ring_person = np.rint((el - EL0) / DEL).astype(np.int64)
        ring_person = np.clip(ring_person, 0, RINGS - 1)
        ring = np.concatenate((bring, ring_person))
        intensity = np.concatenate((bint, np.full(len(raw_person), 800.0)))
        grid = to_grid(x, y, z, ring, intensity)
        mask = foreground_mask(grid, background, ground, s)
        comps = components(mask, grid.range, s)
        feats = [component_features(p, grid, ground) for p in comps]
        merged = merge_components(feats, s)
        feats = [component_features(p, grid, ground) for p in merged]
        stamp = i * 0.1
        tracks = tracker.update(feats, stamp)
        target = tracker.choose()
        state = event.update(stamp, target.features if target is not None else None)
        hmm_result = hmm.update(stamp, target.features if target is not None else None)
        yield dict(
            index=i, stamp=stamp, grid=grid, mask=mask, components=comps,
            features=feats, tracks=tracks, target=target, state=state,
            hmm_state=hmm_result["state"], hmm_probs=hmm_result["probabilities"],
            hmm_fall=hmm_result["fall_suspected"],
            hmm_long_lie=hmm_result["long_lie_suspected"],
            background=background, ground=ground, id_switches=tracker.id_switches,
            elapsed_ms=(time.perf_counter() - started) * 1000.0,
        )


def process_synthetic_fall(session, transform=None, settings=None, **kwargs):
    settings = dict(settings or {})
    settings.setdefault("long_lie_s", 5.0)
    return _collect(iter_synthetic_fall(session, transform=transform, settings=settings,
                                        **kwargs))


def _segment_points(p0, p1, radius, count, rng):
    p0 = np.asarray(p0, dtype=np.float64)
    p1 = np.asarray(p1, dtype=np.float64)
    axis = p1 - p0
    length = float(np.linalg.norm(axis))
    if length < 1e-9:
        return np.zeros((0, 3))
    axis = axis / length
    helper = np.array([0.0, 1.0, 0.0]) if abs(axis[1]) < 0.9 else np.array([1.0, 0.0, 0.0])
    u = np.cross(axis, helper)
    u /= np.linalg.norm(u)
    v = np.cross(axis, u)
    t = rng.random(count)
    ang = rng.random(count) * 2.0 * math.pi
    rad = radius * np.sqrt(rng.random(count))
    return (p0 + t[:, None] * (axis * length)[None, :]
            + (rad * np.cos(ang))[:, None] * u[None, :]
            + (rad * np.sin(ang))[:, None] * v[None, :])


def _capsule_body(seed=7):
    """A crude standing body (capsules), not a human model or a capture."""
    rng = np.random.default_rng(seed)
    parts = [
        _segment_points([0, 0, 0.90], [0, 0, 1.45], 0.18, 480, rng),   # torso
        _segment_points([0.22, 0, 1.42], [0.36, 0.06, 0.85], 0.060, 140, rng),
        _segment_points([-0.22, 0, 1.42], [-0.36, 0.06, 0.85], 0.060, 140, rng),
        _segment_points([0.10, 0, 0.90], [0.12, 0.02, 0.05], 0.085, 300, rng),
        _segment_points([-0.10, 0, 0.90], [-0.12, 0.02, 0.05], 0.085, 300, rng),
    ]
    sphere = rng.normal(size=(220, 3))
    sphere /= np.linalg.norm(sphere, axis=1)[:, None]
    sphere *= (0.11 * np.cbrt(rng.random(220)))[:, None]
    sphere += np.array([0.0, 0.0, 1.62])
    parts.append(sphere)
    body = np.vstack(parts)
    body[:, 0] += 1.40
    body[:, 1] += 1.20
    return body


def iter_synthetic_capsule_fall(session, transform=None, settings=None, empty_frame=50,
                                stand_frames=20, fall_frames=15, lie_frames=60,
                                recover_frames=15, after_frames=10):
    """Controlled capsule fall injected into a real empty scene.

    This is an algorithm demo: the body is a crude capsule model, not a human
    and not a capture. It is useful for checking the state machine and the
    range-image front-end on a known height collapse; it is not evidence.
    """
    s = dict(DEFAULTS)
    s.update(settings or {})
    meta, points = load_session(session)
    background = Background.from_session(meta, points, s["background_prefix"])
    ground = (Ground.from_transform(transform) if transform
              else Ground.fit(meta, points, s["background_prefix"]))
    base = read_raw(meta, points, empty_frame)
    bx = base["x"].astype(np.float64)
    by = base["y"].astype(np.float64)
    bz = base["z"].astype(np.float64)
    bring = base["ring"].astype(np.int64)
    bint = base["intensity"].astype(np.float64)
    body = _capsule_body()
    pivot = np.array([float(body[:, 0].mean()), float(body[:, 1].mean()), 0.0])
    tracker = Tracker(s)
    event = EventState(s)
    hmm = FallHMM(min_event_points=s["min_event_points"],
                  min_visible_ratio=s["min_visible_ratio"],
                  fall_hold_s=s["fall_hold_s"], long_lie_s=s["long_lie_s"])
    total = stand_frames + fall_frames + lie_frames + recover_frames + after_frames
    for i in range(total):
        started = time.perf_counter()
        if i < stand_frames:
            theta = 0.0
        elif i < stand_frames + fall_frames:
            theta = (i - stand_frames + 1) / float(fall_frames) * (math.pi / 2.0)
        elif i < stand_frames + fall_frames + lie_frames:
            theta = math.pi / 2.0
        elif i < stand_frames + fall_frames + lie_frames + recover_frames:
            k = i - (stand_frames + fall_frames + lie_frames)
            theta = (1.0 - (k + 1) / float(recover_frames)) * (math.pi / 2.0)
        else:
            theta = 0.0
        c, sn = math.cos(theta), math.sin(theta)
        q = body - pivot
        q2 = np.column_stack((q[:, 0], q[:, 1] * c - q[:, 2] * sn,
                              q[:, 1] * sn + q[:, 2] * c))
        p2 = q2 + pivot
        p2[:, 2] += 0.03 - p2[:, 2].min()
        raw_person = ground.from_ground(p2)
        x = np.concatenate((bx, raw_person[:, 0]))
        y = np.concatenate((by, raw_person[:, 1]))
        z = np.concatenate((bz, raw_person[:, 2]))
        el = np.degrees(np.arctan2(raw_person[:, 2], np.hypot(raw_person[:, 0], raw_person[:, 1])))
        ring_person = np.clip(np.rint((el - EL0) / DEL).astype(np.int64), 0, RINGS - 1)
        ring = np.concatenate((bring, ring_person))
        intensity = np.concatenate((bint, np.full(len(raw_person), 800.0)))
        grid = to_grid(x, y, z, ring, intensity)
        mask = foreground_mask(grid, background, ground, s)
        comps = components(mask, grid.range, s)
        feats = [component_features(p, grid, ground) for p in comps]
        merged = merge_components(feats, s)
        feats = [component_features(p, grid, ground) for p in merged]
        stamp = i * 0.1
        tracks = tracker.update(feats, stamp)
        target = tracker.choose()
        state = event.update(stamp, target.features if target is not None else None)
        hmm_result = hmm.update(stamp, target.features if target is not None else None)
        yield dict(
            index=i, stamp=stamp, grid=grid, mask=mask, components=comps,
            features=feats, tracks=tracks, target=target, state=state,
            hmm_state=hmm_result["state"], hmm_probs=hmm_result["probabilities"],
            hmm_fall=hmm_result["fall_suspected"],
            hmm_long_lie=hmm_result["long_lie_suspected"],
            background=background, ground=ground, id_switches=tracker.id_switches,
            elapsed_ms=(time.perf_counter() - started) * 1000.0,
        )


def process_synthetic_capsule_fall(session, transform=None, settings=None, **kwargs):
    settings = dict(settings or {})
    settings.setdefault("long_lie_s", 5.0)
    return _collect(iter_synthetic_capsule_fall(session, transform=transform,
                                                settings=settings, **kwargs))