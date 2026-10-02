#!/bin/bash
# HF-01 round 2 strengthened install check: isolated staging workspace with the reused
# decoder package present, so the installed node runs the full default path.
set -u
inner=/tmp/hf01_install_inner_r2b.sh
cat > "$inner" <<'INNER'
#!/bin/bash
source /opt/ros/noetic/setup.bash
rm -rf /tmp/hf01_install_check
mkdir -p /tmp/hf01_install_check/src
cp -r /root/catkin_ws/src/inno_lidar_msg /tmp/hf01_install_check/src/
cp -r /root/catkin_ws/src/human_fall_detection /tmp/hf01_install_check/src/
cp -r /root/catkin_ws/src/human_follow_calibration /tmp/hf01_install_check/src/
cd /tmp/hf01_install_check
timeout 300 catkin_make install > /tmp/hf01_install_build_r2b.log 2>&1
echo "catkin_make install exit=$?"
tail -3 /tmp/hf01_install_build_r2b.log
echo "--- installed files ---"
ls -l install/share/human_fall_detection/config/default.yaml
ls -l install/lib/human_fall_detection/ install/lib/human_follow_calibration/
source install/setup.bash
rospack find human_fall_detection
echo "rospack exit=$?"
python3 - <<'PY'
import os
import rospkg
path = rospkg.RosPack().get_path("human_fall_detection")
config = os.path.join(path, "config", "default.yaml")
print("resolved package:", path)
print("default config exists:", os.path.exists(config))
assert path.startswith("/tmp/hf01_install_check/install/"), path
assert os.path.exists(config)
PY
echo "install-space config check exit=$?"
echo "--- installed node, default config resolution, wait for a fresh frame (15 s) ---"
timeout -s INT 15 rosrun human_fall_detection sensor_health.py --session-id health_install_check_b \
  > /tmp/hf01_install_run_r2b.log 2>&1 &
node_pid=$!
sleep 3
timeout 20 python3 - <<'PY'
import json
import rospy
from std_msgs.msg import String
rospy.init_node("hf01_install_reader_b", anonymous=True)
deadline = rospy.Time.now() + rospy.Duration(12)
payload = None
while rospy.Time.now() < deadline and not rospy.is_shutdown():
    msg = rospy.wait_for_message("/human_fall/health", String, timeout=5)
    payload = json.loads(msg.data)
    if payload["observability"] != "invalid":
        break
print("strict json parse: ok")
print("session:", payload["session_id"])
print("observability:", payload["observability"])
cloud = payload["topics"]["cloud"]
print("cloud status/decode_error:", cloud["status"], cloud["decode_error"])
print("cloud layout valid/point_step:", cloud["layout"]["valid"], cloud["layout"]["point_step"])
print("cloud header==first_point_ts:", cloud["header_equals_first_point_stamp"])
PY
echo "install node reader exit=$?"
kill -INT $node_pid 2>/dev/null
wait $node_pid 2>/dev/null
echo "install node wait exit=$?"
cat /tmp/hf01_install_run_r2b.log
INNER
docker cp "$inner" slam-localization:/tmp/hf01_install_inner_r2b.sh
echo "docker cp exit=$?"
timeout 600 docker exec slam-localization bash /tmp/hf01_install_inner_r2b.sh
echo "exec exit=$?"
echo "--- cleanup temporary workspace ---"
docker exec slam-localization rm -rf /tmp/hf01_install_check /tmp/hf01_install_inner_r2b.sh \
  /tmp/hf01_install_build_r2b.log /tmp/hf01_install_run_r2b.log
echo "cleanup exit=$?"
rm -f "$inner"
