#!/bin/bash
# HF-01 round 2: isolated staging/install workspace check that config ships into the
# install space and that the installed node resolves its default config. Temporary
# paths only; no active driver/vendor library or remote service is replaced.
set -u
inner=/tmp/hf01_install_inner_r2.sh
cat > "$inner" <<'INNER'
#!/bin/bash
source /opt/ros/noetic/setup.bash
rm -rf /tmp/hf01_install_check
mkdir -p /tmp/hf01_install_check/src
cp -r /root/catkin_ws/src/inno_lidar_msg /tmp/hf01_install_check/src/
cp -r /root/catkin_ws/src/human_fall_detection /tmp/hf01_install_check/src/
cd /tmp/hf01_install_check
timeout 300 catkin_make install > /tmp/hf01_install_build_r2.log 2>&1
echo "catkin_make install exit=$?"
tail -3 /tmp/hf01_install_build_r2.log
echo "--- install manifest content ---"
ls -l install/share/human_fall_detection/config/default.yaml
echo "default config ls exit=$?"
ls -l install/share/human_fall_detection/
echo "share ls exit=$?"
head -3 install/share/human_fall_detection/config/default.yaml
echo "config head exit=$?"
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
echo "--- installed node with default config resolution (15 s) ---"
timeout -s INT 15 rosrun human_fall_detection sensor_health.py --session-id health_install_check \
  > /tmp/hf01_install_run_r2.log 2>&1 &
node_pid=$!
sleep 3
timeout 15 python3 - <<'PY'
import json
import rospy
from std_msgs.msg import String
rospy.init_node("hf01_install_reader", anonymous=True)
msg = rospy.wait_for_message("/human_fall/health", String, timeout=10)
payload = json.loads(msg.data)
print("install-space node published health; session:", payload["session_id"])
print("observability:", payload["observability"])
PY
echo "install node reader exit=$?"
kill -INT $node_pid 2>/dev/null
wait $node_pid 2>/dev/null
echo "install node wait exit=$?"
cat /tmp/hf01_install_run_r2.log
INNER
docker cp "$inner" slam-localization:/tmp/hf01_install_inner_r2.sh
echo "docker cp exit=$?"
timeout 600 docker exec slam-localization bash /tmp/hf01_install_inner_r2.sh
echo "exec exit=$?"
echo "--- cleanup temporary workspace ---"
docker exec slam-localization rm -rf /tmp/hf01_install_check /tmp/hf01_install_inner_r2.sh \
  /tmp/hf01_install_build_r2.log /tmp/hf01_install_run_r2.log
echo "cleanup exit=$?"
rm -f "$inner"
