#!/bin/bash
# HF-01 round 2 retry: early SIGINT delivered to the record process itself.
# The previous attempt ran the recording to completion because a non-interactive
# shell background job inherits SIG_IGN; here a Python driver resets SIGINT to
# SIG_DFL in the child and signals exactly that process. The lidar service is
# never touched. Also checks a real session-conflict refusal on the device.
set -u
inner=/tmp/hf01_session_inner_r2b.sh
cat > "$inner" <<'INNER'
#!/bin/bash
source /opt/ros/noetic/setup.bash
source /root/catkin_ws/devel/setup.bash
mkdir -p /root/catkin_ws/human_fall_sessions
echo "--- health node start (timeout -s INT 30) ---"
timeout -s INT 30 rosrun human_fall_detection sensor_health.py --session-id health_r2_sigint_b \
  > /tmp/hf01_health_r2b.log 2>&1 &
health_pid=$!
echo "health_pid=$health_pid"
echo "--- read one /human_fall/health message (timeout 20) ---"
timeout 20 python3 - <<'PY'
import json
import rospy
from std_msgs.msg import String
rospy.init_node("hf01_r2b_reader", anonymous=True)
msg = rospy.wait_for_message("/human_fall/health", String, timeout=15)
payload = json.loads(msg.data)
print("strict json parse: ok")
print("session_id:", payload["session_id"])
print("observability:", payload["observability"])
cloud = payload["topics"]["cloud"]
print("cloud stamp_status/secs/nsecs/source:", cloud["stamp_status"], cloud["stamp_secs"],
      cloud["stamp_nsecs"], cloud["source_stamp_s"])
imu = payload["topics"]["imu"]
print("imu covariance_zero/not_provided/usable/reason:", imu["orientation_covariance_zero"],
      imu["orientation_not_provided"], imu["orientation_usable"], imu["orientation_reason"])
print("imu measurements_finite:", imu["measurements_finite"])
print("device abnormal_flag:", payload["topics"]["device_status"]["abnormal_flag"])
with open("/tmp/hf01_health_r2b_sample.json", "w") as out:
    out.write(msg.data)
PY
echo "health sample exit=$?"
echo "--- record --duration 30, SIGINT to the record process after 7 s ---"
timeout 120 python3 - <<'PY'
import signal
import subprocess
import time

cmd = [
    "python3", "/root/catkin_ws/src/human_fall_detection/scripts/record_session.py",
    "--duration", "30",
    "--session-id", "hf01_sigint_r2b",
    "--output-dir", "/root/catkin_ws/human_fall_sessions",
    "--config", "/root/catkin_ws/src/human_fall_detection/config/default.yaml",
]


def reset_sigint():
    signal.signal(signal.SIGINT, signal.SIG_DFL)


with open("/tmp/hf01_sigint_r2b.log", "w") as log:
    process = subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT,
                               preexec_fn=reset_sigint)
    time.sleep(7)
    process.send_signal(signal.SIGINT)
    returncode = process.wait()
print("record exit=", returncode)
PY
echo "record driver exit=$?"
cat /tmp/hf01_sigint_r2b.log
echo "--- manifest ---"
cat /root/catkin_ws/human_fall_sessions/hf01_sigint_r2b.manifest.json
echo "--- bag re-read (rosbag info) ---"
timeout 30 rosbag info /root/catkin_ws/human_fall_sessions/hf01_sigint_r2b.bag
echo "rosbag info exit=$?"
echo "--- bag re-read (python API, strict health JSON parse) ---"
timeout 60 python3 - <<'PY'
import json
import rosbag
path = "/root/catkin_ws/human_fall_sessions/hf01_sigint_r2b.bag"
health = 0
with rosbag.Bag(path) as bag:
    info = bag.get_type_and_topic_info()
    for name in sorted(info.topics):
        topic = info.topics[name]
        print("{} {} {} messages".format(name, topic.msg_type, topic.message_count))
    for _, msg, _ in bag.read_messages(topics=["/human_fall/health"]):
        json.loads(msg.data)
        health += 1
print("health messages parsed with strict json.loads:", health)
PY
echo "python reread exit=$?"
echo "--- R1: re-run the same session id must refuse and preserve files ---"
sha256sum /root/catkin_ws/human_fall_sessions/hf01_sigint_r2b.bag \
  /root/catkin_ws/human_fall_sessions/hf01_sigint_r2b.manifest.json > /tmp/hf01_r2b_before.txt
cat /tmp/hf01_r2b_before.txt
timeout 20 python3 /root/catkin_ws/src/human_fall_detection/scripts/record_session.py --duration 1 \
  --session-id hf01_sigint_r2b --output-dir /root/catkin_ws/human_fall_sessions \
  --config /root/catkin_ws/src/human_fall_detection/config/default.yaml
echo "conflict run exit=$?"
sha256sum -c /tmp/hf01_r2b_before.txt
echo "conflict hash check exit=$?"
kill -INT $health_pid 2>/dev/null
wait $health_pid 2>/dev/null
echo "health node wait exit=$?"
echo "--- session dir ---"
ls -l /root/catkin_ws/human_fall_sessions/
INNER
docker cp "$inner" slam-localization:/tmp/hf01_session_inner_r2b.sh
echo "docker cp exit=$?"
timeout 300 docker exec slam-localization bash /tmp/hf01_session_inner_r2b.sh
echo "exec exit=$?"
docker exec slam-localization rm -f /tmp/hf01_session_inner_r2b.sh /tmp/hf01_health_r2b.log \
  /tmp/hf01_health_r2b_sample.json /tmp/hf01_sigint_r2b.log /tmp/hf01_r2b_before.txt
echo "cleanup exit=$?"
rm -f "$inner"
