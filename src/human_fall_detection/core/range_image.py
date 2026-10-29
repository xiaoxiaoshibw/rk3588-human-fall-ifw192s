"""标定表驱动的距离图；仅 stdlib + NumPy，不插值或重建测量点。"""
import hashlib
import json
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .capture_input import ROW_DTYPE


class ScanGrid:
    """原生 ring/column 表；列方向可递增或递减，不能用等角取整替代。"""

    def __init__(self, azimuth_deg, elevation_deg, tolerance_deg=0.02):
        az = np.array(azimuth_deg, dtype=np.float64, copy=True)
        el = np.array(elevation_deg, dtype=np.float64, copy=True)
        tolerance = float(tolerance_deg)
        if (az.ndim != 2 or min(az.shape) < 2 or az.shape != el.shape
                or not np.isfinite(az).all() or not np.isfinite(el).all()
                or (np.abs(az) >= 180).any() or (np.abs(el) > 90).any()
                or not np.isfinite(tolerance) or tolerance <= 0):
            raise ValueError('invalid direction table or tolerance')
        order = np.argsort(az, axis=1)
        sorted_az = np.take_along_axis(az, order, axis=1)
        if (np.diff(sorted_az, axis=1) <= 2 * tolerance).any():
            raise ValueError('azimuth directions are ambiguous within tolerance')
        if not ((np.diff(az, axis=1) > 0).all()
                or (np.diff(az, axis=1) < 0).all()):
            raise ValueError('columns must have a consistent angular order')
        self.shape, self.tolerance_deg = az.shape, tolerance
        self.azimuth_deg, self.elevation_deg = az, el
        self._keys = (sorted_az + 360 * np.arange(az.shape[0])[:, None]).ravel()
        self._cells = (order + az.shape[1] * np.arange(az.shape[0])[:, None]).ravel()
        # 厘度查表只加速候选列搜索；最终仍用原标定角及容差核对。
        self._lookup_low = int(np.floor(az.min() * 100)) - 2
        width = int(np.ceil(az.max() * 100)) - self._lookup_low + 3
        self._lookup = np.full((az.shape[0], width), -1, dtype=np.int32)
        ring, col = np.indices(az.shape)
        centres = np.rint(az * 100).astype(np.int64) - self._lookup_low
        for delta in range(-int(np.ceil(tolerance * 100)) - 1,
                           int(np.ceil(tolerance * 100)) + 2):
            bins = centres + delta
            ok = (bins >= 0) & (bins < width)
            self._lookup[ring[ok], bins[ok]] = col[ok]
        digest = hashlib.sha256()
        for values in (az, el):
            digest.update(values.astype('<f8').tobytes())
        digest.update(json.dumps(dict(shape=az.shape, tolerance_deg=tolerance), sort_keys=True).encode())
        self.sha256 = digest.hexdigest()
        for values in (az, el, self._keys, self._cells, self._lookup):
            values.flags.writeable = False

    @classmethod
    def from_csv(cls, azimuth_path, elevation_path, tolerance_deg=0.02):
        return cls(np.loadtxt(Path(azimuth_path), delimiter=','),
                   np.loadtxt(Path(elevation_path), delimiter=','), tolerance_deg)

    def decode(self, packed, binding, timings=None):
        """确定性最近回波；同距离取最小帧内行，所有排除行均保留。"""
        tick = time.perf_counter() if timings is not None else None
        def mark(name):
            nonlocal tick
            if timings is not None:
                now = time.perf_counter()
                timings[name] = (now-tick)*1000
                tick = now
        if not isinstance(binding, tuple) or not binding:
            raise ValueError('an explicit stream/frame/calibration binding is required')
        if isinstance(packed, (bytes, bytearray, memoryview)):
            if len(packed) % ROW_DTYPE.itemsize:
                raise ValueError('truncated 28-byte point record')
            packed = np.frombuffer(packed, dtype=ROW_DTYPE)
        if not isinstance(packed, np.ndarray) or packed.ndim != 1 or packed.dtype != ROW_DTYPE:
            raise ValueError('expected capture_input.ROW_DTYPE rows')
        mark('decode_frombuffer_ms')
        xyz = np.lib.stride_tricks.as_strided(packed['x'], shape=(len(packed), 3),
                                            strides=(packed.strides[0], 4), writeable=False)
        x, y, z = (packed[name].astype(np.float64) for name in ('x', 'y', 'z'))
        mark('decode_xyz_ms')
        ranges = np.sqrt(x*x + y*y + z*z)
        finite = np.isfinite(ranges)
        positive = np.zeros(len(ranges), dtype=bool)
        positive[finite] = ranges[finite] > 0.1
        rings = packed['ring'].astype(np.int64)
        eligible = positive & (rings < self.shape[0])
        rows = np.flatnonzero(eligible)
        mark('decode_range_filter_ms')
        az = np.degrees(np.arctan2(y[rows], x[rows]))
        el = np.degrees(np.arctan2(z[rows], np.hypot(x[rows], y[rows])))
        mark('decode_angles_ms')
        bins = np.rint(az * 100).astype(np.int64) - self._lookup_low
        in_lookup = (bins >= 0) & (bins < self._lookup.shape[1])
        columns = self._lookup[rings[rows], np.clip(bins, 0, self._lookup.shape[1] - 1)]
        cells = rings[rows] * self.shape[1] + np.maximum(columns, 0)
        known = (in_lookup & (columns >= 0)
                 & (np.abs(self.azimuth_deg.ravel()[cells] - az) <= self.tolerance_deg)
                 & (np.abs(self.elevation_deg.ravel()[cells] - el) <= self.tolerance_deg))
        # 密角表的厘度bin可能交叠；失败候选用精确最近方向搜索兜底。
        if not known.all():
            bad = np.flatnonzero(~known)
            query = az[bad] + 360 * rings[rows[bad]]
            right = np.minimum(np.searchsorted(self._keys, query), len(self._keys)-1)
            left = np.maximum(right-1, 0)
            nearest = np.where(np.abs(self._keys[left]-query) <= np.abs(self._keys[right]-query), left, right)
            candidate = self._cells[nearest]
            accepted = ((candidate // self.shape[1] == rings[rows[bad]])
                        & (np.abs(self.azimuth_deg.ravel()[candidate]-az[bad]) <= self.tolerance_deg)
                        & (np.abs(self.elevation_deg.ravel()[candidate]-el[bad]) <= self.tolerance_deg))
            cells[bad[accepted]] = candidate[accepted]
            known[bad[accepted]] = True
        unknown_rows = rows[~known]
        rows, cells = rows[known], cells[known]
        mark('decode_lookup_ms')
        # 排序仅在真实重复回波存在时发生；常规单回波帧保持线性开销。
        counts = np.bincount(cells, minlength=np.prod(self.shape))
        duplicate_rows = np.empty(0, dtype=np.int64)
        if (counts > 1).any():
            order = np.lexsort((rows, ranges[rows], cells))
            ordered_cells = cells[order]
            first = np.r_[True, ordered_cells[1:] != ordered_cells[:-1]]
            duplicate_rows = rows[order[~first]]
            rows, cells = rows[order[first]], cells[order[first]]
        mark('decode_duplicates_ms')
        source_rows = np.full(self.shape, -1, dtype=np.int64)
        source_rows.ravel()[cells] = rows
        image = np.full(self.shape, np.nan)
        image.ravel()[cells] = ranges[rows]
        intensity, point_time = np.full(self.shape, np.nan), np.full(self.shape, np.nan)
        intensity.ravel()[cells] = packed['intensity'][rows]
        point_time.ravel()[cells] = packed['timestamp'][rows]
        time_valid = np.isfinite(point_time)
        n = time_valid.sum(axis=1)
        row_time = np.full(self.shape[0], np.nan)
        row_time[n > 0] = np.where(time_valid, point_time, 0).sum(axis=1)[n > 0] / n[n > 0]
        rejected = dict(nonfinite_rows=np.flatnonzero(~finite),
                        zero_or_near_rows=np.flatnonzero(finite & ~positive),
                        invalid_ring_rows=np.flatnonzero(positive & ~eligible),
                        unknown_direction_rows=unknown_rows, duplicate_rows=duplicate_rows)
        mark('decode_fill_ms')
        return RangeFrame(self, binding, xyz, image, source_rows >= 0, source_rows,
                          intensity, point_time, row_time, rejected)


@dataclass
class RangeFrame:
    grid: ScanGrid
    binding: tuple
    xyz: np.ndarray
    range_m: np.ndarray
    valid: np.ndarray
    source_rows: np.ndarray
    intensity: np.ndarray
    point_time_s: np.ndarray
    row_time_s: np.ndarray  # 已存储时间的逐行均值；不是去畸变或精确扫描时间。
    rejected: dict
