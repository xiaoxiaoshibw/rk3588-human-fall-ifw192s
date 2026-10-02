#!/bin/bash
set -u
R1=/tmp/hf07_verify_r1
WS=/root/catkin_ws/hf07_verify_ws
echo "== extracted package files =="
docker exec slam-localization bash -lc "ls -la $R1/src/human_fall_detection; echo '--- ws src ---'; ls -la $WS/src; echo '--- ws pkg ---'; ls -la $WS/src/human_fall_detection 2>&1 | head"
echo "== package.xml =="
docker exec slam-localization bash -lc "cat $WS/src/human_fall_detection/package.xml 2>&1 | head -30"
echo "== any CATKIN_IGNORE / COLCON_IGNORE =="
docker exec slam-localization bash -lc "find $WS/src -maxdepth 2 -name 'CATKIN_IGNORE' -o -maxdepth 2 -name 'COLCON_IGNORE' -o -maxdepth 2 -name '.catkin_ignore' 2>/dev/null"
echo "== rospack list (isolated env) =="
docker exec slam-localization bash -lc "source /opt/ros/noetic/setup.bash; source $WS/devel/setup.bash; rospack list | grep -E 'human_fall|human_follow|inno_lidar'"
echo "== unit test failures =="
docker exec slam-localization bash -lc "cd $R1 && python3 -B -W error -m unittest discover -s src/human_fall_detection/tests 2>&1 | grep -E 'FAIL|ERROR|Ran |OK|Error' | head -40"
echo RECON_DONE
