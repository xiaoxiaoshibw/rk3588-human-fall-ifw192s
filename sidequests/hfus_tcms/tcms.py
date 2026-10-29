"""Hit-support experiment, not free-space inference or a human classifier."""
from collections import deque
from itertools import product
import math
import numpy as np

BASE = 20001
SHIFTS = [(s, s[0]*BASE*BASE+s[1]*BASE+s[2])
          for s in product((-1, 0, 1), repeat=3) if s != (0, 0, 0)]


def support(points, size, tile_m=1.2):
    """Return observed occupied cells and original current-frame row IDs.

    Cells absent from this dictionary are UNKNOWN, never observed-free.
    Fixed RAW coordinates deliberately avoid claiming physical leveling.
    """
    p = np.asarray(points)
    if p.ndim != 2 or p.shape[1] != 3 or not np.issubdtype(p.dtype, np.number):
        raise ValueError('Expected numeric Nx3 XYZ')
    if not math.isfinite(size) or not .01 <= size <= 1 or not math.isfinite(tile_m) or tile_m < size:
        raise ValueError('Invalid grid size')
    valid = np.isfinite(p).all(1) & np.any(p != 0, axis=1)
    ids = np.flatnonzero(valid)
    radius = np.linalg.norm(p[ids].astype('f8'), axis=1)
    ids = ids[(radius >= .3) & (radius <= 12)]
    keys = np.floor(p[ids].astype('f8')/size).astype('i8')
    tile_cells = max(1, int(round(tile_m/size)))
    tiles = keys//tile_cells
    codes = keys[:, 0]*BASE*BASE+keys[:, 1]*BASE+keys[:, 2]
    out = {}
    if len(ids):
        unique, inv = np.unique(tiles, axis=0, return_inverse=True)
        order = np.argsort(inv, kind='stable')
        groups = np.split(order, np.cumsum(np.bincount(inv))[:-1])
        for tile, group in zip(unique, groups):
            key = tuple(int(v) for v in tile)
            out[key] = (set(int(v) for v in codes[group]), ids[group])
    return out, int(len(p)-len(ids))


def mismatch(a, b):
    return 1-2*len(a & b)/(len(a)+len(b)) if a and b else None


def explain(a, b, penalty=.03):
    """Same hit sets for both explanations. Shift B toward A, no point matches.

    Positive score measures fit improvement minus L1 grid-shift complexity.
    It is not a probability. Fixed tile boundaries can fragment a target.
    """
    static = mismatch(a, b)
    if static is None:
        return None
    common = len(a & b)
    gain, best = 0., (0, 0, 0)
    for shift, delta in SHIFTS:
        hit = sum((v+delta) in a for v in b)
        value = 2*(hit-common)/(len(a)+len(b))-penalty*sum(abs(v) for v in shift)
        if value > gain:
            gain, best = value, shift
    return static, gain, best


class Window:
    def __init__(self, size, frames, max_gap_s=.5, min_cells=8):
        if not math.isfinite(size) or not .01 <= size <= 1 or type(frames) is not int or frames < 2:
            raise ValueError('Invalid voxel/window')
        if not math.isfinite(max_gap_s) or max_gap_s <= 0 or type(min_cells) is not int or min_cells < 1:
            raise ValueError('Invalid support/time constraint')
        self.size, self.frames = float(size), frames
        self.max_gap_s, self.min_cells = float(max_gap_s), min_cells
        self.history = deque(maxlen=2*frames)
        self.last = None

    def update(self, hits, stamp):
        if not math.isfinite(stamp) or (self.last is not None and stamp <= self.last):
            raise ValueError('Strictly increasing finite time required')
        reset = self.last is not None and stamp-self.last > self.max_gap_s
        if reset:
            self.history.clear()
        self.last = stamp
        # Copy sets so external caller mutation cannot alter temporal history.
        self.history.append((stamp, {k: frozenset(v[0]) for k, v in hits.items()}))
        if len(self.history) < 2*self.frames:
            return [], {'state': 'WARMUP', 'gap_reset': reset, 'span_s': None}
        history = list(self.history)
        early, late = {}, {}
        for dest, frames in [(early, history[:self.frames]), (late, history[self.frames:])]:
            for _, frame in frames:
                for tile, cells in frame.items():
                    dest.setdefault(tile, set()).update(cells)
        rows = []
        for tile in sorted(hits):
            a, b = early.get(tile, set()), late.get(tile, set())
            if min(len(a), len(b)) < self.min_cells:
                continue
            b2, b3, shift = explain(a, b)
            b1 = mismatch(set(history[-2][1].get(tile, ())), set(history[-1][1][tile]))
            center = (np.array(tile)+.5)*round(1.2/self.size)*self.size
            range_bin = min(2, int(np.linalg.norm(center)//4))
            rows.append(dict(tile=list(tile), range_bin=range_bin, early_cells=len(a), late_cells=len(b),
                             B1=b1, B2=b2, B3=b3, shift_to_past=list(shift)))
        return rows, {'state': 'SCORED', 'gap_reset': reset,
                      'span_s': stamp-history[0][0], 'eligible_tiles': len(rows),
                      'unknown_current_tiles': len(hits)-len(rows)}


def calibrate(rows, minimum=30):
    result = {}
    for band in range(3):
        result[str(band)] = {}
        for method in ('B1', 'B2', 'B3'):
            values = [r[method] for r in rows if r['range_bin'] == band and r[method] is not None]
            result[str(band)][method] = dict(n=len(values), threshold=float(np.quantile(values, .99))
                                             if len(values) >= minimum else None)
    return result


def active(row, thresholds, method):
    threshold = thresholds[str(row['range_bin'])][method]['threshold']
    return threshold is not None and row[method] is not None and row[method] > threshold
