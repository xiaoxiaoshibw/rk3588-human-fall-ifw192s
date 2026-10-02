#!/bin/bash
# HF-01: catkin_make the new package only; snapshot driver binary before/after.
set -u
inner=/tmp/hf01_build_inner.sh
cat > "$inner" <<'INNER'
#!/bin/bash
source /opt/ros/noetic/setup.bash
cd /root/catkin_ws
echo "--- before: driver binary hash ---"
sha256sum devel/lib/inno_lidar_ros/inno_lidar_node 2>&1
echo "before exit=$?"
echo "--- catkin_make (whitelist keeps existing packages + new one) ---"
timeout 900 catkin_make -DCATKIN_WHITELIST_PACKAGES="inno_lidar_ros;human_follow_calibration;human_fall_detection"
echo "catkin_make exit=$?"
echo "--- after: driver binary hash ---"
sha256sum devel/lib/inno_lidar_ros/inno_lidar_node 2>&1
echo "after exit=$?"
echo "--- runtime package resolution in re-sourced shell ---"
source devel/setup.bash
timeout 5 rospack find human_fall_detection; echo "rospack hfd exit=$?"
timeout 5 rospack find inno_lidar_ros; echo "rospack inno exit=$?"
timeout 5 rospack find human_follow_calibration; echo "rospack hfc exit=$?"
timeout 5 rostopic list; echo "rostopic list exit=$?"
echo "--- installed node files ---"
ls -l devel/lib/human_fall_detection/
echo "ls exit=$?"
timeout 15 rosrun human_fall_detection sensor_health.py --help
echo "rosrun help exit=$?"
INNER
docker cp "$inner" slam-localization:/tmp/hf01_build_inner.sh
echo "docker cp exit=$?"
timeout 1000 docker exec slam-localization bash /tmp/hf01_build_inner.sh
echo "exec exit=$?"
docker exec slam-localization rm -f /tmp/hf01_build_inner.sh
echo "cleanup exit=$?"
rm -f "$inner"
