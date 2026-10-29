"""显式前缀的逐射线中位/MAD背景；未知射线不冒充前景或空场。"""
import numpy as np


class RayBackground:
    def __init__(self, frames, *, empty_prefix_declared, min_observations=10,
                 min_valid_fraction=0.6, scene_change_fraction=0.35):
        frames = list(frames)
        if not empty_prefix_declared or not frames:
            raise ValueError('background needs an explicitly declared development empty prefix')
        if isinstance(min_observations, bool) or int(min_observations) != min_observations or min_observations < 1:
            raise ValueError('min_observations must be a positive integer')
        if not (0 < min_valid_fraction <= 1 and 0 < scene_change_fraction <= 1):
            raise ValueError('invalid background quality limits')
        self.binding = (frames[0].binding, frames[0].grid.sha256)
        for frame in frames:
            self._check(frame)
        stack = np.stack([f.range_m for f in frames])
        self.observations = np.isfinite(stack).sum(axis=0)
        self.known = self.observations >= min_observations
        if not self.known.any():
            raise ValueError('prefix has no sufficiently observed rays')
        self.mean_m = np.full(frames[0].grid.shape, np.nan)
        self.sigma_m = np.full_like(self.mean_m, np.nan)
        observed = stack[:, self.known]
        # Small prefix, many rays: sort each ray once instead of masked-array
        # nanmedian dispatch. NaNs sort last; the two middle valid samples are
        # exactly NumPy's median, including the even-count average.
        counts = (~np.isnan(observed)).sum(axis=0)
        columns = np.arange(observed.shape[1])
        def median(values):
            ordered = np.sort(values, axis=0)
            return (ordered[(counts-1)//2, columns]+ordered[counts//2, columns])*.5
        center = median(observed)
        self.mean_m[self.known] = center
        self.sigma_m[self.known] = np.maximum(0.005, 1.4826 * median(np.abs(observed - center)))
        self.min_valid_fraction = float(min_valid_fraction)
        self.scene_change_fraction = float(scene_change_fraction)
        self.invalidated = False

    def _check(self, frame):
        if (frame.binding, frame.grid.sha256) != self.binding:
            raise ValueError('background stream/frame/calibration/grid binding mismatch')

    def foreground(self, frame):
        self._check(frame)
        comparable = frame.valid & self.known
        residual = np.zeros(frame.grid.shape)
        residual[comparable] = frame.range_m[comparable] - self.mean_m[comparable]
        threshold = np.full(frame.grid.shape, 0.04)
        threshold[self.known] = np.maximum(0.04, 4 * self.sigma_m[self.known])
        changed = comparable & (np.abs(residual) > threshold)
        fraction = float(changed.sum()) / max(1, int(comparable.sum()))
        valid_fraction = float(frame.valid.mean())
        if valid_fraction >= self.min_valid_fraction and fraction > self.scene_change_fraction:
            self.invalidated = True
        status = ('background_invalidated' if self.invalidated else
                  'insufficient_valid_cells' if valid_fraction < self.min_valid_fraction else 'ready')
        return dict(mask=changed if status == 'ready' else np.zeros_like(changed),
                    residual_m=residual, unknown=frame.valid & ~self.known, status=status,
                    valid_fraction=valid_fraction, changed_fraction=fraction)

    def update(self, frame, *, freeze_mask, alpha=0.002):
        """只更新匹配背景且未冻结的已知格；不学习未知/前景，不重启失效背景。"""
        if not np.isfinite(alpha) or not 0 < alpha <= 1:
            raise ValueError('alpha must be in (0,1]')
        freeze = np.asarray(freeze_mask)
        if freeze.dtype != np.bool_ or freeze.shape != frame.grid.shape:
            raise ValueError('freeze_mask must be a grid boolean mask')
        result = self.foreground(frame)
        if result['status'] != 'ready':
            return 0
        selected = frame.valid & self.known & ~freeze & ~result['mask']
        self.mean_m[selected] += alpha * result['residual_m'][selected]
        return int(selected.sum())
