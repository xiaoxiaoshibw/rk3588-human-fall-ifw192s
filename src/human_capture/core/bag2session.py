"""bag → meta.json + points.bin 抽取。

读取 record_session.py 写的 .bag（rosbag python 模块），逐帧解 PointCloud2
的 packed 字段，按 HC-03 契约的 28 字节行主序写出 points.bin，同时生成 meta.json。

设计约束：
- 单进程单线程；numpy 一次性把整个 message.data 转 np.frombuffer 再按 field 切片，
  避免 per-point python 循环（49K 点 × 89 帧，纯 Python 循环要分钟级）。
- is_dense=False 必滤 NaN/Inf（xyz 任一非法即丢点），把损失点记进每帧 dropped_points。
- timestamp 字段在原始 bag 里是 float64@18，转 float32 存（ns 级精度对应用太晚，
  差分窗口 1s 内误差 <0.1µs）；ring 是 uint16@16 原样。
- 文件体大小：50帧×49k×28B ≈ 69 MB，写盘 time.sleep(0) 粒度的 I/O，不归我们管。

错误语义：任何一步失败 raise ExtractError，由 capture_server watcher 接 → failed(reason)。
"""

import hashlib
import json
import os
import struct

import numpy as np

SERVICE_VERSION = "0.1.0"
EXTRACTION_TOOL = "bag2session/" + SERVICE_VERSION
FORMAT = "human_capture_session"
FORMAT_VERSION = 1
POINT_STRIDE_BYTES = 28   # 见 docs/human_capture/tickets/HC-03.md "格式定稿"

# PointCloud2 datatype 枚举（ROS 标准）

_DTYPES = {
    7: np.dtype("<f4"),    # FLOAT32
    8: np.dtype("<f8"),    # FLOAT64
    4: np.dtype("<u2"),    # UINT16
    3: np.dtype("<i2"),    # INT16
    5: np.dtype("<u4"),    # UINT32
    6: np.dtype("<i4"),    # INT32
    2: np.dtype("<u1"),    # UINT8
}


class ExtractError(Exception):
    pass


def _topic_for_points(bag):
    """找一个看上去像主点云的话题：类型 PointCloud2、消息数最多。"""
    info = bag.get_type_and_topic_info()
    candidates = [(name, t) for name, t in info.topics.items()
                  if t.msg_type == "sensor_msgs/PointCloud2"]
    if not candidates:
        raise ExtractError("bag 中没有 PointCloud2 话题")
    candidates.sort(key=lambda item: -item[1].message_count)
    return candidates[0][0]


def _check_fields(fields, expected):
    """验证 fields 列表包含预期字段。返回 {name: (offset, datatype)}。"""
    got = {f.name: (f.offset, f.datatype) for f in fields}
    missing = [name for name in expected if name not in got]
    if missing:
        raise ExtractError("PointCloud2 缺字段: %s" % ",".join(missing))
    return got


def _message_points_array(msg):
    """单帧 → 结构化 numpy 数组（按 28 字节 stride 打包好）。
    返回 (packed_bytes, n_points, n_dropped)。packed_bytes 直接 append 到文件。
    """
    if msg.is_bigendian:
        raise ExtractError("big-endian PointCloud2 不支持")
    if msg.point_step < 26:
        raise ExtractError("point_step=%d 小于预期 26" % msg.point_step)

    fields = _check_fields(msg.fields, ("x", "y", "z", "intensity", "ring", "timestamp"))
    n_total = msg.width * msg.height
    if n_total == 0:
        return b"", 0, 0

    raw = np.frombuffer(bytes(msg.data), dtype=np.uint8).reshape(n_total, msg.point_step)

    def _col(name):
        offset, dtype = fields[name]
        width = _DTYPES[dtype].itemsize
        return raw[:, offset:offset + width].copy().view(_DTYPES[dtype]).reshape(-1)

    x = _col("x").astype(np.float32)
    y = _col("y").astype(np.float32)
    z = _col("z").astype(np.float32)
    intensity = _col("intensity").astype(np.float32)
    ring = _col("ring").astype(np.uint16)
    ts = _col("timestamp").astype(np.float64).astype(np.float32)

    # NaN/Inf 过滤（xyz 任一非法即丢）
    keep = np.isfinite(x) & np.isfinite(y) & np.isfinite(z)
    n_kept = int(keep.sum())
    n_dropped = n_total - n_kept

    if n_kept == 0:
        return b"", 0, n_dropped

    # 用结构化 dtype 一次打包成 28 字节行
    row_dtype = np.dtype([
        ("x", "<f4"),            # 0
        ("y", "<f4"),            # 4
        ("z", "<f4"),            # 8
        ("intensity", "<f4"),    # 12
        ("ring", "<u2"),         # 16
        ("_pad1", "<u2"),        # 18 (0)
        ("timestamp", "<f4"),    # 20
        ("_pad2", "<f4"),        # 24 (0)
    ])
    assert row_dtype.itemsize == POINT_STRIDE_BYTES
    packed = np.zeros(n_kept, dtype=row_dtype)
    packed["x"] = x[keep]
    packed["y"] = y[keep]
    packed["z"] = z[keep]
    packed["intensity"] = intensity[keep]
    packed["ring"] = ring[keep]
    packed["timestamp"] = ts[keep]

    return packed.tobytes(), n_kept, n_dropped


def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def extract(bag_path, session_dir, session_id, topics_extra=()):
    """主入口。返回写出的 meta dict。失败 raise ExtractError。

    bag_path:    record_session.py 录出的 .bag
    session_dir: 抽取产物落地目录（通常 <staging>/<sid>/）
    session_id:  cap_...
    topics_extra: 附加要在 meta 记消息数的话题（不抽取点）
    """
    if not os.path.exists(bag_path):
        raise ExtractError("bag 不存在: %s" % bag_path)
    try:
        import rosbag
    except ImportError as exc:
        raise ExtractError("rosbag python module 不可用: %r" % exc)

    os.makedirs(session_dir, exist_ok=True)
    bin_path = os.path.join(session_dir, "points.bin")
    meta_path = os.path.join(session_dir, "meta.json")

    try:
        bag = rosbag.Bag(bag_path)
    except Exception as exc:
        raise ExtractError("rosbag.Bag 打开失败: %r" % exc)

    with bag, open(bin_path, "wb") as bin_fh:
        points_topic = _topic_for_points(bag)

        frames = []
        offset_points = 0
        total_dropped = 0
        first_bag_time = None
        last_bag_time = None

        topics_to_read = [points_topic]
        extra_counts = {}

        for topic, msg, bag_time in bag.read_messages(topics=topics_to_read):
            if first_bag_time is None:
                first_bag_time = bag_time
            last_bag_time = bag_time

            if topic == points_topic:
                packed, n_kept, n_dropped = _message_points_array(msg)
                total_dropped += n_dropped
                bin_fh.write(packed)
                frames.append({
                    "seq": int(msg.header.seq),
                    "stamp_sec": int(msg.header.stamp.secs),
                    "stamp_nanosec": int(msg.header.stamp.nsecs),
                    "bag_time_sec": round(bag_time.to_sec(), 6),
                    "offset_points": offset_points,
                    "count_points": n_kept,
                    "dropped_points": n_dropped,
                })
                offset_points += n_kept
            else:
                extra_counts[topic] = extra_counts.get(topic, 0) + 1

    # bag 其他话题（IMU/devstatus）的光数不进 frames，但要在 meta 记账
    try:
        info = rosbag.Bag(bag_path).get_type_and_topic_info()
        all_topics = {name: t.message_count for name, t in info.topics.items()}
    except Exception:
        all_topics = {}

    duration_sec = 0.0
    if first_bag_time is not None and last_bag_time is not None:
        duration_sec = round(last_bag_time.to_sec() - first_bag_time.to_sec(), 6)

    meta = {
        "format": FORMAT,
        "format_version": FORMAT_VERSION,
        "session_id": session_id,
        "created_iso": _iso_now(),
        "sensor": {"model": "IFW192S", "frame_id": "innolidar"},
        "time_domain": "device_stamp_s_unanchored",
        "duration_sec": duration_sec,
        "topics": sorted(all_topics.keys()),
        "topic_message_counts": all_topics,
        "point_layout": {
            "fields": ["x", "y", "z", "intensity", "ring", "timestamp"],
            "dtypes": ["<f4", "<f4", "<f4", "<f4", "<u2", "<f4"],
            "stride_bytes": POINT_STRIDE_BYTES,
            "endian": "little",
            "pad_offsets_bytes": [18, 24],
        },
        "point_file": "points.bin",
        "point_stride_bytes": POINT_STRIDE_BYTES,
        "total_points": offset_points,
        "total_dropped_points": total_dropped,
        "frames": frames,
        "human_annotations": [],
        "extraction": {
            "tool": EXTRACTION_TOOL,
            "source_bag": bag_path,
            "source_bag_sha256": _sha256(bag_path),
            "point_step_bytes_src": 26,
            "dropped_frames": 0,
        },
    }

    # 原子写 meta
    tmp_meta = meta_path + ".tmp"
    with open(tmp_meta, "w", encoding="utf-8") as fh:
        json.dump(meta, fh, ensure_ascii=False, indent=1, sort_keys=True)
        fh.write("\n")
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp_meta, meta_path)

    meta["_computed"] = {
        "points_bin_sha256": _sha256(bin_path),
        "points_bin_size_bytes": os.path.getsize(bin_path),
    }
    return meta


def _iso_now():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
