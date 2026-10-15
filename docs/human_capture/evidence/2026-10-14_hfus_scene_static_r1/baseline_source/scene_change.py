"""Frozen surface change detection with static-anchor vibration compensation.

No human labels, future action frames or action-derived background updates.
Coordinates are rigidly corrected; original frame-local rows remain identities.
"""
import numpy as np
from scipy.spatial import cKDTree
from scipy.spatial.transform import Rotation


class FrozenSurfaces:
    def __init__(self, xyz, tolerance, cfg):
        self.xyz = np.asarray(xyz, dtype=float)
        if self.xyz.ndim != 2 or self.xyz.shape[1] != 3 or not np.isfinite(self.xyz).all() or len(self.xyz) < cfg['normal_neighbors']:
            raise ValueError('Finite, supported frozen background required')
        if not np.isfinite(tolerance) or tolerance <= 0:
            raise ValueError('Positive finite background tolerance required')
        self.tau, self.cfg = tolerance, cfg
        self.tree = cKDTree(self.xyz)
        distances, indices = self.tree.query(self.xyz, k=cfg['normal_neighbors'])
        neighbors = self.xyz[indices]
        self.centers = neighbors.mean(axis=1)
        delta = neighbors - self.centers[:, None]
        values, vectors = np.linalg.eigh(np.einsum('nki,nkj->nij', delta, delta) / cfg['normal_neighbors'])
        self.normals = vectors[:, :, 0]
        self.radius = distances[:, -1]
        self.planar = ((values[:, 0] <= cfg['planarity_ratio'] * np.maximum(values[:, 1], np.finfo(float).eps))
                       & (values[:, 1] > tolerance**2 / cfg['normal_neighbors'])
                       & (self.radius <= tolerance * cfg['surface_radius_tau']))

    def compensate(self, points, limits=None):
        """Fit six small rigid degrees of freedom using only close static planes.

        Degenerate geometry, unsupported/excessive correction or a worse residual
        explicitly returns the uncorrected points. Does not track a moving body.
        """
        p = np.asarray(points, dtype=float)
        if p.ndim != 2 or p.shape[1] != 3:
            raise ValueError('Expected an N by 3 point array')
        finite = np.flatnonzero(np.isfinite(p).all(axis=1))
        sample = finite[np.linspace(0, len(finite)-1, min(len(finite), self.cfg['anchor_limit']), dtype=int)] if len(finite) else finite
        moved = p.copy(); matrix = np.eye(3); translation = np.zeros(3)
        initial = None; count = 0
        def failure(reason):
            return p.copy(), {'status': reason, 'R': np.eye(3).tolist(), 't': [0., 0., 0.], 'anchor_count': count}
        for _ in range(self.cfg['fit_iterations']):
            d, ix = self.tree.query(moved[sample])
            keep = (d <= self.tau * self.cfg['anchor_radius_tau']) & self.planar[ix]
            x = moved[sample[keep]]; n = self.normals[ix[keep]]
            residual = np.einsum('ij,ij->i', x-self.centers[ix[keep]], n)
            if len(residual) < self.cfg['min_anchors']: return failure('INSUFFICIENT_STATIC_ANCHORS')
            trim = np.abs(residual) <= np.quantile(np.abs(residual), self.cfg['anchor_trim_quantile'])
            x, n, residual = x[trim], n[trim], residual[trim]; count = len(x)
            if count < self.cfg['min_anchors']: return failure('INSUFFICIENT_STATIC_ANCHORS')
            a = np.column_stack((np.cross(x, n), n))
            step, _, rank, singular = np.linalg.lstsq(a, -residual, rcond=None)
            if rank < 6 or singular[-1] / singular[0] < self.cfg['min_singular_ratio']:
                return failure('DEGENERATE_STATIC_ANCHORS')
            if initial is None: initial = float(np.median(np.abs(residual)))
            rotation = Rotation.from_rotvec(step[:3]).as_matrix()
            moved = moved @ rotation.T + step[3:]
            matrix, translation = rotation @ matrix, rotation @ translation + step[3:]
        angle = float(np.linalg.norm(Rotation.from_matrix(matrix).as_rotvec()))
        shift = float(np.linalg.norm(translation))
        if limits and (angle > limits['rotation_rad'] or shift > limits['translation_m']):
            return failure('OUTSIDE_EMPTY_SCENE_VIBRATION_ENVELOPE')
        # Evaluate exactly the original anchor rows before/after; no changed denominator.
        original_d, original_ix = self.tree.query(p[sample])
        fixed = (original_d <= self.tau * self.cfg['anchor_radius_tau']) & self.planar[original_ix]
        normals = self.normals[original_ix[fixed]]; centers = self.centers[original_ix[fixed]]
        before = float(np.median(np.abs(np.einsum('ij,ij->i', p[sample[fixed]]-centers, normals))))
        after = float(np.median(np.abs(np.einsum('ij,ij->i', moved[sample[fixed]]-centers, normals))))
        if after > before: return failure('STATIC_RESIDUAL_WORSENED')
        return moved, {'status': 'COMPENSATED', 'R': matrix.tolist(), 't': translation.tolist(),
                       'translation_m': shift, 'rotation_rad': angle, 'anchor_count': count,
                       'static_residual_before_m': before, 'static_residual_after_m': after}

    def split(self, points, valid):
        p = np.asarray(points, dtype=float)
        if p.ndim != 2 or p.shape[1] != 3 or np.shape(valid) != (len(p),):
            raise ValueError('Expected N by 3 points and N validity flags')
        valid = np.asarray(valid, dtype=bool) & np.isfinite(p).all(axis=1)
        ids = np.flatnonzero(valid)
        d, ix = self.tree.query(p[ids])
        offset = p[ids] - self.centers[ix]
        normal_distance = np.abs(np.einsum('ij,ij->i', offset, self.normals[ix]))
        # Bound tangent support: never extend an infinite furniture/floor plane.
        tangent = np.sqrt(np.maximum(0., np.einsum('ij,ij->i', offset, offset)-normal_distance**2))
        surface = self.planar[ix] & (tangent <= self.radius[ix]) & (normal_distance <= self.tau)
        matched = (d <= self.tau) | surface
        bg = np.zeros(len(p), bool); bg[ids[matched]] = True
        distance = np.full(len(p), np.inf); distance[ids] = d
        return np.flatnonzero(valid & ~bg), bg, distance, int(np.count_nonzero(surface & (d > self.tau)))

    def split_pose_hypotheses(self, nominal, corrected, valid):
        """Pose correction cannot promote a known background return to a new object.

        A return explained by either supported pose is not proven scene emergence.
        Disagreement is archived as UNKNOWN, not silently assigned a human identity.
        """
        _, before, _, _ = self.split(nominal, valid)
        _, after, distance, extra = self.split(corrected, valid)
        matched = before | after
        ambiguous = before ^ after
        return np.flatnonzero(np.asarray(valid) & ~matched), matched, distance, extra, ambiguous
