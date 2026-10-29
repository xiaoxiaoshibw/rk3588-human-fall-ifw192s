"""Causal angular range-change cue; NOT a background or human classifier.

Only a nearer return in an angular bin with repeated older farther returns is
supported. No-return is unknown. Bin quantization, motion of the sensor and
occlusion still limit interpretation; callers must not use this as point GT.
"""
from collections import deque

import numpy as np


class VisibilityChange:
    def __init__(self, angular_deg=0.5, margin_m=0.2, history_s=0.8, min_views=3):
        if not 0 < angular_deg <= 5 or margin_m <= 0 or history_s <= 0 or min_views < 1:
            raise ValueError('positive bounded change-cue parameters required')
        self.angle = float(angular_deg)
        self.margin = float(margin_m)
        self.history_s = float(history_s)
        self.min_views = int(min_views)
        self.n_azimuth = int(np.ceil(360 / angular_deg))
        self.n_elevation = int(np.ceil(180 / angular_deg))
        self.history = deque()
        self.last = None
        self.binding = None

    def step(self, xyz, stamp, binding):
        points = np.asarray(xyz, dtype=float)
        if points.ndim != 2 or points.shape[1] != 3 or not np.isfinite(points).all() \
                or not np.isfinite(stamp):
            self.history.clear(); self.last = None
            raise ValueError('finite source frame and time required')
        if self.binding != binding or self.last is not None and (
                stamp <= self.last or stamp - self.last > self.history_s):
            self.history.clear()
        self.binding, self.last = binding, stamp
        while self.history and stamp - self.history[0][0] > self.history_s:
            self.history.popleft()
        radius = np.linalg.norm(points, axis=1)
        if np.any(radius <= 0):
            self.history.clear()
            raise ValueError('zero rays have no angular observation')
        azimuth = np.degrees(np.arctan2(points[:, 1], points[:, 0]))
        elevation = np.degrees(np.arctan2(points[:, 2], np.linalg.norm(points[:, :2], axis=1)))
        a = np.floor((azimuth + 180) / self.angle).astype(int) % self.n_azimuth
        e = np.minimum(self.n_elevation - 1, np.floor((elevation + 90) / self.angle).astype(int))
        bins = e * self.n_azimuth + a
        current = np.full(self.n_azimuth * self.n_elevation, np.inf)
        np.minimum.at(current, bins, radius)
        seen = np.zeros(len(points), dtype=int)
        nearest = np.full(len(points), np.inf)
        for _, old in self.history:
            old_ranges = old[bins]
            seen += np.isfinite(old_ranges)
            nearest = np.minimum(nearest, old_ranges)
        support = (seen >= self.min_views) & (nearest > radius + self.margin)
        # Compare BEFORE storing this frame; no future or same-frame evidence.
        self.history.append((float(stamp), current))
        return support, seen
