printf '\n[DRIVER_STARTUP_LOG_TAIL]\n'
docker logs --tail 100 slam-localization 2>&1 | grep -Ei 'lidar|imu|camera|stereo|error|warn|calib|8080|type|driver|point' | tail -n 60 || true
printf '\n[DRM_DRIVERS]\n'
for d in /sys/class/drm/renderD*; do
  [ -e "$d" ] || continue
  printf '%s\n' "$d"
  readlink -f "$d/device/driver"
  cat "$d/device/uevent" 2>/dev/null | head -n 8
done
printf '\n[ETH2_LINK]\n'
for p in /sys/class/net/eth2/operstate /sys/class/net/eth2/carrier; do printf '%s: ' "$p"; cat "$p"; done
printf '\n[CONTAINER_VIDEO_DEVICES]\n'
docker exec slam-localization bash -c 'ls /dev/video* /dev/media* /dev/dri/renderD* 2>/dev/null || true'
printf '\n[ROS_PACKAGE_LIST_CAMERA_RELATED]\n'
docker exec slam-localization bash -c 'source /opt/ros/noetic/setup.bash; if [ -f /root/catkin_ws/devel/setup.bash ]; then source /root/catkin_ws/devel/setup.bash; fi; rospack list | grep -Ei "camera|stereo|image|depth|realsense|zed|foxglove|inno" || true'
printf '\n[REMOTE_BUILD_FLAGS]\n'
docker exec slam-localization bash -c 'grep -nE "ENABLE_IMU_MSG_PARSE|COMPILE_METHOD|POINT_TYPE" /root/catkin_ws/src/inno_lidar_ros/CMakeLists.txt; grep -n "timestamp" /root/catkin_ws/src/inno_lidar_ros/third_party/inno_driver/inno_driver/msg/imu_types.hpp'
printf '\n[END]\n'
