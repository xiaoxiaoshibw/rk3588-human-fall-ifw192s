"""ROS-free live PointCloud2 -> calibrated range image; no inference or disk IO."""
import math
import threading
import time

import numpy as np

from .capture_input import ROW_DTYPE
from .node_runtime import LatestFrameQueue


def pointcloud_rows(msg):
    """按消息声明读取，保留所有点及行号；只在边界打包一次为ScanGrid输入。

    XYZ/intensity=float32, ring=uint16, timestamp=float32/64。逐点时间转为现有
    ROW_DTYPE的float32，仅为兼容离线契约；精确帧身份使用header的整数秒/纳秒。
    """
    width, height = int(msg.width), int(msg.height)
    step, stride = int(msg.point_step), int(msg.row_step)
    if (width < 0 or height <= 0 or width * height > 262144 or step <= 0
            or stride < width * step or stride * height > 64 * 1024 * 1024):
        raise ValueError('invalid or oversized PointCloud2 dimensions/strides')
    data = memoryview(msg.data)
    if not data.c_contiguous or data.nbytes != stride * height:
        raise ValueError('PointCloud2 data length/contiguity mismatch')
    fields = {}
    for field in msg.fields:
        if field.name in fields:
            raise ValueError('duplicate field: ' + field.name)
        fields[field.name] = field
    names = ('x', 'y', 'z', 'intensity', 'ring', 'timestamp')
    formats, offsets, intervals = [], [], []
    endian = '>' if msg.is_bigendian else '<'
    for name in names:
        field = fields.get(name)
        allowed = (7, 8) if name == 'timestamp' else ((4,) if name == 'ring' else (7,))
        if field is None or field.count != 1 or field.datatype not in allowed:
            raise ValueError('missing or unsupported field: ' + name)
        dtype = np.dtype(endian + {4: 'u2', 7: 'f4', 8: 'f8'}[field.datatype])
        start, end = int(field.offset), int(field.offset) + dtype.itemsize
        if start < 0 or end > step or any(start < b and a < end for a, b in intervals):
            raise ValueError('out-of-bounds or overlapping field: ' + name)
        formats.append(dtype)
        offsets.append(start)
        intervals.append((start, end))
    packed = np.zeros(width * height, dtype=ROW_DTYPE)
    if not len(packed):
        return packed
    dtype = np.dtype(dict(names=names, formats=formats, offsets=offsets, itemsize=step))
    view = np.ndarray((height, width), dtype=dtype, buffer=data, strides=(stride, step))
    # 不过滤NaN/零点，避免source_rows与原始PointCloud2点索引错位。
    with np.errstate(over='raise', invalid='ignore'):
        for name in names:
            packed[name] = view[name].reshape(-1)
    return packed


def preview_rgb(frame):
    rgb = np.zeros(frame.valid.shape + (3,), dtype=np.uint8)
    t = np.clip((frame.range_m[frame.valid] - .1) / 7.9, 0, 1)
    rgb[frame.valid] = np.column_stack((255*(1-t), 255*(1-np.abs(2*t-1)), 255*t)).astype('u1')
    return rgb[::-1, ::-1]


def image_buffers(frame, preview=False):
    """与离线v2一致旋转180度；返回ROS Image所需的无压缩字节。"""
    arrays = {
        'range': ('32FC1', frame.range_m[::-1, ::-1].astype('<f4')),
        'source_rows': ('32SC1', frame.source_rows[::-1, ::-1].astype('<i4')),
        'valid': ('mono8', frame.valid[::-1, ::-1].astype('u1') * 255),
    }
    if preview:
        arrays['preview'] = ('rgb8', preview_rgb(frame))
    return {name: dict(encoding=encoding, height=a.shape[0], width=a.shape[1],
                      is_bigendian=False, step=a.shape[1]*a.dtype.itemsize*(3 if a.ndim == 3 else 1),
                      data=a.tobytes()) for name, (encoding, a) in arrays.items()}


class LiveRange:
    """单worker消费；回调仅替换最新消息。时效以本机单调接收时钟度量。"""

    def __init__(self, grid, frame_id, max_age_s=.5, preview=False, clock=time.perf_counter):
        if not frame_id or not math.isfinite(max_age_s) or max_age_s <= 0:
            raise ValueError('explicit frame_id and positive max_age_s required')
        self.grid, self.frame_id, self.max_age_s = grid, frame_id, max_age_s
        self.preview, self.clock = preview, clock
        self.queue = LatestFrameQueue(1)
        self._submit_lock = threading.Lock()
        self.received = self.processed = self.invalid = self.expired = 0

    def submit(self, msg):
        received = self.clock()
        with self._submit_lock:
            self.received += 1
            self.queue.put((received, msg))

    def process_latest(self):
        item = self.queue.take()
        if item is None:
            return None
        received, msg = item
        started = self.clock()
        report = dict(schema='lidar_range_live/1', status='invalid', images={}, source=None,
                      grid_sha256=self.grid.sha256, quantity='radial_range', units='m',
                      orientation='native_grid_rotated_180_for_view', interpolation=False,
                      human_semantic='UNKNOWN', fall_event='UNKNOWN',
                      timestamp_precision='point_time_float32; header_integer_sec_nsec',
                      queue_age_ms=(started-received)*1000)
        try:
            header = msg.header
            seq, sec, nsec = header.seq, header.stamp.secs, header.stamp.nsecs
            if (header.frame_id != self.frame_id
                    or any(isinstance(v, bool) or not isinstance(v, int) or v < 0 for v in (seq, sec, nsec))
                    or nsec >= 1000000000 or sec == nsec == 0):
                raise ValueError('invalid header or unexpected sensor frame_id')
            report['source'] = dict(seq=seq, stamp_sec=sec, stamp_nanosec=nsec, frame_id=header.frame_id)
            if started - received > self.max_age_s:
                report['status'] = 'expired'
            else:
                rows = pointcloud_rows(msg)
                adapted = self.clock()
                frame = self.grid.decode(rows, (header.frame_id, sec, nsec, seq, self.grid.sha256))
                decoded = self.clock()
                images = image_buffers(frame, self.preview)
                finished = self.clock()
                report.update(adapt_ms=(adapted-started)*1000, decode_ms=(decoded-adapted)*1000,
                              image_pack_ms=(finished-decoded)*1000, conversion_ms=(finished-started)*1000,
                              local_frame_age_ms=(finished-received)*1000, input_points=len(rows),
                              valid_pixels=int(frame.valid.sum()),
                              rejected={k:len(v) for k,v in frame.rejected.items()})
                if finished - received > self.max_age_s:
                    report['status'] = 'expired'
                else:
                    report.update(status='ready' if frame.valid.any() else 'no_valid_pixels', images=images)
                    self.processed += 1
        except (ValueError, TypeError, AttributeError, OverflowError, FloatingPointError) as exc:
            report['error'] = str(exc)
            self.invalid += 1
        if report['status'] == 'expired':
            self.expired += 1
        with self._submit_lock:
            report.update(received=self.received, processed=self.processed,
                          invalid=self.invalid, expired=self.expired, queue_overwritten=self.queue.dropped)
        return report
