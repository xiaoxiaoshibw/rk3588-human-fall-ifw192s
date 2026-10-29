"""离线整段非因果输入模型：只给离线回放/对照喂数据，永不进入在线链。

两条输入都由显式声明绑定，不能冒充在线 W1 的空场前缀，也不能被
``RangeEngine``/ROS 服务安装：

* ``QuantileBackground`` —— 整段每射线 98 分位距离；只把“明显更近”的
  回波算前景。整段统计用到了未来帧，所以是非因果离线输入。
* ``fit_declared_plane`` —— 本会话点云的确定性 RANSAC + 最小二乘精修，
  只是显示/高度参考，``physical_verified=False``、``runtime_eligible=False``。

检测/跟踪/特征/状态机本身只走 ``core.range_runtime.RangeRuntime``。
"""
import numpy as np

QUANTILE = 0.98
MIN_OBSERVATIONS = 20
DELTA_M = 0.30
SEED = 20261023
DECLARATION = 'offline_whole_recording_quantile'

GROUND_THRESHOLD_M = 0.02
GROUND_ITERATIONS = 1500
GROUND_SAMPLE_POINTS = 20000
GROUND_REFINE_ROUNDS = 5
GROUND_ABOVE_THRESHOLD_M = 0.15


class QuantileBackground:
    """整段逐射线分位背景；``non_causal=True`` 是构造前提，不是可选开关。"""

    non_causal = True
    declaration = DECLARATION

    def __init__(self, mean_m, known, *, binding, grid_sha256, quantile=QUANTILE,
                 min_observations=MIN_OBSERVATIONS, delta_m=DELTA_M):
        mean = np.asarray(mean_m, dtype=np.float64)
        known = np.asarray(known)
        if mean.ndim != 2 or known.shape != mean.shape or known.dtype != np.bool_:
            raise ValueError('background needs a 2-D grid and a matching boolean known mask')
        if float(quantile) != QUANTILE:
            raise ValueError('unsupported offline background quantile')
        if int(min_observations) != MIN_OBSERVATIONS:
            raise ValueError('unsupported offline background observation floor')
        if np.isfinite(mean[~known]).any() or not np.isfinite(mean[known]).all():
            raise ValueError('background must be finite exactly where known')
        if not known.any():
            raise ValueError('background needs at least one sufficiently observed ray')
        delta = float(delta_m)
        if not np.isfinite(delta) or delta <= 0:
            raise ValueError('foreground delta must be a positive finite distance')
        self.mean_m, self.known = mean, known
        self.binding, self.grid_sha256 = binding, grid_sha256
        self.quantile, self.min_observations, self.delta_m = float(quantile), int(min_observations), delta

    @classmethod
    def from_stack(cls, stack, observed, *, binding=None, grid_sha256=None, quantile=QUANTILE,
                   min_observations=MIN_OBSERVATIONS, delta_m=DELTA_M):
        """``stack`` 是 (frames, ring, column) 距离栈；未观测射线保持 NaN。"""
        values = np.asarray(stack)
        counts = np.asarray(observed)
        if values.ndim != 3 or counts.shape != values.shape[1:] or not counts.size:
            raise ValueError('background stack and observation counts disagree')
        if counts.dtype.kind not in 'iu' or (counts < 0).any() or (counts > values.shape[0]).any():
            raise ValueError('invalid per-ray observation counts')
        ordered = np.sort(np.where(np.isfinite(values), values, np.nan), axis=0)
        numeric = counts.astype(np.int64)
        index = np.clip((numeric * float(quantile)).astype(np.int64), 0,
                        np.maximum(numeric - 1, 0))
        mean = np.take_along_axis(ordered, index[None, ...], axis=0)[0]
        known = numeric >= int(min_observations)
        mean = np.where(known, mean, np.nan)
        del ordered
        return cls(mean, known, binding=binding, grid_sha256=grid_sha256,
                   quantile=quantile, min_observations=min_observations, delta_m=delta_m)

    def foreground(self, frame):
        if (frame.binding, frame.grid.sha256) != (self.binding, self.grid_sha256):
            raise ValueError('offline background binding mismatch')
        comparable = frame.valid & self.known
        residual = np.zeros(frame.grid.shape)
        with np.errstate(invalid='ignore'):
            residual[comparable] = frame.range_m[comparable] - self.mean_m[comparable]
        changed = comparable & (residual < -self.delta_m)
        return dict(mask=changed, residual_m=residual, unknown=frame.valid & ~self.known,
                    status='ready', valid_fraction=float(frame.valid.mean()),
                    changed_fraction=float(changed.sum()) / max(1, int(comparable.sum())))

    def statistics(self):
        return dict(declaration=self.declaration, causal=False, runtimeEligible=False,
                    quantile=self.quantile, minObservations=self.min_observations,
                    deltaM=self.delta_m, knownRays=int(self.known.sum()),
                    note='整段统计用到未来帧；只用于离线对照，不是在线空场前缀契约')


def fit_declared_plane(points, *, binding=None, frame='innolidar', seed=SEED):
    """确定性 RANSAC + 最小二乘；返回只供离线显示/高度参考的平面。"""
    xyz = np.asarray(points, dtype=np.float64)
    if xyz.ndim != 2 or xyz.shape[1] != 3 or len(xyz) < 100:
        raise ValueError('地面拟合需要至少 100 个 (N,3) 点')
    if not np.isfinite(xyz).all():
        raise ValueError('地面拟合输入包含非有限值')
    rng = np.random.default_rng(seed)
    sample_size = min(len(xyz), GROUND_SAMPLE_POINTS)
    sample = xyz[np.sort(rng.choice(len(xyz), sample_size, replace=False))]
    span = float(np.ptp(sample, axis=0).max())
    if not span > 0.5:
        raise ValueError('点云空间跨度太小，无法拟合地面')
    candidates = []
    for _ in range(GROUND_ITERATIONS):
        picks = rng.choice(sample_size, 3, replace=False)
        a, b, c = sample[picks]
        normal = np.cross(b - a, c - a)
        norm = float(np.linalg.norm(normal))
        if not np.isfinite(norm) or norm < 1e-9:
            continue
        normal = normal / norm
        offset = float(-normal @ a)
        count = int((np.abs(sample @ normal + offset) < GROUND_THRESHOLD_M).sum())
        if count >= max(400, sample_size // 100):
            candidates.append((count, normal, offset))
    if not candidates:
        raise ValueError('RANSAC 没有找到足够的平面内点')
    candidates.sort(key=lambda item: (-item[0], tuple(np.round(item[1], 9)), round(item[2], 9)))
    planes = []
    for count, normal, offset in candidates:
        if any(abs(float(normal @ other[1])) > 0.99 and abs(offset - other[2]) < 0.05
               for other in planes):
            continue
        planes.append((count, normal, offset))
        if len(planes) >= 5:
            break
    refined = []
    for count, normal, offset in planes:
        for _ in range(GROUND_REFINE_ROUNDS):
            distance = sample @ normal + offset
            band = np.abs(distance) < 0.08
            if band.sum() < 100:
                break
            pts = sample[band]
            centre = pts.mean(axis=0)
            _, _, vt = np.linalg.svd(pts - centre, full_matrices=False)
            candidate = vt[-1] / np.linalg.norm(vt[-1])
            if float(candidate @ normal) < 0:
                candidate = -candidate
            normal, offset = candidate, float(-candidate @ centre)
        # 让“设备在平面上方”：offset>0 时高度 h = p·n + d，原点 h=d。
        if offset < 0:
            normal, offset = -normal, -offset
        heights = xyz @ normal + offset
        refined.append(dict(inlier_count=count, normal=normal, offset_m=offset,
                            above_fraction=float((heights > GROUND_ABOVE_THRESHOLD_M).mean()),
                            residual_median_m=float(np.median(np.abs(sample @ normal + offset)))))
    refined.sort(key=lambda item: (-item['above_fraction'], -item['inlier_count'],
                                   tuple(np.round(item['normal'], 9))))
    best = refined[0]
    normal, offset = best['normal'], best['offset_m']
    height = float(offset)
    if not 0.2 <= height <= 5.0:
        raise ValueError('拟合地面到设备的高度不合理：%.3f m' % height)
    if abs(float(normal[2])) < 0.4:
        raise ValueError('拟合地面法向与传感器 z 轴偏差过大')
    inliers = np.abs(xyz @ normal + offset) < 0.05
    result = dict(status='valid', frame=str(frame), normal=[float(v) for v in normal],
                  offset_m=float(offset), sensor_height_m=height,
                  method='deterministic_ransac+least_squares',
                  threshold_m=GROUND_THRESHOLD_M, iterations=GROUND_ITERATIONS,
                  sample_points=int(sample_size), inlier_fraction=float(inliers.mean()),
                  inlier_residual_median_m=float(np.median(np.abs(xyz[inliers] @ normal + offset))),
                  above_fraction=best['above_fraction'],
                  above_threshold_m=GROUND_ABOVE_THRESHOLD_M,
                  physical_verified=False, offline_only=True, runtime_eligible=False,
                  note='本会话点云拟合；不是标定/物理地面认证，runtime_eligible=false')
    if binding is not None:
        result['binding'] = binding
    return result