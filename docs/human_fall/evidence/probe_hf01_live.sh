#!/bin/bash
# HF-01 read-only live probe on welcomtech. Every sampling command has an explicit timeout.
set -u
section() { printf '\n[%s]\n' "$1"; }

section DATE
date -Is
echo "exit=$?"

section LIDAR_STACK_SERVICE
timeout 5 systemctl is-active lidar-stack.service
echo "exit=$?"

section CARRIER
timeout 5 ip -br address
echo "exit=$?"

section CONTAINER
timeout 5 docker ps --format '{{.Names}} {{.Image}} {{.Status}}'
echo "exit=$?"

section SRC_TREE
timeout 5 ls /home/wel/slam_localization_wuhan/src
echo "exit=$?"

inner=/tmp/hf01_probe_inner.sh
cat > "$inner" <<'INNER'
#!/bin/bash
source /opt/ros/noetic/setup.bash
source /root/catkin_ws/devel/setup.bash
echo "[CACHE_WHITELIST]"; grep -E 'CATKIN_WHITELIST_PACKAGES' /root/catkin_ws/build/CMakeCache.txt; echo "exit=$?"
echo "[CACHE_SOURCE_DIR]"; grep -E 'CMAKE_HOME_DIRECTORY|catkin_SOURCE_DIR' /root/catkin_ws/build/CMakeCache.txt | head -n 4; echo "exit=$?"
echo "[ROSPACK_BASELINE]"; timeout 5 rospack find inno_lidar_ros; echo "exit=$?"
echo "[ROSPACK_CALIBRATION]"; timeout 5 rospack find human_follow_calibration; echo "exit=$?"
echo "[NODES]"; timeout 5 rosnode list; echo "exit=$?"
echo "[TOPICS]"; timeout 5 rostopic list; echo "exit=$?"
echo "[HZ_CLOUD]"; timeout -s INT 8 rostopic hz -w 20 /innolidar_points; echo "exit=$?"
echo "[HZ_IMU]"; timeout -s INT 8 rostopic hz -w 200 /inno_imu; echo "exit=$?"
echo "[HZ_DEVICE]"; timeout -s INT 8 rostopic hz -w 20 /device_status; echo "exit=$?"
echo "[PYTHON]"; python3 --version; python3 -c 'import numpy; print("numpy", numpy.__version__)'; echo "exit=$?"
echo "[ROSBAG_MODULE]"; python3 -c 'import rosbag; print("rosbag python module ok")'; echo "exit=$?"
INNER
docker cp "$inner" slam-localization:/tmp/hf01_probe_inner.sh
echo "docker cp exit=$?"
timeout 90 docker exec slam-localization bash /tmp/hf01_probe_inner.sh
echo "docker exec exit=$?"
docker exec slam-localization rm -f /tmp/hf01_probe_inner.sh
echo "cleanup exit=$?"
rm -f "$inner"
