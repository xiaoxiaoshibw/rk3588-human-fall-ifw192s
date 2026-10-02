#!/bin/bash
echo "=== container host ==="
hostname
echo "=== /root/catkin_ws ==="
ls -la /root/catkin_ws
echo "=== src ==="
ls /root/catkin_ws/src
echo "=== webui ==="
ls -la /root/catkin_ws/webui
echo "=== containers/ros ==="
ls /opt/ros
python3 --version
python3 -c "import numpy; print('numpy', numpy.__version__)"
echo "=== processes ==="
ps -ef | grep -E "ros|http|bridge|8090|8765" | grep -v grep
echo "=== listeners ==="
(ss -ltnp 2>/dev/null || netstat -ltnp 2>/dev/null) | grep -E "8090|8765"
echo "=== env ==="
env | grep -E "ROS|CATKIN" | sort
