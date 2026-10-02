#!/bin/bash
# HF-07 isolated build + synthetic protocol chain verification on ldiar-wel.
# Runs on the host as `wel`; every real action happens inside the
# slam-localization container. The live driver is never rebuilt or restarted.
set -u
R1=/tmp/hf07_verify_r1
WS=/root/catkin_ws/hf07_verify_ws
EV=$R1/docs/human_fall/evidence/2026-10-01_autonomous_hf07_11_r1

echo "DATE=$(date -Is)"
echo "USER=$(id -un) HOST=$(hostname) ARCH=$(uname -m)"
echo "== container =="
docker ps --format '{{.Names}} {{.Image}} {{.Status}}'
echo "DOCKER_PS_EXIT=$?"

echo "== active driver hash BEFORE =="
docker exec slam-localization sha256sum /root/catkin_ws/devel/lib/inno_lidar_ros/inno_lidar_node
echo "DRIVER_BEFORE_EXIT=$?"

echo "== upload + unpack =="
docker cp /tmp/hf07_verify_r1.tar slam-localization:/tmp/hf07_verify_r1.tar
echo "DOCKER_CP_EXIT=$?"
docker exec slam-localization bash -lc "rm -rf $R1 && mkdir -p $R1 && tar -xf /tmp/hf07_verify_r1.tar -C $R1 && find $R1 -maxdepth 3 -type d | sort"
echo "DOCKER_UNPACK_EXIT=$?"

echo "== isolated catkin build devel + install (no top-level build script) =="
docker exec slam-localization bash -lc "
set -e
source /opt/ros/noetic/setup.bash
rm -rf $WS
mkdir -p $WS/src
cp -r $R1/src/human_fall_detection $WS/src/human_fall_detection
cp -r $R1/src/human_follow_calibration $WS/src/human_follow_calibration
cp -r /root/catkin_ws/src/inno_lidar_msg $WS/src/inno_lidar_msg
cd $WS/src && catkin_init_workspace
cd $WS && catkin_make -j4
echo BUILD_EXIT=\$?
catkin_make install -j4
echo INSTALL_BUILD_EXIT=\$?
"
echo "DOCKER_BUILD_WRAP_EXIT=$?"

echo "== SOURCE layout probe (script placed in package root, no manual path) =="
docker exec slam-localization bash -lc "cp $EV/probe_imports.py $R1/src/human_fall_detection/_probe.py && cd $R1/src/human_fall_detection && python3 _probe.py; echo SOURCE_PROBE_EXIT=\$?"
echo "DOCKER_SOURCE_WRAP_EXIT=$?"

echo "== DEVEL layout probe from /tmp (no manual path) =="
docker exec slam-localization bash -lc "
source /opt/ros/noetic/setup.bash
source $WS/devel/setup.bash
cd /tmp
python3 $EV/probe_imports.py
echo DEVEL_PROBE_EXIT=\$?
rosrun human_fall_detection human_fall_node.py --help >/tmp/hf07_node_help.txt 2>&1
echo ROSRUN_HELP_EXIT=\$?
"
echo "DOCKER_DEVEL_WRAP_EXIT=$?"

echo "== INSTALL layout probe from /tmp (no manual path) =="
docker exec slam-localization bash -lc "
source /opt/ros/noetic/setup.bash
source $WS/install/setup.bash
cd /tmp
python3 $EV/probe_imports.py
echo INSTALL_PROBE_EXIT=\$?
"
echo "DOCKER_INSTALL_WRAP_EXIT=$?"

echo "== installed artifacts + source hashes =="
docker exec slam-localization bash -lc "
source /opt/ros/noetic/setup.bash
source $WS/devel/setup.bash
echo '--- devel bin ---'; ls -l $WS/devel/lib/human_fall_detection | head -20
echo '--- install bin ---'; ls -l $WS/install/lib/human_fall_detection 2>/dev/null | head -20
cd $R1 && sha256sum src/human_fall_detection/core/__init__.py src/human_fall_detection/core/node_runtime.py src/human_fall_detection/scripts/human_fall_node.py src/human_fall_detection/setup.py src/human_fall_detection/CMakeLists.txt src/human_fall_detection/config/human_fall.yaml src/human_fall_detection/launch/human_fall.launch src/human_fall_detection/tests/test_hf07_node.py
"
echo "DOCKER_HASH_WRAP_EXIT=$?"

echo "== local unit tests on device (expect 177) =="
docker exec slam-localization bash -lc "cd $R1 && python3 -B -W error -m unittest discover -s src/human_fall_detection/tests -v > /tmp/hf07_unit.log 2>&1; echo UNIT_EXIT=\$?; tail -4 /tmp/hf07_unit.log; grep -E 'FAIL|ERROR' /tmp/hf07_unit.log | head -20"
echo "DOCKER_UNIT_WRAP_EXIT=$?"

echo "== independent HF07 composition review (5 methods) on device =="
docker exec slam-localization bash -lc "cd $R1 && python3 -B -W error docs/human_fall/evidence/review_hf07_codex.py 2>&1; echo REVIEW_HF07_EXIT=\$?"
echo "DOCKER_REVIEW_HF07_WRAP_EXIT=$?"

echo "== independent HF04-06 boundary review (18 methods) on device =="
docker exec slam-localization bash -lc "cd $R1 && python3 -B -W error docs/human_fall/evidence/review_hf04_06_codex.py 2>&1; echo REVIEW_HF04_06_EXIT=\$?"
echo "DOCKER_REVIEW_HF04_06_WRAP_EXIT=$?"

echo "== stop only our own live-preview node/demo (targeted, not the driver) =="
docker exec slam-localization bash -lc "pkill -f 'human_fall_detection/human_fall_nod[e].py' 2>/dev/null; pkill -f 'hf11_live_de[m]o' 2>/dev/null; sleep 1; echo stopped"
echo "DOCKER_STOP_OURS_WRAP_EXIT=$?"

echo "== synthetic protocol-chain integration =="
docker exec slam-localization bash -lc "
source /opt/ros/noetic/setup.bash
source $WS/devel/setup.bash
export ROS_MASTER_URI=http://localhost:11311
rosrun human_fall_detection human_fall_node.py --config $EV/hf07_verify.yaml --perception $WS/src/human_fall_detection/config/perception.yaml >/tmp/hf07_node.log 2>&1 &
NODE=\$!
sleep 3
python3 $EV/hf07_verify_integration.py
INT=\$?
echo INTEGRATION_EXIT=\$INT
kill -INT \$NODE 2>/dev/null
sleep 2
kill -9 \$NODE 2>/dev/null
wait \$NODE 2>/dev/null
echo NODE_EXIT=\$?
echo '--- node log (tail) ---'
tail -25 /tmp/hf07_node.log
"
echo "DOCKER_INTEGRATION_WRAP_EXIT=$?"

echo "== topic check (verify topics only, no cmd_vel) =="
docker exec slam-localization bash -lc "source /opt/ros/noetic/setup.bash; rostopic list | grep -E 'hf07_verify|cmd_vel'"
echo "TOPIC_EXIT=$?"

echo "== active driver hash AFTER =="
docker exec slam-localization sha256sum /root/catkin_ws/devel/lib/inno_lidar_ros/inno_lidar_node
echo "DRIVER_AFTER_EXIT=$?"
echo SCRIPT_DONE
