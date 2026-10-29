"""Explicit GT crop and observed-target windows. NumPy only; no semantic claims."""
from collections import deque
import hashlib
import math

import numpy as np


def xyz(value, minimum=1):
    points = np.asarray(value, dtype=np.float64)
    if (points.ndim != 2 or points.shape[1] != 3 or len(points) < minimum or
            not np.isfinite(points).all() or
            np.any(np.abs(points) > np.finfo(np.float32).max)):
        raise ValueError('Expected finite float32-representable N,3 points')
    return points


def transform_joints(joints, matrix):
    """Column-vector convention: lidar_xyz = R @ joint_xyz + t, same units."""
    joints = xyz(joints)
    matrix = np.asarray(matrix, dtype=np.float64)
    if (matrix.shape != (4, 4) or not np.isfinite(matrix).all() or
            not np.allclose(matrix[3], [0, 0, 0, 1], atol=1e-10, rtol=0) or
            not np.allclose(matrix[:3, :3].T @ matrix[:3, :3], np.eye(3), atol=1e-6, rtol=0) or
            not np.isclose(np.linalg.det(matrix[:3, :3]), 1, atol=1e-6, rtol=0)):
        raise ValueError('Expected a proper rigid joint-to-LiDAR transform; units must already match')
    return xyz(joints @ matrix[:3, :3].T + matrix[:3, 3])


def crop_rows(points, joints, matrix, margin=0.25):
    """Expanded joint AABB, inclusive boundary; returns original source row IDs.

    This is an oracle diagnostic envelope, not point-level person ground truth.
    No recentering, rescaling, nearest-cluster rescue or scene fallback is applied.
    """
    points = xyz(points)
    if not math.isfinite(margin) or margin < 0:
        raise ValueError('Expected finite nonnegative margin in input units')
    aligned = transform_joints(joints, matrix)
    lo, hi = aligned.min(0) - margin, aligned.max(0) + margin
    return np.flatnonzero(np.all((points >= lo) & (points <= hi), axis=1))


def sample_rows(points, count, source_key):
    """Same source-name seed rule as the frozen whole-scene deep baseline."""
    points = xyz(points, minimum=10)
    if not isinstance(count, int) or isinstance(count, bool) or count < 1:
        raise ValueError('Expected positive integer point budget')
    if not isinstance(source_key, str) or not source_key:
        raise ValueError('Missing deterministic source key')
    seed = int.from_bytes(hashlib.sha256(source_key.encode()).digest()[:8], 'little')
    return np.random.default_rng(seed).choice(len(points), count, replace=len(points) < count)


def valid_binding(value):
    if isinstance(value, tuple):
        return bool(value) and all(valid_binding(item) for item in value)
    return isinstance(value, (str, int, np.integer)) and not isinstance(value, bool) and value != ''


class TargetPointCache:
    """Only measured locked target rows enter history; invalid observations clear it."""
    def __init__(self, window=30, points=256, max_gap_s=0.5):
        if (not isinstance(window, int) or isinstance(window, bool) or window < 1 or
                not isinstance(points, int) or isinstance(points, bool) or points < 1 or
                not math.isfinite(max_gap_s) or max_gap_s <= 0):
            raise ValueError('Invalid window/point budget/gap')
        self.window, self.points, self.max_gap_s = window, points, max_gap_s
        self.frames = deque(maxlen=window)
        self.clear()

    def clear(self):
        self.frames.clear()
        self.key = self.last_time = None
        self.last_sample_rows = np.empty(0, dtype=np.int64)

    def push(self, cloud, source_rows, timestamp, identity, generation, calibration,
             source_key, locked=True, predicted=False):
        if not locked or predicted:
            self.clear()
            return None
        try:
            cloud = xyz(cloud)
            rows = np.asarray(source_rows)
            if (rows.ndim != 1 or rows.dtype.kind not in 'iu' or len(rows) < 10 or
                    len(np.unique(rows)) != len(rows) or (rows < 0).any() or
                    (rows >= len(cloud)).any() or
                    not all(valid_binding(value) for value in (identity, generation, calibration)) or
                    not math.isfinite(timestamp)):
                raise ValueError('Invalid target rows or stream binding')
            local = sample_rows(cloud[rows], self.points, source_key)
        except (TypeError, ValueError, OverflowError):
            self.clear()
            raise ValueError('Invalid target observation; causal history cleared')
        key = (identity, generation, calibration)
        if (key != self.key or self.last_time is None or timestamp <= self.last_time or
                timestamp - self.last_time > self.max_gap_s):
            self.clear()
        self.key, self.last_time = key, timestamp
        self.last_sample_rows = rows[local].astype(np.int64, copy=True)
        self.frames.append(cloud[self.last_sample_rows].astype(np.float32))
        return np.stack(self.frames) if len(self.frames) == self.window else None
