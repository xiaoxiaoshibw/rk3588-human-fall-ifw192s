"""ROS read-only join by exact source and wire headers; ignore capture edges."""
import json
import time
import rospy
from sensor_msgs.msg import PointCloud2
from std_msgs.msg import String

original = {}
display = {}
states = []
def key(msg):
    return (msg.header.seq, msg.header.stamp.secs, msg.header.stamp.nsecs)
def cloud(msg):
    original[key(msg)] = (msg.width * msg.height, msg.point_step, msg.is_dense,
                          [(f.name, f.offset, f.datatype, f.count) for f in msg.fields])
def shown(msg):
    display[key(msg)] = (msg.width * msg.height, msg.point_step, msg.is_dense,
                        [(f.name, f.offset, f.datatype, f.count) for f in msg.fields])
def state(msg):
    record = json.loads(msg.data)
    if record.get("visualization"):
        states.append(record)
rospy.init_node("codex_wire_mapping_probe", anonymous=True)
rospy.Subscriber("/innolidar_points", PointCloud2, cloud, queue_size=16, buff_size=2**24)
rospy.Subscriber("/human_fall/display_points", PointCloud2, shown, queue_size=16, buff_size=2**24)
rospy.Subscriber("/human_fall/state", String, state, queue_size=16)
time.sleep(8)
rospy.signal_shutdown("captured bounded metadata")
matched = 0
edge = 0
errors = []
for record in states:
    viz = record["visualization"]
    src = viz["source"]
    source_key = (src["seq"], src["stamp_secs"], src["stamp_nsecs"])
    wire_key = (viz["wire_seq"], src["stamp_secs"], src["stamp_nsecs"])
    if source_key not in original or wire_key not in display:
        edge += 1
        continue
    full, thin = original[source_key], display[wire_key]
    actual_source = record["source"]
    assert source_key == (actual_source["seq"], actual_source["stamp_secs"], actual_source["stamp_nsecs"])
    if (full[0] != viz["original_points"] or thin[0] != viz["display_points"]
            or full[1:] != thin[1:] or viz["source_topic"] != "/innolidar_points"
            or viz["topic"] != "/human_fall/display_points"):
        errors.append({"source": source_key, "wire": wire_key})
    matched += 1
print(json.dumps({"state_records": len(states), "joined_frames": matched,
                  "capture_edge_unjoined": edge, "mapping_or_layout_errors": errors}, indent=2))
assert matched >= 20 and not errors
