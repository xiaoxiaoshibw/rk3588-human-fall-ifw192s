#!/bin/bash
# HF-01 deploy: extract the new package archive into the mounted src tree only.
set -u
mkdir -p /home/wel/slam_localization_wuhan/src
tar -xf /tmp/hf01_hfd.tar -C /home/wel/slam_localization_wuhan/src
echo "extract exit=$?"
rm -f /tmp/hf01_hfd.tar
cd /home/wel/slam_localization_wuhan/src || exit 1
echo '--- file list ---'
find human_fall_detection -type f | sort
echo '--- sha256 ---'
sha256sum human_fall_detection/CMakeLists.txt human_fall_detection/package.xml \
  human_fall_detection/config/default.yaml human_fall_detection/scripts/record_session.py \
  human_fall_detection/scripts/sensor_health.py human_fall_detection/tests/test_hf01_health.py
echo "sha256 exit=$?"
echo '--- line endings (file) ---'
file human_fall_detection/scripts/sensor_health.py human_fall_detection/config/default.yaml
echo "file exit=$?"
echo '--- parent tree unchanged check ---'
ls /home/wel/slam_localization_wuhan/src
echo "ls exit=$?"
