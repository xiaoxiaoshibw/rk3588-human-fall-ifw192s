@echo off
rem 打开雷达 WebUI；服务没起就先在板上拉起
curl -s -o NUL --max-time 2 http://192.168.3.125:8090 || ssh wel@192.168.3.125 "docker exec -d slam-localization python3 -m http.server 8090 --directory /root/catkin_ws/webui"
start "" http://192.168.3.125:8090
