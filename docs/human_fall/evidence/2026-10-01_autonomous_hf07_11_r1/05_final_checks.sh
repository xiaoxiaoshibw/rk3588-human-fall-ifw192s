#!/bin/bash
set -u
echo "== no leftover human_fall_node process =="
docker exec slam-localization bash -lc "ps -ef | grep -E 'human_fall_node|hf07_verify' | grep -v grep || echo NONE"
echo "== no leftover verify topics =="
docker exec slam-localization bash -lc "source /opt/ros/noetic/setup.bash; rostopic list | grep -E 'hf07_verify|hf11_clientpub' || echo NONE"
echo "== active driver hash =="
docker exec slam-localization sha256sum /root/catkin_ws/devel/lib/inno_lidar_ros/inno_lidar_node
echo "== preview served =="
curl -sS -o /dev/null -w "INDEX=%{http_code}\n" http://192.168.3.125:8090/human_fall_preview/index.html
curl -sS -o /dev/null -w "JS=%{http_code}\n" http://192.168.3.125:8090/human_fall_preview/human_fall.js
echo "== active page hash unchanged =="
docker exec slam-localization sha256sum /root/catkin_ws/webui/index.html
echo SCRIPT_DONE
