#!/bin/bash
source /opt/ros/noetic/setup.bash
source /root/catkin_ws/hf07_verify_ws/devel/setup.bash
D=/root/catkin_ws/hf07_verify_ws/devel/lib/human_fall_detection
echo "== wrapper head =="
sed -n '1,30p' "$D/human_fall_node.py"
echo "== bin contents =="
ls "$D"
echo "== manual import with bin dir on path =="
cd /tmp
python3 - "$D" <<'PY'
import os, sys
d = sys.argv[1]
sys.path.insert(0, d)
print("path0:", sys.path[:3])
import sensor_health
print("sensor_health ok")
try:
    import core.node_runtime
    print("core ok")
except Exception as exc:
    import traceback
    traceback.print_exc()
PY
echo "== roslaunch-less rosrun 4s =="
cd /
timeout 4 rosrun human_fall_detection human_fall_node.py \
  --config /tmp/hf07_verify_r1/docs/human_fall/evidence/2026-10-01_autonomous_hf07_11_r1/hf07_verify.yaml \
  --perception /root/catkin_ws/hf07_verify_ws/src/human_fall_detection/config/perception.yaml 2>&1 | head -30
echo DIAG_DONE
