#!/bin/bash
set -u
echo "== live processes =="
docker exec slam-localization bash -lc "ps -ef | grep -E 'human_fall_node|hf11_live_demo' | grep -v grep"
echo "== preview files hashes =="
docker exec slam-localization sha256sum /root/catkin_ws/webui/human_fall_preview/index.html /root/catkin_ws/webui/human_fall_preview/human_fall.js /root/catkin_ws/webui/human_fall_preview/human_fall_lib.js /root/catkin_ws/webui/index.html
echo "== preview curl =="
curl -sS -o /tmp/p_idx -w "INDEX=%{http_code} %{size_download}B\n" "http://192.168.3.125:8090/human_fall_preview/index.html"
curl -sS -o /tmp/p_js -w "JS=%{http_code} %{size_download}B\n" "http://192.168.3.125:8090/human_fall_preview/human_fall.js"
curl -sS -o /tmp/p_lib -w "LIB=%{http_code} %{size_download}B\n" "http://192.168.3.125:8090/human_fall_preview/human_fall_lib.js"
echo "== served index references lib =="
grep -c "human_fall_lib.js" /tmp/p_idx
echo "== state/candidates publishing (2s) =="
docker exec slam-localization bash -lc "source /opt/ros/noetic/setup.bash; timeout 2 rostopic hz /hf07_verify/candidates" 2>&1 | tail -2
docker exec slam-localization bash -lc "source /opt/ros/noetic/setup.bash; timeout 2 rostopic hz /hf07_verify/state" 2>&1 | tail -2
echo "== preview URL =="
echo "http://192.168.3.125:8090/human_fall_preview/index.html?prefix=/hf07_verify/&points=/hf07_verify/points"
echo "== stop command (documented) =="
echo "docker exec slam-localization pkill -f 'human_fall_detection/human_fall_nod[e].py'; docker exec slam-localization pkill -f 'hf11_live_de[m]o'"
echo SCRIPT_DONE
