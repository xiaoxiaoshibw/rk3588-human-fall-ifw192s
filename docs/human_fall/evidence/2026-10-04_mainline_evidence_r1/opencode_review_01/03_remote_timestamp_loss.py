"""GL-E01 R1 independent timestamp quantization probe (remote, read-only).

Reads the original bag's float64 point timestamp at offset 18, casts to float32,
and reports the true max absolute numeric loss over every point and the raw
value where it occurs. No unit/clock claim is made.
"""
import json
from pathlib import Path
import sys
import time

import numpy as np

sys.path.insert(0, '/opt/ros/noetic/lib/python3/dist-packages')
import rosbag

PATH = '/root/catkin_ws/captures_remote/cap_20261002_163621.bag'
EXPECTED_SHA = 'bbbc0c00122c68c9c71cd6a799e4ee977f839cc4904d733f9660998df0ebd378'


def main():
    started = time.time()
    loss_max = 0.0
    loss_at = None
    ts_min = ts_max = None
    n_points = 0
    n_frames = 0
    n_nonfinite_ts = 0
    with rosbag.Bag(PATH, 'r') as bag:
        topic = [n for n, v in bag.get_type_and_topic_info().topics.items()
                 if v.msg_type == 'sensor_msgs/PointCloud2']
        if topic != ['/innolidar_points']:
            raise ValueError('unexpected PointCloud2 topics: %r' % (topic,))
        for _, msg, _ in bag.read_messages(topics=topic):
            raw = np.frombuffer(msg.data, dtype=np.uint8).reshape(
                msg.width * msg.height, msg.point_step)
            ts64 = raw[:, 18:26].copy().view('<f8').reshape(-1)
            bad = ~np.isfinite(ts64)
            n_nonfinite_ts += int(bad.sum())
            good = ts64[~bad]
            n_points += int(good.size)
            n_frames += 1
            if good.size:
                cast = good.astype('<f4').astype('<f8')
                diff = np.abs(good - cast)
                i = int(np.argmax(diff))
                if float(diff[i]) > loss_max:
                    loss_max = float(diff[i])
                    loss_at = float(good[i])
                lo, hi = float(good.min()), float(good.max())
                ts_min = lo if ts_min is None else min(ts_min, lo)
                ts_max = hi if ts_max is None else max(ts_max, hi)
    print(json.dumps(dict(
        kind='gle01_r1_independent_remote_timestamp_loss', schema=1,
        bag_sha_declared=EXPECTED_SHA, frames=n_frames, points=n_points,
        nonfinite_timestamps=n_nonfinite_ts,
        max_abs_float64_to_float32_loss=loss_max,
        raw_value_at_max_loss=loss_at,
        raw_range=[ts_min, ts_max],
        units_verified=False, clock_sync_verified=False,
        old_microsecond_claim_supported=False,
        note='loss in raw device seconds; no unit inference performed',
        elapsed_s=time.time() - started)))


if __name__ == '__main__':
    main()
