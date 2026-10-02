#!/bin/bash
set -u
echo "== deploy preview (does not touch active index.html) =="
docker exec slam-localization mkdir -p /root/catkin_ws/webui/human_fall_preview
docker cp /tmp/hf11_idx.html slam-localization:/root/catkin_ws/webui/human_fall_preview/index.html
docker cp /tmp/hf11_hf.js slam-localization:/root/catkin_ws/webui/human_fall_preview/human_fall.js
echo "DEPLOY_CP_EXIT=$?"
echo "== listing =="
docker exec slam-localization ls -la /root/catkin_ws/webui/human_fall_preview
echo "== hashes (preview + active untouched) =="
docker exec slam-localization sha256sum /root/catkin_ws/webui/human_fall_preview/index.html /root/catkin_ws/webui/human_fall_preview/human_fall.js /root/catkin_ws/webui/index.html /root/catkin_ws/webui/index.html.bak4-20260930
echo "== curl preview URL =="
curl -sS -o /tmp/hf11_preview_curl.html -w "PREVIEW_INDEX_HTTP=%{http_code} bytes=%{size_download}\n" http://192.168.3.125:8090/human_fall_preview/index.html
curl -sS -o /tmp/hf11_hf_curl.js -w "PREVIEW_JS_HTTP=%{http_code} bytes=%{size_download}\n" http://192.168.3.125:8090/human_fall_preview/human_fall.js
curl -sS -o /tmp/hf11_three.js -w "PARENT_THREE_HTTP=%{http_code} bytes=%{size_download}\n" http://192.168.3.125:8090/three.min.js
curl -sS -o /tmp/hf11_orbit.js -w "PARENT_ORBIT_HTTP=%{http_code} bytes=%{size_download}\n" http://192.168.3.125:8090/OrbitControls.js
echo "== served preview sanity =="
grep -c "human_fall.js" /tmp/hf11_preview_curl.html
grep -c "../three.min.js" /tmp/hf11_preview_curl.html
grep -c "hfSelectMode" /tmp/hf11_preview_curl.html
grep -c "clientPublish" /tmp/hf11_hf_curl.js
echo "== active page still original title =="
curl -sS http://192.168.3.125:8090/index.html | grep -o "<title>[^<]*</title>" | head -1
echo SCRIPT_DONE
