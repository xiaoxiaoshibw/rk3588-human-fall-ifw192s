#!/usr/bin/env python3
"""HF-11 preview live input: a clearly SYNTHETIC standing-person point cloud.

Publishes on /hf07_verify/points (not a real human, not /innolidar_points) so the
preview URL can be exercised end-to-end against the isolated verify node without
touching the production topic or the live driver.
"""

import time

import numpy as np
import rospy
from sensor_msgs.msg import PointCloud2, PointField


def make_cloud(points, secs, nsecs, seq=0):
    msg = PointCloud2()
    msg.header.seq = int(seq)
    msg.header.stamp = rospy.Time(int(secs), int(nsecs))
    msg.header.frame_id = "innolidar"
    msg.height = 1
    msg.width = len(points)
    msg.is_bigendian = False
    msg.point_step = 16
    msg.row_step = 16 * len(points)
    msg.is_dense = True
    msg.fields = [PointField("x", 0, 7, 1), PointField("y", 4, 7, 1),
                  PointField("z", 8, 7, 1), PointField("intensity", 12, 7, 1)]
    buf = np.zeros((len(points), 4), dtype="<f4")
    buf[:, :3] = points
    buf[:, 3] = 1.0
    msg.data = buf.tobytes()
    return msg


def main():
    rospy.init_node("hf11_live_demo", disable_signals=True)
    topic = rospy.get_param("~topic", "/hf07_verify/points")
    rate_hz = float(rospy.get_param("~rate_hz", 10.0))
    pub = rospy.Publisher(topic, PointCloud2, queue_size=1)
    rospy.loginfo("hf11_live_demo: SYNTHETIC standing cloud -> %s @ %.1f Hz", topic, rate_hz)
    start = time.time()
    t0 = 1000.0
    seq = 0
    rate = rospy.Rate(rate_hz)
    while not rospy.is_shutdown():
        elapsed = time.time() - start
        z = np.linspace(-1.4, 0.1, 80)
        y = 0.15 * np.sin(elapsed * 0.5)
        points = np.column_stack((np.full(80, 3.0), np.full(80, y), z)).astype("<f4")
        stamp = t0 + elapsed
        secs = int(stamp)
        nsecs = int(round((stamp - secs) * 1e9))
        seq += 1
        pub.publish(make_cloud(points, secs, nsecs, seq))
        rate.sleep()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
