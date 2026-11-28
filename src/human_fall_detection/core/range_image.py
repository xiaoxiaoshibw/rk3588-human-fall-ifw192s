"""标定表驱动的距离图；仅 stdlib + NumPy，不插值或重建测量点。"""
import hashlib
import json
import math
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
        self._az_flat = az.ravel()
        self._el_flat = el.ravel()
        self._n_cells = int(az.size)
        self._keys = (sorted_az + 360 * np.arange(az.shape[0])[:, None]).ravel()
        self._cells = (order + az.shape[1] * np.arange(az.shape[0])[:, None]).ravel()
        # 紧凑半角正切查表 + 代数正余弦内点核验（跳过常规射线的 atan2/hypot），
        # 任何边界/未命中点一律回落到精确 atan2 + searchsorted，保证结果逐位等价。
        az_rad = np.radians(az)
        el_rad = np.radians(el)
        self._cos_az = np.cos(az_rad).ravel()
        self._sin_az = np.sin(az_rad).ravel()
        self._cos_el = np.cos(el_rad).ravel()
        self._sin_el = np.sin(el_rad).ravel()
        self._tan_tol_safe = (
            math.tan(math.radians(tolerance - 1e-6)) if tolerance > 1e-6 else -1.0
        )
        self._u_lut = None
        self._u_low = 0.0
        self._inv_u_step = 0.0
        self._u_bins = 0
        if (np.abs(az) < 150.0).all() and az.shape[1] <= 32767:
            u_table = np.tan(az_rad * 0.5)
            sorted_u = np.take_along_axis(u_table, order, axis=1)
            min_u_gap = float(np.min(np.diff(sorted_u, axis=1)))
            if min_u_gap > 0.0:
                u_step = min(0.002, max(1e-5, min_u_gap / 3.0))
                u_low = float(u_table.min()) - 2.0 * u_step
                u_bins = int(math.ceil((float(u_table.max()) - u_low) / u_step)) + 3
                if u_bins <= 65536:
                    u_lut = np.full((az.shape[0], u_bins), -1, dtype=np.int16)
                    u_tol = math.radians(tolerance) * 0.5 * (1.0 + float(np.max(u_table * u_table)))
                    delta_bins = int(math.ceil(u_tol / u_step)) + 1
                    ring, col = np.indices(az.shape)
                    centres = np.rint((u_table - u_low) / u_step).astype(np.int64)
                    for delta in range(-delta_bins, delta_bins + 1):
                        bins = centres + delta
                        ok = (bins >= 0) & (bins < u_bins)
                        u_lut[ring[ok], bins[ok]] = col[ok]
                    u_lut.flags.writeable = False
                    self._u_lut = u_lut
                    self._u_low = u_low
                    self._inv_u_step = 1.0 / u_step
                    self._u_bins = u_bins
        digest = hashlib.sha256()
        for values in (az, el):
            digest.update(values.astype('<f8').tobytes())
        digest.update(json.dumps(dict(shape=az.shape, tolerance_deg=tolerance), sort_keys=True).encode())
        self.sha256 = digest.hexdigest()
        for values in (az, el, self._keys, self._cells,
                       self._cos_az, self._sin_az, self._cos_el, self._sin_el):
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
        x = packed['x'].astype(np.float64)
        y = packed['y'].astype(np.float64)
        z = packed['z'].astype(np.float64)
        mark('decode_xyz_ms')
        xy2 = x * x + y * y
        ranges = np.sqrt(xy2 + z * z)
        finite = np.isfinite(ranges)
        positive = np.zeros(len(ranges), dtype=bool)
        positive[finite] = ranges[finite] > 0.1
        rings = packed['ring'].astype(np.int64)
        eligible = positive & (rings < self.shape[0])
        rows = np.flatnonzero(eligible)
        mark('decode_range_filter_ms')
        w_cols = self.shape[1]
        if len(rows) == 0:
            mark('decode_angles_ms')
            unknown_rows = np.empty(0, dtype=np.int64)
            cells = np.empty(0, dtype=np.int64)
            mark('decode_lookup_ms')
        elif self._u_lut is not None and self._tan_tol_safe > 0.0:
            xr = x[rows]
            yr = y[rows]
            zr = z[rows]
            rr = rings[rows]
            rho = np.sqrt(xy2[rows])
            denom = xr + rho
            valid_u = denom > 1e-12
            with np.errstate(divide='ignore', invalid='ignore'):
                u = yr / denom
            u_finite = valid_u & np.isfinite(u)
            bins = np.rint((np.where(u_finite, u, 0.0) - self._u_low) * self._inv_u_step).astype(np.int64)
            in_lut = u_finite & (bins >= 0) & (bins < self._u_bins)
            mark('decode_angles_ms')
            columns = self._u_lut[rr, np.clip(bins, 0, self._u_bins - 1)]
            cells = rr * w_cols + np.maximum(columns, 0)
            ca = self._cos_az[cells]
            sa = self._sin_az[cells]
            dot_xy = xr * ca + yr * sa
            cross_xy = yr * ca - xr * sa
            ce = self._cos_el[cells]
            se = self._sin_el[cells]
            dot_rz = rho * ce + zr * se
            cross_rz = zr * ce - rho * se
            known = (
                in_lut & (columns >= 0)
                & (dot_xy > 0.0) & (np.abs(cross_xy) <= dot_xy * self._tan_tol_safe)
                & (dot_rz > 0.0) & (np.abs(cross_rz) <= dot_rz * self._tan_tol_safe)
            )
            if not known.all():
                bad = np.flatnonzero(~known)
                xb, yb, zb, rb, rhob = xr[bad], yr[bad], zr[bad], rr[bad], rho[bad]
                az_b = np.degrees(np.arctan2(yb, xb))
                el_b = np.degrees(np.arctan2(zb, rhob))
                query = az_b + 360.0 * rb
                right = np.minimum(np.searchsorted(self._keys, query), len(self._keys) - 1)
                left = np.maximum(right - 1, 0)
                nearest = np.where(
                    np.abs(self._keys[left] - query) <= np.abs(self._keys[right] - query),
                    left,
                    right,
                )
                candidate = self._cells[nearest]
                accepted = (
                    (candidate // w_cols == rb)
                    & (np.abs(self._az_flat[candidate] - az_b) <= self.tolerance_deg)
                    & (np.abs(self._el_flat[candidate] - el_b) <= self.tolerance_deg)
                )
                cells[bad[accepted]] = candidate[accepted]
                known[bad[accepted]] = True
            unknown_rows = rows[~known]
            rows, cells = rows[known], cells[known]
            mark('decode_lookup_ms')
        else:
            xr, yr, zr = x[rows], y[rows], z[rows]
            rr = rings[rows]
            az = np.degrees(np.arctan2(yr, xr))
            el = np.degrees(np.arctan2(zr, np.sqrt(xy2[rows])))
            mark('decode_angles_ms')
            query = az + 360.0 * rr
            right = np.minimum(np.searchsorted(self._keys, query), len(self._keys) - 1)
            left = np.maximum(right - 1, 0)
            nearest = np.where(
                np.abs(self._keys[left] - query) <= np.abs(self._keys[right] - query),
                left,
                right,
            )
            cells = self._cells[nearest]
            known = (
                (cells // w_cols == rr)
                & (np.abs(self._az_flat[cells] - az) <= self.tolerance_deg)
                & (np.abs(self._el_flat[cells] - el) <= self.tolerance_deg)
            )
            unknown_rows = rows[~known]
            rows, cells = rows[known], cells[known]
            mark('decode_lookup_ms')
        # 排序仅在真实重复回波存在时发生；常规单回波帧保持线性开销。
        duplicate_rows = np.empty(0, dtype=np.int64)
        if len(cells):
            counts = np.bincount(cells, minlength=self._n_cells)
            if (counts > 1).any():
                order = np.lexsort((rows, ranges[rows], cells))
                ordered_cells = cells[order]
                first = np.r_[True, ordered_cells[1:] != ordered_cells[:-1]]
                duplicate_rows = rows[order[~first]]
                rows, cells = rows[order[first]], cells[order[first]]
        mark('decode_duplicates_ms')
        source_rows = np.full(self.shape, -1, dtype=np.int64)
        valid = np.zeros(self.shape, dtype=bool)
        image = np.full(self.shape, np.nan)
        intensity = np.full(self.shape, np.nan)
        point_time = np.full(self.shape, np.nan)
        if len(cells):
            source_rows.ravel()[cells] = rows
            valid.ravel()[cells] = True
            image.ravel()[cells] = ranges[rows]
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
        return RangeFrame(self, binding, xyz, image, valid, source_rows,
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
