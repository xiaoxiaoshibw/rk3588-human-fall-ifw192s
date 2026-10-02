#!/bin/bash
set -u
echo "== one /hf07_verify/state sample (standalone ground -> non-empty calibration id) =="
docker exec slam-localization bash -lc "source /opt/ros/noetic/setup.bash; timeout 5 rostopic echo -n1 /hf07_verify/state" | grep -E "calibration_id|ground_status|kind|fall_status|track_status|position_source_m|selection_version|clock_domain" | head -20
echo "== served preview index markers (single cloud source selection) =="
curl -sS "http://192.168.3.125:8090/human_fall_preview/index.html" | grep -E "HF_POINTS_TOPIC|const TOPICS" | head -4
echo SCRIPT_DONE
