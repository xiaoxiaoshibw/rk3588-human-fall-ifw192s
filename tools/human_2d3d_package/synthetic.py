"""确定性合成场景：只用于自检 / demo，不是实测数据，也不构成效果验证。

做法：从标定角表取每条射线的方向，先给一个固定的合成背景距离（默认 4 m），
再把一组轴对齐长方体（默认是头 / 躯干 / 双臂 / 双腿的粗略人体轮廓，全部位于
2.60–2.85 m 前向）用射线-盒求交放到背景前面。所有人点都在盒面上，没有插值、没有补点。

因此它验证的是"链路能不能跑、2D→3D 的来源行映射是否一致、部位假设是否只消费锁定行"，
不能用来回答准确率、召回、误报、人体语义或物理有效性——那些一律 UNKNOWN。
"""
import numpy as np

from core.capture_input import ROW_DTYPE

# (x 前向, y 横向, z 高度) 米；前端面统一在 2.60 m，保证 2D 轮廓深度连续。
DEFAULT_BODY = (
    ((2.60, 2.85), (-0.10, 0.10), (1.50, 1.72)),    # 头
    ((2.60, 2.85), (-0.22, 0.22), (0.95, 1.50)),    # 躯干
    ((2.60, 2.85), (0.22, 0.34), (0.98, 1.40)),     # 手臂 1
    ((2.60, 2.85), (-0.34, -0.22), (0.98, 1.40)),   # 手臂 2
    ((2.60, 2.85), (0.02, 0.16), (0.0, 0.95)),      # 腿 1
    ((2.60, 2.85), (-0.16, -0.02), (0.0, 0.95)),    # 腿 2
)
DEFAULT_BACKGROUND_M = 4.0


def scene_rows(grid, *, person=False, background_m=DEFAULT_BACKGROUND_M, body=None,
               intensity=100.0):
    """返回一帧 28 字节测量行；``person=True`` 时把合成人体轮廓放到背景前面。"""
    boxes = DEFAULT_BODY if body is None else tuple(body)
    azimuth = np.radians(np.asarray(grid.azimuth_deg, dtype=np.float64))
    elevation = np.radians(np.asarray(grid.elevation_deg, dtype=np.float64))
    direction = np.stack((np.cos(elevation) * np.cos(azimuth),
                          np.cos(elevation) * np.sin(azimuth),
                          np.sin(elevation)), axis=-1)
    ranges = np.full(grid.shape, float(background_m))
    if person:
        for bounds, lateral, vertical in boxes:
            low = np.array([bounds[0], lateral[0], vertical[0]], dtype=np.float64)
            high = np.array([bounds[1], lateral[1], vertical[1]], dtype=np.float64)
            enter = np.full(grid.shape, -np.inf)
            leave = np.full(grid.shape, np.inf)
            for axis in range(3):
                component = direction[..., axis]
                safe = np.where(np.abs(component) < 1e-12,
                                np.where(component >= 0, 1e-12, -1e-12), component)
                first, second = low[axis] / safe, high[axis] / safe
                enter = np.maximum(enter, np.minimum(first, second))
                leave = np.minimum(leave, np.maximum(first, second))
            hit = (leave >= enter) & (enter > 0.1) & (leave > 0.1)
            ranges = np.where(hit & (enter < ranges), enter, ranges)
    points = direction * ranges[..., None]
    rows = np.zeros(points[..., 0].size, dtype=ROW_DTYPE)
    rows['x'] = points[..., 0].astype(np.float32).ravel()
    rows['y'] = points[..., 1].astype(np.float32).ravel()
    rows['z'] = points[..., 2].astype(np.float32).ravel()
    rows['intensity'] = float(intensity)
    rows['ring'] = np.repeat(np.arange(grid.shape[0], dtype=np.uint16), grid.shape[1])
    rows['timestamp'] = 0.0
    return rows