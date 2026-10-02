#!/usr/bin/env bash
set -e
docker exec -i slam-localization bash -s <<'CONTAINER'
set -e
source /opt/ros/noetic/setup.bash
source /root/catkin_ws/hf07_verify_ws/devel/setup.bash
package=/root/catkin_ws/hf07_verify_ws/src/human_fall_detection
follower=/root/catkin_ws/hf07_verify_ws/src/human_follow_calibration
mkdir -p "$follower/scripts"
CONTAINER
docker cp /tmp/human_fall_node.py slam-localization:/root/catkin_ws/hf07_verify_ws/src/human_fall_detection/scripts/human_fall_node.py
docker cp /tmp/deploy_human_fall.sh slam-localization:/root/catkin_ws/hf07_verify_ws/src/human_fall_detection/scripts/deploy_human_fall.sh
docker cp /tmp/calibrate_human_follow.py slam-localization:/root/catkin_ws/hf07_verify_ws/src/human_follow_calibration/scripts/calibrate_human_follow.py
docker exec -i slam-localization bash -s <<'CONTAINER'
set -e
source /opt/ros/noetic/setup.bash
source /root/catkin_ws/hf07_verify_ws/devel/setup.bash
package=/root/catkin_ws/hf07_verify_ws/src/human_fall_detection
bash -n "$package/scripts/deploy_human_fall.sh"
PYTHONPATH="$package:$package/scripts" python3 -B -W error -m unittest discover -s "$package/tests" > /tmp/codex_final_board_tests.txt 2>&1
tail -n 10 /tmp/codex_final_board_tests.txt
bash "$package/scripts/deploy_human_fall.sh" release
bash "$package/scripts/deploy_human_fall.sh" start
sleep 3
bash "$package/scripts/deploy_human_fall.sh" status
CONTAINER
