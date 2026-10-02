#!/bin/bash
# HF-02 R3 device evidence script.
# Read-only on the live stack: only isolated /tmp work areas are written.
# C++ is unchanged in R3, so no ROS rebuild is run; the active binary hash is
# checked before and after. Every container command prints its inner exit code;
# the wrapper prints its own.
set -u
echo "DATE=$(date -Is)"
echo "USER=$(id -un) HOST=$(hostname) ARCH=$(uname -m)"
echo "== docker ps =="
docker ps
echo "DOCKER_PS_EXIT=$?"
echo "== container env =="
docker exec slam-localization bash -lc 'python3 --version; echo INNER_PY_VERSION_EXIT=$?; head -2 /etc/os-release; python3 -c "import numpy; print(\"numpy\", numpy.__version__)"; echo INNER_NUMPY_EXIT=$?'
echo "DOCKER_ENV_WRAP_EXIT=$?"
echo "== active driver binary and session dir before any work =="
docker exec slam-localization bash -lc 'sha256sum /root/catkin_ws/devel/lib/inno_lidar_ros/inno_lidar_node; ls -l /root/catkin_ws/human_fall_sessions/'
echo "DOCKER_ACTIVE_BEFORE_WRAP_EXIT=$?"

echo "== unpack uploaded isolated tree =="
docker cp /tmp/hf02_r3_verify.tar slam-localization:/tmp/hf02_r3_verify.tar
echo "DOCKER_CP_EXIT=$?"
docker exec slam-localization bash -lc 'rm -rf /tmp/hf02_r3_verify && mkdir -p /tmp/hf02_r3_verify && tar -xf /tmp/hf02_r3_verify.tar -C /tmp/hf02_r3_verify && echo INNER_UNPACK_EXIT=$?'
echo "DOCKER_UNPACK_WRAP_EXIT=$?"
docker exec slam-localization bash -lc 'find /tmp/hf02_r3_verify -type f | sort'
echo "DOCKER_FIND_WRAP_EXIT=$?"

echo "== uploaded tree hashes =="
docker exec slam-localization bash -lc 'sha256sum /tmp/hf02_r3_verify/src/human_fall_detection/core/timebase.py /tmp/hf02_r3_verify/src/human_fall_detection/core/sensor_quality.py /tmp/hf02_r3_verify/src/human_fall_detection/tests/test_hf02_timebase.py /tmp/hf02_r3_verify/src/inno_lidar_ros/src/source/publish_manager.cpp /tmp/hf02_r3_verify/src/human_follow_calibration/scripts/calibrate_human_follow.py /tmp/hf02_r3_verify/docs/human_fall/evidence/review_hf02_r2_codex.py'
echo "DOCKER_HASH_WRAP_EXIT=$?"

echo "== unit tests on device =="
docker exec slam-localization bash -lc 'cd /tmp/hf02_r3_verify && python3 -B -W error -m unittest discover -s src/human_fall_detection/tests -v 2>&1; echo DEVICE_UNITTEST_EXIT=$?'
echo "DOCKER_UNITTEST_WRAP_EXIT=$?"

echo "== R2/R4 boundary script (previously failing) on device =="
docker exec slam-localization bash -lc 'cd /tmp/hf02_r3_verify && python3 -B -W error docs/human_fall/evidence/review_hf02_r2_codex.py 2>&1; echo DEVICE_R2_BOUNDARY_EXIT=$?'
echo "DOCKER_R2_BOUNDARY_WRAP_EXIT=$?"

echo "== original Codex Python review script on device =="
docker exec slam-localization bash -lc 'cd /tmp/hf02_r3_verify && python3 -B -W error docs/human_fall/evidence/review_hf02_codex.py 2>&1; echo DEVICE_CODEX_REVIEW_EXIT=$?'
echo "DOCKER_CODEX_REVIEW_WRAP_EXIT=$?"

echo "== actual C++ helper, all ROS variants, on device =="
docker exec slam-localization bash -lc 'cd /tmp/hf02_r3_verify && CXX=g++ python3 -B docs/human_fall/evidence/hf02_r2_driver_boundary_check.py 2>&1; echo DEVICE_DRIVER_BOUNDARY_EXIT=$?'
echo "DOCKER_DRIVER_BOUNDARY_WRAP_EXIT=$?"
docker exec slam-localization bash -lc 'cd /tmp/hf02_r3_verify && CXX=g++ python3 -B docs/human_fall/evidence/review_hf02_driver_codex.py 2>&1; echo DEVICE_DRIVER_CODEX_EXIT=$?'
echo "DOCKER_DRIVER_CODEX_WRAP_EXIT=$?"

echo "== active driver binary after checks (must be unchanged) =="
docker exec slam-localization bash -lc 'sha256sum /root/catkin_ws/devel/lib/inno_lidar_ros/inno_lidar_node'
echo "DOCKER_ACTIVE_AFTER_WRAP_EXIT=$?"
echo "SCRIPT_DONE"
