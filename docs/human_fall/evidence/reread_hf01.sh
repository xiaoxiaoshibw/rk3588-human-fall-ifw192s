#!/bin/bash
# HF-01: re-read health JSON and point-cloud layout from the recorded bag.
set -u
inner=/tmp/hf01_reread_inner.sh
cat > "$inner" <<'INNER'
#!/bin/bash
source /opt/ros/noetic/setup.bash
cd /root/catkin_ws
timeout 60 python3 - <<'PY'
import json
import sys
import rosbag
sys.path.insert(0, "/root/catkin_ws/src/human_fall_detection/scripts")
from sensor_health import pointcloud_layout, read_point_timestamps

bag_path = "/root/catkin_ws/human_fall_sessions/hf01_verify.bag"
with rosbag.Bag(bag_path) as bag:
    health_raw = None
    cloud_msg = None
    for _topic, msg, _t in bag.read_messages(topics=["/human_fall/health"]):
        health_raw = msg.data
        break
    for _topic, msg, _t in bag.read_messages(topics=["/innolidar_points"]):
        cloud_msg = msg
        break
health = json.loads(health_raw)
print("health from bag: strict json parse ok")
print(json.dumps(health, indent=2, sort_keys=True, allow_nan=False))
layout = pointcloud_layout(cloud_msg)
stamps = read_point_timestamps(cloud_msg)
print("cloud from bag: layout_valid=%s errors=%s point_step=%s width=%s" % (
    layout["valid"], layout["errors"], layout["point_step"], layout["width"]))
print("cloud from bag: first_point_ts=%.9f last_point_ts=%.9f span=%.6f" % (
    stamps[0], stamps[-1], stamps[-1] - stamps[0]))
PY
echo "reread exit=$?"
INNER
docker cp "$inner" slam-localization:/tmp/hf01_reread_inner.sh
echo "docker cp exit=$?"
timeout 90 docker exec slam-localization bash /tmp/hf01_reread_inner.sh
echo "exec exit=$?"
docker exec slam-localization rm -f /tmp/hf01_reread_inner.sh
echo "cleanup exit=$?"
rm -f "$inner"
