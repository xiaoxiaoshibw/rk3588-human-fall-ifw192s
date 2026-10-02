#!/usr/bin/env python3
"""Real ROS subscription probe: display wire header vs state visualization mapping."""
import json
import rospy
from sensor_msgs.msg import PointCloud2
from std_msgs.msg import String

display = []
states = []
source = []


def on_display(m):
    display.append({"seq": m.header.seq, "secs": m.header.stamp.secs,
                    "nsecs": m.header.stamp.nsecs, "width": m.width,
                    "height": m.height, "point_step": m.point_step,
                    "fields": [f.name for f in m.fields]})


def on_state(m):
    try:
        st = json.loads(m.data)
    except (TypeError, ValueError):
        return
    if isinstance(st, dict) and st.get("visualization"):
        states.append(st)


def on_source(m):
    if len(source) < 2:
        source.append({"width": m.width, "height": m.height,
                       "point_step": m.point_step,
                       "fields": [f.name for f in m.fields]})


rospy.init_node("hf09_display_probe", anonymous=True)
rospy.Subscriber("/human_fall/display_points", PointCloud2, on_display, queue_size=5)
rospy.Subscriber("/human_fall/state", String, on_state, queue_size=10)
rospy.Subscriber("/innolidar_points", PointCloud2, on_source, queue_size=2)
rospy.sleep(7.0)

matched = 0
mismatch = 0
for d in display:
    hit = None
    for st in states:
        v = st.get("visualization") or {}
        src = v.get("source") or {}
        if v.get("wire_seq") == d["seq"] and src.get("stamp_secs") == d["secs"] \
                and src.get("stamp_nsecs") == d["nsecs"]:
            hit = v
            break
    if hit:
        matched += 1
    else:
        mismatch += 1

last_viz = states[-1]["visualization"] if states else {}
print("display_frames", len(display), "state_with_viz", len(states))
print("matched_wire_mapping", matched, "unmatched", mismatch)
print("sample_display", display[0] if display else None)
print("sample_viz", last_viz)
print("source_sample", source[0] if source else None)
if display and source:
    same_fields = display[-1]["fields"] == source[0]["fields"]
    same_step = display[-1]["point_step"] == source[0]["point_step"]
    print("fields_preserved", same_fields, "point_step_preserved", same_step)
    print("original_points_equals_source_width",
          last_viz.get("original_points") == source[0]["width"])
    print("display_width_equals_display_points",
          display[-1]["width"] == last_viz.get("display_points"))
    print("topic_ok", last_viz.get("topic") == "/human_fall/display_points",
          "source_topic_ok", last_viz.get("source_topic") == "/innolidar_points")
print("PROBE_DONE")
