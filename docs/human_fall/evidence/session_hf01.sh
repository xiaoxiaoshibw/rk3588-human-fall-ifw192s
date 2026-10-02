#!/bin/bash
# HF-01: live health node sample + 8 s short bag record + re-read verification.
set -u
inner=/tmp/hf01_session_inner.sh
cat > "$inner" <<'INNER'
#!/bin/bash
source /opt/ros/noetic/setup.bash
source /root/catkin_ws/devel/setup.bash
mkdir -p /root/catkin_ws/human_fall_sessions
echo "--- health node start (timeout -s INT 25, logs to /tmp/hf01_health.log) ---"
timeout -s INT 25 rosrun human_fall_detection sensor_health.py --config /root/catkin_ws/src/human_fall_detection/config/default.yaml > /tmp/hf01_health.log 2>&1 &
health_pid=$!
echo "health_pid=$health_pid"
echo "--- read one /human_fall/health message and validate strict JSON (timeout 20) ---"
timeout 20 python3 - <<'PY'
import json
import rospy
from std_msgs.msg import String
rospy.init_node("hf01_verify_reader", anonymous=True)
msg = rospy.wait_for_message("/human_fall/health", String, timeout=15)
payload = json.loads(msg.data)
print("strict json parse: ok")
print("observability:", payload["observability"])
print("time_epoch:", payload["time_epoch"])
print("cloud status:", payload["topics"]["cloud"]["status"])
print("cloud layout valid:", payload["topics"]["cloud"]["layout"]["valid"])
print("cloud points:", payload["topics"]["cloud"]["points"])
print("cloud header==first_point_ts:", payload["topics"]["cloud"]["header_equals_first_point_stamp"])
print("imu status:", payload["topics"]["imu"]["status"])
print("imu measurements_finite:", payload["topics"]["imu"]["measurements_finite"])
print("imu orientation_reason:", payload["topics"]["imu"]["orientation_reason"])
print("imu units_verified/alignment_verified:", payload["topics"]["imu"]["units_verified"], payload["topics"]["imu"]["alignment_verified"])
print("device abnormal_flag:", payload["topics"]["device_status"]["abnormal_flag"])
print("reason_codes:", payload["reason_codes"])
with open("/tmp/hf01_health_sample.json", "w") as out:
    out.write(msg.data)
PY
echo "health sample exit=$?"
echo "--- health node log ---"
cat /tmp/hf01_health.log
echo "--- record short bag (8 s) ---"
timeout 60 rosrun human_fall_detection record_session.py --duration 8 --session-id hf01_verify \
  --output-dir /root/catkin_ws/human_fall_sessions \
  --config /root/catkin_ws/src/human_fall_detection/config/default.yaml
echo "record exit=$?"
wait $health_pid 2>/dev/null
echo "health node wait exit=$?"
echo "--- bag re-read (rosbag info CLI) ---"
timeout 30 rosbag info /root/catkin_ws/human_fall_sessions/hf01_verify.bag
echo "rosbag info exit=$?"
echo "--- manifest ---"
cat /root/catkin_ws/human_fall_sessions/hf01_verify.manifest.json
echo "--- session files ---"
ls -l /root/catkin_ws/human_fall_sessions/
INNER
docker cp "$inner" slam-localization:/tmp/hf01_session_inner.sh
echo "docker cp exit=$?"
timeout 240 docker exec slam-localization bash /tmp/hf01_session_inner.sh
echo "exec exit=$?"
docker exec slam-localization rm -f /tmp/hf01_session_inner.sh /tmp/hf01_health.log /tmp/hf01_health_sample.json
echo "cleanup exit=$?"
rm -f "$inner"
