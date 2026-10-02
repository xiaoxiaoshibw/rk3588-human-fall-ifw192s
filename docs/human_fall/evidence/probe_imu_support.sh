printf '\n[LIVE_LINK]\n'
ip -br address
printf '\n[SDK_METADATA]\n'
lib=/home/wel/slam_localization_wuhan/src/inno_lidar_ros/third_party/inno_driver/lib/aarch64/libinno_driver.so
ls -lh "$lib"
sha256sum "$lib"
printf '\n[SDK_IMU_DECODER_SYMBOLS]\n'
if command -v nm >/dev/null; then nm -D -C "$lib" | grep -Ei 'imu|decode|IFW|FW192|AOD|IFN' | head -n 90; fi
printf '\n[SDK_IMU_STRINGS]\n'
if command -v strings >/dev/null; then strings "$lib" | grep -Ei 'imu|accelerometer|gyroscope|BMI[0-9]|ICM[0-9]|MPU[0-9]|LSM[0-9]|IFW192|FW192' | head -n 90; fi
printf '\n[RUNTIME_MAPPING]\n'
pid=$(pgrep -x inno_lidar_node | head -n 1)
if [ -n "$pid" ]; then grep 'libinno_driver' /proc/$pid/maps 2>/dev/null | head -n 3 || true; fi
printf '\n[POINT_AND_IMU_SAMPLE]\n'
docker exec slam-localization bash -c 'source /opt/ros/noetic/setup.bash; source /root/catkin_ws/devel/setup.bash; timeout 8 rostopic echo -n 1 /innolidar_points/header; echo point_probe_status=$?; timeout 8 rostopic echo -n 1 /inno_imu; echo imu_probe_status=$?'
printf '\n[END]\n'
