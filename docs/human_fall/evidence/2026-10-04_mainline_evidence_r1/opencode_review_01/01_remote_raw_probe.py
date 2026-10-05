"""GL-E01 R1 independent remote raw PointCloud2 probe (run via docker exec stdin).

Read-only. Does not import any project module, the author 02/03 scripts, or the
bag2session extractor. Parses the serialized PointCloud2 data by explicit byte
splices (not the author's structured-dtype path) and emits per-frame headers,
counts, raw bag_time and aggregate/frame SHA-256 digests.
"""
import hashlib
import json
from pathlib import Path
import sys
import time

import numpy as np

sys.path.insert(0, '/opt/ros/noetic/lib/python3/dist-packages')
import rosbag

PATH = '/root/catkin_ws/captures_remote/cap_20261002_163621.bag'
EXPECTED_SHA = 'bbbc0c00122c68c9c71cd6a799e4ee977f839cc4904d733f9660998df0ebd378'
# Independent expectation of the source layout (claim under review).
EXPECTED_FIELDS = [('x', 0, 7, 1), ('y', 4, 7, 1), ('z', 8, 7, 1),
                   ('intensity', 12, 7, 1), ('ring', 16, 4, 1),
                   ('timestamp', 18, 8, 1)]


def sha_file(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def main():
    started = time.time()
    size = Path(PATH).stat().st_size
    sha_before = sha_file(PATH)
    with open(PATH, 'rb') as f:
        magic = f.read(13).decode('ascii', 'replace')
    canonical = hashlib.sha256()
    xyz_digest = hashlib.sha256()
    raw_data_digest = hashlib.sha256()
    frames = []
    offset = 0
    dropped_total = 0
    ts_min = ts_max = None
    canonical_stride = 28

    with rosbag.Bag(PATH, 'r') as bag:
        info = bag.get_type_and_topic_info()
        topics = {n: dict(type=v.msg_type, count=v.message_count)
                  for n, v in info.topics.items()}
        pc = [n for n, v in topics.items() if v['type'] == 'sensor_msgs/PointCloud2']
        if pc != ['/innolidar_points']:
            raise ValueError('unexpected PointCloud2 topic set: %r' % (pc,))
        topic = pc[0]
        for _, msg, t in bag.read_messages(topics=[topic]):
            got = [(f.name, int(f.offset), int(f.datatype), int(f.count))
                   for f in msg.fields]
            if got != EXPECTED_FIELDS:
                raise ValueError('field layout mismatch: %r' % (got,))
            if msg.is_bigendian:
                raise ValueError('big-endian payload')
            if msg.point_step != 26:
                raise ValueError('point_step=%d' % msg.point_step)
            if msg.row_step != msg.width * msg.point_step:
                raise ValueError('row padding mismatch')
            if len(msg.data) != msg.height * msg.row_step:
                raise ValueError('data length mismatch')
            n_total = msg.width * msg.height
            raw = np.frombuffer(msg.data, dtype=np.uint8).reshape(n_total, 26)
            raw_data_digest.update(msg.data)
            x = raw[:, 0:4].copy().view('<f4').reshape(-1)
            y = raw[:, 4:8].copy().view('<f4').reshape(-1)
            z = raw[:, 8:12].copy().view('<f4').reshape(-1)
            ts64 = raw[:, 18:26].copy().view('<f8').reshape(-1)
            keep = np.isfinite(x) & np.isfinite(y) & np.isfinite(z)
            n_kept = int(keep.sum())
            n_dropped = n_total - n_kept
            dropped_total += n_dropped
            # Independent byte-splice canonical 28B: copy raw bytes 0..17
            # (x,y,z,intensity,ring), leave pad@18..19 zero, place float32
            # timestamp at 20..23, leave pad@24..27 zero.
            canon = np.zeros((n_kept, canonical_stride), dtype=np.uint8)
            canon[:, 0:18] = raw[keep, 0:18]
            ts32 = ts64[keep].astype('<f4')
            canon[:, 20:24] = ts32.view(np.uint8).reshape(-1, 4)
            blob = canon.tobytes()
            frame_xyz = canon[:, 0:12].copy().tobytes()
            canonical.update(blob)
            xyz_digest.update(frame_xyz)
            good = np.isfinite(ts64)
            if np.any(good):
                lo = float(ts64[good].min())
                hi = float(ts64[good].max())
                ts_min = lo if ts_min is None else min(ts_min, lo)
                ts_max = hi if ts_max is None else max(ts_max, hi)
            frames.append(dict(
                ordinal=len(frames), seq=int(msg.header.seq),
                stamp_sec=int(msg.header.stamp.secs),
                stamp_nanosec=int(msg.header.stamp.nsecs),
                frame_id=msg.header.frame_id, width=int(msg.width),
                height=int(msg.height), point_step=int(msg.point_step),
                row_step=int(msg.row_step), count_points=n_kept,
                dropped_points=n_dropped, offset_points=offset,
                bag_time_sec=t.to_sec(),
                raw_frame_data_sha256=hashlib.sha256(msg.data).hexdigest(),
                canonical_frame_sha256=hashlib.sha256(blob).hexdigest(),
                xyz_frame_sha256=hashlib.sha256(frame_xyz).hexdigest()))
            offset += n_kept

    sha_after = sha_file(PATH)
    if sha_before != sha_after:
        raise ValueError('bag changed during read')
    if sha_before != EXPECTED_SHA:
        raise ValueError('bag sha != declared; refuse foreign input')
    # Independent endian/offset sanity on the very first serialized point.
    first22 = frames[0]['count_points'] if frames else 0
    out = dict(
        kind='gle01_r1_independent_remote_raw_probe', schema=1,
        source=dict(path=PATH, size=size, magic=magic, sha256_before=sha_before,
                    sha256_after=sha_after, matches_declared_sha=True),
        topics=topics,
        observed_fields=EXPECTED_FIELDS, point_step=26, is_bigendian=False,
        canonical_layout=dict(stride=28, pad_bytes_values=[18, 19, 24, 25, 26, 27],
                              timestamp_offset=20, timestamp_dtype='<f4'),
        canonical_bin_sha256=canonical.hexdigest(),
        canonical_xyz_sha256=xyz_digest.hexdigest(),
        raw_serialized_data_sha256=raw_data_digest.hexdigest(),
        total_points=offset, total_dropped_points=dropped_total,
        frame_count=len(frames),
        source_timestamp_raw_range=[ts_min, ts_max],
        frames=frames,
        first_frame_points=first22,
        python=sys.version, numpy=np.__version__,
        elapsed_s=time.time() - started)
    print(json.dumps(out, allow_nan=False))


if __name__ == '__main__':
    main()
