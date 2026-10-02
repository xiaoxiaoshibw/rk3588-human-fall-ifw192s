#!/bin/bash
# HF-02 R2: record the cold-workspace one-pass build outcome.
# The driver CMakeLists has no add_dependencies on the generated message
# headers (grep exit 1 in 06_device_checks.txt), so a cold parallel build can
# race message generation; 06 records the deterministic two-pass build that
# actually compiled and linked publish_manager.cpp. This note keeps the
# observation honest, whichever way the cold race lands.
set -u
echo "DATE=$(date -Is)"
docker exec slam-localization bash -lc 'source /opt/ros/noetic/setup.bash; rm -rf /tmp/hf02_r2_cold_ws; mkdir -p /tmp/hf02_r2_cold_ws/src; cp -a /root/catkin_ws/src/inno_lidar_ros /root/catkin_ws/src/inno_lidar_msg /tmp/hf02_r2_cold_ws/src/; cp /tmp/hf02_r2_verify/src/inno_lidar_ros/src/source/publish_manager.cpp /tmp/hf02_r2_cold_ws/src/inno_lidar_ros/src/source/publish_manager.cpp; cd /tmp/hf02_r2_cold_ws; catkin_make -j4 2>&1; echo COLD_ONE_PASS_BUILD_EXIT=$?'
echo "DOCKER_COLD_BUILD_WRAP_EXIT=$?"
echo "SCRIPT_DONE"
