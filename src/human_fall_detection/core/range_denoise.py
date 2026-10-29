"""深度邻接支撑；边缘仅记账，保留原测量，不把真实轮廓一律删掉。"""
import numpy as np


def depth_continuous(a, b):
    # NumPy 1.17 的 NaN 比较会触发 invalid 警告；缺回波邻接明确为False。
    with np.errstate(invalid='ignore'):
        return np.abs(a - b) <= np.maximum(0.05, 0.012 * np.minimum(a, b))


def denoise(frame, foreground, min_neighbours=2):
    mask = np.asarray(foreground)
    if mask.dtype != np.bool_ or mask.shape != frame.grid.shape:
        raise ValueError('foreground must be a grid boolean mask')
    if isinstance(min_neighbours, bool) or not isinstance(min_neighbours, (int, np.integer)) or not 0 <= min_neighbours <= 8:
        raise ValueError('min_neighbours must be an integer in [0,8]')
    support = np.zeros(frame.grid.shape, dtype=np.uint8)
    edge = np.zeros(frame.grid.shape, dtype=bool)
    cells = np.flatnonzero((mask & frame.valid).ravel())
    h, w = frame.grid.shape
    depth = frame.range_m.ravel()
    for dy, dx in ((0, 1), (0, -1), (1, 0), (-1, 0), (1, 1), (1, -1), (-1, 1), (-1, -1)):
        inside = ((cells // w + dy >= 0) & (cells // w + dy < h)
                  & (cells % w + dx >= 0) & (cells % w + dx < w))
        a = cells[inside]
        b = a + dy*w + dx
        valid = frame.valid.ravel()[b]
        support.ravel()[a] += (valid & depth_continuous(depth[a], depth[b])).astype(np.uint8)
        if abs(dy) + abs(dx) == 1:
            with np.errstate(invalid='ignore'):
                edge.ravel()[a] |= valid & (np.abs(depth[a] - depth[b]) > 0.2)
    keep = mask & frame.valid & (support >= min_neighbours)
    return dict(mask=keep, edge=edge, isolated=mask & ~keep, support=support)
