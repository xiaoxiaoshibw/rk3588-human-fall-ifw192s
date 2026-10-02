#!/bin/bash
# Start the isolated verify node + a SYNTHETIC input so the preview URL shows a
# real request->ROS->ack link. Production topics/page/driver are untouched.
set -u
WS=/root/catkin_ws/hf07_verify_ws
EV=/tmp/hf07_verify_r1/docs/human_fall/evidence/2026-10-01_autonomous_hf07_11_r1

echo "== deploy preview =="
docker exec slam-localization mkdir -p /root/catkin_ws/webui/human_fall_preview
docker cp /tmp/hf11_idx.html slam-localization:/root/catkin_ws/webui/human_fall_preview/index.html
docker cp /tmp/hf11_hf.js slam-localization:/root/catkin_ws/webui/human_fall_preview/human_fall.js
docker cp /tmp/hf11_hf_lib.js slam-localization:/root/catkin_ws/webui/human_fall_preview/human_fall_lib.js
docker cp /tmp/hf11_live_demo.py slam-localization:/tmp/hf11_live_demo.py

echo "== stop previous demo/node =="
docker exec slam-localization bash -lc "pkill -f 'human_fall_detection/human_fall_nod[e].py'; pkill -f 'hf11_live_de[m]o'; sleep 1; echo stopped"
sleep 1

echo "== start verify node (detached) =="
docker exec -d slam-localization bash -lc "source /opt/ros/noetic/setup.bash; source $WS/devel/setup.bash; export ROS_MASTER_URI=http://localhost:11311; exec rosrun human_fall_detection human_fall_node.py --config $EV/hf07_verify.yaml --perception $WS/src/human_fall_detection/config/perception.yaml > /tmp/hf11_node.log 2>&1"
sleep 2

echo "== start SYNTHETIC demo input (detached) =="
docker exec -d slam-localization bash -lc "source /opt/ros/noetic/setup.bash; source $WS/devel/setup.bash; export ROS_MASTER_URI=http://localhost:11311; exec python3 /tmp/hf11_live_demo.py > /tmp/hf11_demo.log 2>&1"
sleep 4

echo "== processes =="
docker exec slam-localization bash -lc "ps -ef | grep -E 'human_fall_node|hf11_live_demo' | grep -v grep"
echo "== topics =="
docker exec slam-localization bash -lc "source /opt/ros/noetic/setup.bash; rostopic list | grep -E 'hf07_verify'"
echo "== node log =="
docker exec slam-localization bash -lc "tail -5 /tmp/hf11_node.log"
echo "== demo log =="
docker exec slam-localization bash -lc "tail -3 /tmp/hf11_demo.log"
echo SCRIPT_DONE
