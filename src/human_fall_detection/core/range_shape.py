"""标定距离图的目标形状旁路；不分类、不补点、不改变跟踪或规则。"""
from collections import deque

import numpy as np


def shape_features(frame, rows, labels=None):
    """任意3D候选均可用同帧来源行调用；不要求由2D连通域生成。"""
    rows = np.asarray(rows)
    if (rows.ndim != 1 or not rows.size or rows.dtype.kind not in 'iu'
            or len(np.unique(rows)) != len(rows) or rows.min() < 0
            or rows.max() >= len(frame.xyz)):
        raise ValueError('shape requires unique nonempty current source rows')
    selected = np.zeros(len(frame.xyz), dtype=bool)
    selected[rows] = True
    valid_cells = np.flatnonzero(frame.valid.ravel())
    source = frame.source_rows.ravel()[valid_cells]
    if (source < 0).any() or (source >= len(frame.xyz)).any():
        raise ValueError('invalid decoded source mapping')
    cells = valid_cells[selected[source]]
    if len(cells) != len(rows) or not np.array_equal(np.sort(source[selected[source]]), np.sort(rows)):
        raise ValueError('shape rows must map one-to-one to current valid cells')
    h, w = frame.grid.shape
    y, x = cells // w, cells % w
    ranges = frame.range_m.ravel()[cells]
    if not np.isfinite(ranges).all() or (ranges <= .1).any():
        raise ValueError('invalid selected depth')
    row_span, col_span = int(y.max()-y.min()+1), int(x.max()-x.min()+1)
    edges = dict(top=bool((y == 0).any()), bottom=bool((y == h-1).any()),
                 left=bool((x == 0).any()), right=bool((x == w-1).any()))
    adjacent_invalid = np.zeros(len(cells), dtype=bool)
    for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1)):
        inside = (y+dy >= 0) & (y+dy < h) & (x+dx >= 0) & (x+dx < w)
        adjacent_invalid[inside] |= ~frame.valid[y[inside]+dy, x[inside]+dx]
    fragments = None
    if labels is not None:
        labels = np.asarray(labels)
        if labels.shape != (h, w) or labels.dtype.kind not in 'iu':
            raise ValueError('invalid component labels')
        ids, counts = np.unique(labels.ravel()[cells], return_counts=True)
        if (ids < 0).any():
            raise ValueError('selected target contains unlabelled cells')
        fragments = [dict(component_id=int(i), pixels=int(n)) for i, n in zip(ids, counts)]
    az = frame.grid.azimuth_deg.ravel()[cells]
    el = frame.grid.elevation_deg.ravel()[cells]
    # 距离平方仅补偿像素数量随距离的缩放；未乘固体角，不是物理表面积。
    return dict(pixel_count=len(cells), row_span=row_span, col_span=col_span,
        bbox_rc=[int(y.min()), int(x.min()), int(y.max()), int(x.max())],
        fill_ratio=float(len(cells)/(row_span*col_span)), aspect_col_row=float(col_span/row_span),
        azimuth_span_deg=float(np.ptp(az)), elevation_span_deg=float(np.ptp(el)),
        range_median_m=float(np.median(ranges)), range_squared_sum_px_m2=float(np.sum(ranges*ranges)),
        area_definition='sum(range_m**2); pixel-distance proxy, NOT physical surface area',
        touches_grid_boundary=any(edges.values()), boundary_edges=edges,
        adjacent_invalid_pixel_count=int(adjacent_invalid.sum()),
        adjacent_invalid_fraction=float(adjacent_invalid.mean()),
        fragments=fragments, fragment_count=len(fragments) if fragments is not None else None,
        largest_fragment_fraction=max(f['pixels'] for f in fragments)/len(cells) if fragments else None,
        fragment_definition='inherited depth-component labels; not independent object count',
        completeness='UNKNOWN', occlusion='UNKNOWN', semantic='UNKNOWN')


class ShapeObserver:
    """只积累同一绑定/目标的连续实测；历史最多128帧和1.2秒。"""
    def __init__(self):
        self.history = deque(maxlen=128)
        self.key = None
        self.last_frame = None
        self.last_time = None

    def update(self, frame, record, labels=None):
        index, stamp = record['frame'], record['time_s']
        if type(index) is not int or index < 0 or not np.isfinite(stamp):
            self.history.clear()
            self.key = None
            raise ValueError('invalid shape observation clock/index')
        rows, tid = record['target_source_rows'], record['target_track_id']
        key = (frame.binding, frame.grid.sha256, record['generation'], tid)
        reason = None
        if key != self.key:
            reason = 'binding_generation_or_target_changed'
        elif self.last_frame is None or index != self.last_frame+1:
            reason = 'input_frame_gap'
        elif stamp <= self.last_time or stamp-self.last_time > .3:
            reason = 'clock_discontinuity'
        elif len(self.history) == self.history.maxlen:
            reason = 'history_capacity'
        self.key, self.last_frame, self.last_time = key, index, stamp
        if reason:
            self.history.clear()
        track = next((t for t in record['tracks'] if t['track_id'] == tid), None)
        measured = (tid is not None and len(rows) > 0 and track is not None
                    and track.get('status') == 'tracked' and track.get('observed') is True
                    and track.get('position_predicted') is False
                    and np.array_equal(track.get('source_rows'), rows))
        base = dict(frame=index, time_s=stamp, track_id=tid, generation=record['generation'],
                    input_inference_sha256=record['inference_sha256'], shadow_only=True)
        if not measured:
            self.history.clear()
            return dict(base, available=False, reason='no_stable_current_measurement',
                        reset_reason=reason, shape=None, temporal=None)
        try:
            shape = shape_features(frame, rows, labels)
        except ValueError:
            self.history.clear()
            raise
        while self.history and stamp-self.history[0][0] > 1.2:
            self.history.popleft()
        prior = self.history[-1] if self.history else None
        self.history.append((stamp, shape['pixel_count'], shape['range_squared_sum_px_m2']))
        first = self.history[0]
        temporal = dict(samples=len(self.history), observed_span_s=float(stamp-first[0]),
            pixel_ratio_previous=shape['pixel_count']/prior[1] if prior else None,
            range_squared_ratio_previous=shape['range_squared_sum_px_m2']/prior[2] if prior else None,
            pixel_ratio_window=shape['pixel_count']/first[1] if len(self.history) > 1 else None,
            reason=None if prior else 'continuous_history_unavailable')
        return dict(base, available=True, reason=None, reset_reason=reason, shape=shape, temporal=temporal)
