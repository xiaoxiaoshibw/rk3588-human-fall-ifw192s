#!/bin/bash
# HF-04..06 round-2 device evidence. Read-only on the live stack: only isolated
# /tmp work areas are written. No ROS build, no driver restart, no network change.
set -u
echo "DATE=$(date -Is)"
echo "USER=$(id -un) HOST=$(hostname) ARCH=$(uname -m)"
echo "== docker ps =="
docker ps --format '{{.Names}}'
echo "DOCKER_PS_EXIT=$?"
echo "== container python/numpy =="
docker exec slam-localization bash -lc 'python3 --version; python3 -c "import numpy; print(\"numpy\", numpy.__version__)"'
echo "DOCKER_ENV_WRAP_EXIT=$?"

echo "== unpack uploaded isolated tree =="
docker cp /tmp/hf04_06_r2_verify.tar slam-localization:/tmp/hf04_06_r2_verify.tar
echo "DOCKER_CP_EXIT=$?"
docker exec slam-localization bash -lc 'rm -rf /tmp/hf04_06_r2_verify && mkdir -p /tmp/hf04_06_r2_verify && tar -xf /tmp/hf04_06_r2_verify.tar -C /tmp/hf04_06_r2_verify && echo INNER_UNPACK_EXIT=$?'
echo "DOCKER_UNPACK_WRAP_EXIT=$?"

echo "== unit tests on device =="
docker exec slam-localization bash -lc 'cd /tmp/hf04_06_r2_verify && python3 -B -W error -m unittest discover -s src/human_fall_detection/tests -v 2>&1; echo DEVICE_UNITTEST_EXIT=$?'
echo "DOCKER_UNITTEST_WRAP_EXIT=$?"

echo "== independent review_hf04_06_codex.py (14 methods) on device =="
docker exec slam-localization bash -lc 'cd /tmp/hf04_06_r2_verify && python3 -B -W error docs/human_fall/evidence/review_hf04_06_codex.py 2>&1; echo DEVICE_REVIEW_EXIT=$?'
echo "DOCKER_REVIEW_WRAP_EXIT=$?"

echo "== uploaded tree hashes =="
docker exec slam-localization bash -lc 'cd /tmp/hf04_06_r2_verify && sha256sum src/human_fall_detection/core/lidar_candidates.py src/human_fall_detection/core/association.py src/human_fall_detection/core/tracking.py src/human_fall_detection/core/selection.py src/human_fall_detection/core/baseline.py src/human_fall_detection/core/features.py src/human_fall_detection/core/fall_state.py src/human_fall_detection/core/pipeline.py src/human_fall_detection/scripts/fall_replay.py src/human_fall_detection/config/perception.yaml src/human_fall_detection/tests/test_hf04_candidates.py src/human_fall_detection/tests/test_hf05_tracking.py src/human_fall_detection/tests/test_hf06_fall_state.py docs/human_fall/evidence/review_hf04_06_codex.py'
echo "DOCKER_HASH_WRAP_EXIT=$?"

echo "== active driver binary unchanged =="
docker exec slam-localization bash -lc 'sha256sum /root/catkin_ws/devel/lib/inno_lidar_ros/inno_lidar_node'
echo "DOCKER_DRIVER_WRAP_EXIT=$?"
echo "SCRIPT_DONE"
