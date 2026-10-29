"""2D 距离图 → 3D 人体目标：算法包唯一对外 API（纯 stdlib + NumPy）。

链路（全部是本包内可审计的几何测量，没有模型、没有 ROS、没有数据目录）：

    点云行 (28 B) → 标定角表 (ring, 列) 距离图(2D) → 逐射线空场背景
    → 前景掩膜 → 8 邻域深度连通域（2D 人体候选区域）
    → 同源行号提升为 3D 点（2D→3D 的唯一入口）
    → 单目标跟踪 → 几何特征 / 姿态旁路 / 区域骨架 / 身体部位假设

边界（README 与 ALGORITHM 同步声明）：
- 只输出几何候选，"这是人 / 这是谁 / 是否真的跌倒"一律 UNKNOWN；
- ``confirmed`` 在运行时被禁用，跌倒状态最高只到 ``suspected``；
- 地面是调用方显式声明的输入，不由本包拟合，也不等于物理地面认证；
- 空场背景必须由调用方显式声明的前 N 帧建立，本包不会自动学习背景。
"""
import hashlib
import json
import math
from pathlib import Path
import sys

import numpy as np

PACKAGE = Path(__file__).resolve().parent
if str(PACKAGE) not in sys.path:
    sys.path.insert(0, str(PACKAGE))

from core.capture_input import ROW_DTYPE
from core.range_image import ScanGrid
from core.range_posture import PostureObserver
from core.range_runtime import RangeRuntime
from core.range_skeleton import estimate as estimate_skeleton, project_regions
from body_branches import METHOD as BODY_METHOD, NAMES as BODY_NAMES, propose as propose_body_parts

VERSION = '1.0.0'
SEMANTIC = 'UNKNOWN'
CALIBRATION_FILES = ('ifw192s_azimuth_192x256.csv', 'ifw192s_elevation_192x256.csv')


def _rows_array(rows):
    """只接受 28 字节测量行；不做列名猜测或自动转置。"""
    if isinstance(rows, (bytes, bytearray, memoryview)):
        if len(rows) % ROW_DTYPE.itemsize:
            raise ValueError('truncated %d-byte point record' % ROW_DTYPE.itemsize)
        array = np.frombuffer(rows, dtype=ROW_DTYPE)
    else:
        array = np.asarray(rows)
        if array.dtype != ROW_DTYPE:
            raise ValueError('expected capture_input.ROW_DTYPE rows, got %r' % (array.dtype,))
    if array.ndim != 1:
        raise ValueError('rows must be a 1-D structured array')
    return array


def _finite_number(value, name):
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValueError('%s must be a finite number' % name) from None
    if not math.isfinite(number):
        raise ValueError('%s must be a finite number' % name)
    return number


class Human2D3D:
    """一次显式会话（含空场前缀）的 2D→3D 人体目标算法实例。

    ``calibration_dir`` 默认取包内 ``calibration/``（本机 IFW192S 角表）。
    ``empty_prefix_frames`` 是调用方声明的连续空场帧数，必须 ≥1。
    ``body_parts=True`` 时额外计算身体部位假设（纯 NumPy，耗时更高）。
    """

    def __init__(self, calibration_dir=None, *, session='local', frame_id='innolidar',
                 empty_prefix_frames=50, body_parts=False, detailed=True):
        directory = Path(calibration_dir) if calibration_dir is not None else PACKAGE / 'calibration'
        azimuth = directory / CALIBRATION_FILES[0]
        elevation = directory / CALIBRATION_FILES[1]
        if not azimuth.is_file() or not elevation.is_file():
            raise ValueError('calibration tables not found in %s' % directory)
        self.grid = ScanGrid.from_csv(azimuth, elevation)
        self.session = str(session)
        self.frame_id = str(frame_id)
        if isinstance(empty_prefix_frames, bool) or not isinstance(empty_prefix_frames, int) \
                or empty_prefix_frames < 1:
            raise ValueError('empty_prefix_frames must be a positive integer')
        self.empty_prefix_frames = empty_prefix_frames
        self.identity = dict(session=self.session, coordinate='RAW/' + self.frame_id, units='m',
                             coordinate_transform='identity', grid_sha256=self.grid.sha256,
                             epoch='caller_supplied_session')
        self.body_parts_enabled = bool(body_parts)
        self.runtime = RangeRuntime(self.grid, self.identity,
                                    empty_prefix_frames=self.empty_prefix_frames,
                                    detailed=bool(detailed))
        self.posture = PostureObserver()
        self.processed = 0
        self.last_stamp = None
        self.last_index = None
        self._buckets = None

    # ------------------------------------------------------------------ 输入
    def encode_points(self, xyz, ring=None, intensity=0.0, timestamp=0.0):
        """把 (N,3) 米制 XYZ 编码成 28 字节测量行（供没有原始 ring 的调用方使用）。

        ``ring`` 为 None 时在整张角表上按 (方位, 仰角) 找最近方向（两项都必须落在
        0.02° 容差内才算命中）。本机 IFW192S 的每条 ring 有各自的方位跨度，因此
        "按仰角中位数猜 ring" 是不成立的；不在角表方向上的点仍按最近方向编码，
        解码阶段会计入 ``unknown_direction_rows``，不会被补造到任何格子上。
        """
        points = np.asarray(xyz, dtype=np.float64)
        if points.ndim != 2 or points.shape[1] != 3:
            raise ValueError('xyz must be an (N,3) array')
        if len(points) and not np.isfinite(points).all():
            raise ValueError('xyz must be finite')
        if ring is None:
            rings = self._nearest_rings(points)
        else:
            rings = np.asarray(ring)
            if rings.shape != (len(points),) or not np.issubdtype(rings.dtype, np.integer):
                raise ValueError('ring must be an integer vector of length N')
            if len(points) and (rings.min() < 0 or rings.max() >= self.grid.shape[0]):
                raise ValueError('ring outside the calibration rows')
            rings = rings.astype(np.uint16)
        rows = np.zeros(len(points), dtype=ROW_DTYPE)
        rows['x'], rows['y'], rows['z'] = (points[:, 0].astype(np.float32),
                                           points[:, 1].astype(np.float32),
                                           points[:, 2].astype(np.float32))
        rows['intensity'] = float(intensity)
        rows['ring'] = rings
        rows['timestamp'] = float(timestamp)
        return rows

    def _direction_buckets(self):
        if self._buckets is None:
            azimuth = np.asarray(self.grid.azimuth_deg, dtype=np.float64).ravel()
            elevation = np.asarray(self.grid.elevation_deg, dtype=np.float64).ravel()
            low = float(azimuth.min()) - 1.0
            width = 0.5
            bins = np.floor((azimuth - low) / width).astype(np.int64)
            unique, inverse = np.unique(bins, return_inverse=True)
            self._buckets = dict(
                azimuth=azimuth, elevation=elevation, low=low, width=width,
                index=dict((int(value), position)
                           for position, value in enumerate(unique)),
                cells=[np.flatnonzero(inverse == position) for position in range(len(unique))],
                columns=int(self.grid.shape[1]))
        return self._buckets

    def _nearest_rings(self, points):
        buckets = self._direction_buckets()
        azimuth = np.degrees(np.arctan2(points[:, 1], points[:, 0]))
        elevation = np.degrees(np.arctan2(points[:, 2], np.hypot(points[:, 0], points[:, 1])))
        point_bins = np.floor((azimuth - buckets['low']) / buckets['width']).astype(np.int64)
        rings = np.zeros(len(points), dtype=np.uint16)
        for value in np.unique(point_bins):
            selected = np.flatnonzero(point_bins == value)
            cells = []
            for offset in (-1, 0, 1):
                position = buckets['index'].get(int(value) + offset)
                if position is not None:
                    cells.append(buckets['cells'][position])
            if not cells:
                rings[selected] = self._global_nearest(azimuth[selected], elevation[selected])
                continue
            candidate = np.concatenate(cells)
            for start in range(0, len(selected), 1024):
                chunk = selected[start:start + 1024]
                delta_az = azimuth[chunk][:, None] - buckets['azimuth'][candidate][None, :]
                delta_el = elevation[chunk][:, None] - buckets['elevation'][candidate][None, :]
                best = (delta_az * delta_az + delta_el * delta_el).argmin(axis=1)
                rings[chunk] = candidate[best] // buckets['columns']
        return rings

    def _global_nearest(self, azimuth, elevation):
        buckets = self._direction_buckets()
        rings = np.zeros(len(azimuth), dtype=np.uint16)
        for start in range(0, len(azimuth), 64):
            chunk = slice(start, start + 64)
            delta_az = azimuth[chunk][:, None] - buckets['azimuth'][None, :]
            delta_el = elevation[chunk][:, None] - buckets['elevation'][None, :]
            best = (delta_az * delta_az + delta_el * delta_el).argmin(axis=1)
            rings[chunk] = best // buckets['columns']
        return rings

    def install_ground(self, normal=(0.0, 0.0, 1.0), offset_m=0.0, frame_id=None):
        """声明地面平面（米），不是拟合结果，也不等于物理地面认证。

        契约与 ``core.range_features.bound_ground`` 一致：``status='valid'``、
        单位法向、有限 offset、且绑定坐标必须是 ``RAW/<frame>``。
        """
        plane = np.asarray(normal, dtype=np.float64)
        if plane.shape != (3,) or not np.isfinite(plane).all():
            raise ValueError('normal must be a finite 3-vector')
        length = float(np.linalg.norm(plane))
        if abs(length - 1.0) > 1e-6:
            raise ValueError('normal must be unit length')
        offset = _finite_number(offset_m, 'offset_m')
        identifier = self.frame_id if frame_id is None else str(frame_id)
        if self.identity['coordinate'] != 'RAW/' + identifier:
            raise ValueError('ground frame/coordinate mismatch')
        ground = dict(status='valid', normal=plane.tolist(), offset_m=offset, frame=identifier,
                      binding=dict(self.identity))
        self.runtime.ground = ground
        self.runtime.ground_sha = hashlib.sha256(
            json.dumps(ground, sort_keys=True, allow_nan=False).encode()).hexdigest()
        return ground

    def clear_ground(self):
        self.runtime.ground = None
        self.runtime.ground_sha = None

    # ------------------------------------------------------------------ 逐帧
    def feed(self, rows, stamp_s, frame_index):
        """消费一帧：``rows`` 为 28 字节测量行，``stamp_s`` 为源时刻秒，``frame_index`` 递增。"""
        array = _rows_array(rows)
        stamp = _finite_number(stamp_s, 'stamp_s')
        if isinstance(frame_index, bool) or not isinstance(frame_index, int) or frame_index < 0:
            raise ValueError('frame_index must be a non-negative integer')
        if self.processed == 0 and frame_index != 0:
            raise ValueError('the explicit empty prefix must start at frame_index 0')
        if self.last_stamp is not None and (stamp <= self.last_stamp or frame_index <= self.last_index):
            raise ValueError('non-increasing stamp/frame index: start a new session instead of '
                             'silently rebinding')
        result, frame, components = self.runtime.update(array, stamp, frame_index)
        self.processed += 1
        self.last_stamp, self.last_index = stamp, frame_index
        return self._result(result, frame, components, frame_index)

    def _result(self, result, frame, components, frame_index):
        height, width = frame.grid.shape
        labels = np.full((height, width), -1, dtype=np.int32)
        lifted = []
        foreground_cells = 0
        for component in components:
            cells = np.asarray(component['cells'], dtype=np.int64)
            rows = np.asarray(component['source_rows'], dtype=np.int64)
            labels.ravel()[cells] = component['component_id']
            foreground_cells += len(cells)
            lifted.append(dict(id=int(component['component_id']),
                               cells=cells, sourceRows=rows,
                               xyz=frame.xyz[rows].astype(np.float64),
                               points=int(component['points']),
                               retained=bool(component['retained']),
                               minPoints=int(component['min_points']),
                               semantic=component['semantic']))
        record = result['tracking']
        rule = result['rule']
        rows = np.asarray(record['target_source_rows'], dtype=np.int64)
        target = self._target(record, frame, rows, rule['features'])
        skeleton = None
        if len(rows):
            skeleton = project_regions(estimate_skeleton(frame.xyz[rows], rows), frame)
        posture = self.posture.update(rule['features'], record, self.runtime.binding)
        body = None
        if self.body_parts_enabled:
            body = self._body(frame, rows) if len(rows) else dict(
                method=BODY_METHOD, parts=[], reason='no_locked_target')
        return dict(
            version=VERSION, semantic=SEMANTIC, confirmedEnabled=False,
            frame=dict(index=int(frame_index), stampS=float(record['time_s']),
                       skippedInputFrames=int(result['skipped_input_frames'])),
            status=result['status'],
            binding=dict(session=self.identity['session'],
                         coordinate=self.identity['coordinate'],
                         gridSha256=self.grid.sha256),
            image2d=dict(shape=[height, width],
                         validCells=int(frame.valid.sum()),
                         foregroundCells=foreground_cells,
                         rangeM=frame.range_m,
                         valid=frame.valid,
                         labels=labels,
                         components=lifted,
                         rejected=dict((name, int(len(values)))
                                       for name, values in frame.rejected.items())),
            target3d=target,
            skeleton=skeleton,
            bodyParts=body,
            fall=dict(state=rule['state']['state'],
                      reasonCodes=list(rule['state']['reason_codes']),
                      confirmedEnabled=bool(rule['state']['confirmed_enabled']),
                      modeVerified=bool(rule['state']['mode_verified']),
                      newEvent=rule['state']['new_event'],
                      posture=posture),
            tracks=[dict(id=t['track_id'], status=t['status'], observed=bool(t['observed']),
                         points=len(t['source_rows'])) for t in record['tracks']],
            timings=dict((name, float(value)) for name, value in result['timings'].items()),
            configSha256=result['config_sha256'])

    def _target(self, record, frame, rows, temporal):
        empty = dict(trackId=None, reason=record['target_reason'], sourceRows=np.zeros(0, np.int64),
                     xyz=np.zeros((0, 3)), pointCount=0, tentative=False)
        if not len(rows):
            return empty
        features = record['target_features'] or {}
        xyz = frame.xyz[rows].astype(np.float64)
        chosen = next((t for t in record['tracks'] if t['track_id'] == record['target_track_id']), {})
        ground_relative = bool(temporal.get('ground_relative'))
        return dict(trackId=record['target_track_id'], reason=None,
                    sourceRows=rows, xyz=xyz, pointCount=int(len(rows)),
                    tentative=chosen.get('status') == 'tentative',
                    centerSourceM=features.get('center_m'),
                    bboxSourceMinM=features.get('bbox_min_m'),
                    bboxSourceMaxM=features.get('bbox_max_m'),
                    heightM=features.get('height_m') if ground_relative else None,
                    heightReason=features.get('height_reason') if not ground_relative
                    else None,
                    heightMedianM=temporal.get('height_median_m'),
                    horizontalExtentM=temporal.get('horizontal_extent_m'),
                    verticality=temporal.get('axis_verticality'),
                    observable=bool(temporal.get('observable')),
                    rangeM=features.get('range_m'),
                    axis=features.get('axis'),
                    velocityMS=chosen.get('velocity_m_s'),
                    selectionScore=chosen.get('selection_score'))

    def _body(self, frame, rows):
        indices = frame.source_rows[::-1, ::-1]
        height, width = frame.grid.shape
        try:
            proposal = propose_body_parts(indices, frame.xyz, rows)
        except (ValueError, TypeError, FloatingPointError) as error:
            return dict(method=BODY_METHOD, parts=[], reason='body_proposal_rejected',
                        error=str(error))
        parts = []
        for slot in proposal:
            pixels = slot.get('pixels')
            if pixels:
                pixels = np.asarray(pixels, dtype=np.int64)
                y, x = pixels // width, pixels % width
                parts.append(dict(part=slot['part'], state=slot['state'],
                                  sourceRows=indices.ravel()[pixels].astype(np.int64),
                                  cells=(height - 1 - y) * width + (width - 1 - x),
                                  supportCount=int(len(pixels)),
                                  uncertainty=list(slot['origin'].get('uncertainty') or []),
                                  evidence=slot['origin'].get('evidence')))
            else:
                parts.append(dict(part=slot['part'], state=slot['state'],
                                  sourceRows=np.zeros(0, np.int64), cells=np.zeros(0, np.int64),
                                  supportCount=0,
                                  uncertainty=list(slot['origin'].get('uncertainty') or []),
                                  evidence=slot['origin'].get('evidence')))
        return dict(method=BODY_METHOD, names=list(BODY_NAMES), parts=parts, reason=None)


def summary(result):
    """JSON 安全的小结：不含点坐标/距离图，只含计数、跟踪、姿态与耗时。"""
    image, target, fall = result['image2d'], result['target3d'], result['fall']
    height = target.get('heightM') or {}
    parts = result['bodyParts']
    return dict(
        version=result['version'], semantic=result['semantic'],
        confirmedEnabled=result['confirmedEnabled'],
        status=result['status'],
        frameIndex=result['frame']['index'], stampS=result['frame']['stampS'],
        skippedInputFrames=result['frame']['skippedInputFrames'],
        validCells=image['validCells'], foregroundCells=image['foregroundCells'],
        rejected=image['rejected'],
        components=[dict(id=c['id'], points=c['points'], retained=c['retained'])
                    for c in image['components']],
        tracks=result['tracks'],
        target=dict(trackId=target['trackId'], points=target['pointCount'],
                    reason=target.get('reason'),
                    heightMedianM=target.get('heightMedianM') or height.get('median'),
                    heightMaxM=height.get('max'),
                    heightReason=target.get('heightReason'),
                    horizontalExtentM=target.get('horizontalExtentM'),
                    verticality=target.get('verticality'),
                    observable=target.get('observable'),
                    bboxSourceMinM=target.get('bboxSourceMinM'),
                    bboxSourceMaxM=target.get('bboxSourceMaxM')),
        skeletonNodes=sorted((result['skeleton'] or {}).get('nodes') or {}),
        bodyParts=None if parts is None else
        dict(method=parts['method'], reason=parts.get('reason'),
             visible=[p['part'] for p in parts['parts'] if p['state'] == 'visible'],
             counts=dict((p['part'], p['supportCount']) for p in parts['parts']),
             reasons=dict((p['part'], (p['evidence'] or {}).get('reason'))
                          for p in parts['parts'] if p['state'] != 'visible')),
        fallState=fall['state'], fallReasonCodes=fall['reasonCodes'],
        posture=fall['posture']['state'], postureReason=fall['posture']['reason'],
        timingsMs=dict((name, round(value, 3)) for name, value in result['timings'].items()))