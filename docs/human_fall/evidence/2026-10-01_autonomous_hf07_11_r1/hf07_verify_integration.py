#!/usr/bin/env python3
"""HF-07 board integration harness (synthetic PointCloud2, not a real human).

Publishes an explicitly synthetic point cloud on the isolated /hf07_verify
namespace, drives the operator selection/baseline/fall protocol against the
running human_fall_node, and reports every observed payload. The geometry is
synthetic and is never presented as real human-fall acceptance.
"""

import json
import os
import sys
import threading
import time

import numpy as np
import rospy
from sensor_msgs.msg import PointCloud2, PointField
from std_msgs.msg import String

PREFIX = "/hf07_verify"
REPORT_PATH = ("/tmp/hf07_verify_r1/docs/human_fall/evidence/"
               "2026-10-01_autonomous_hf07_11_r1/hf07_verify_report.json")

report = {"steps": [], "captured": {}, "ok": False}


def log(name, ok, detail=None):
    report["steps"].append({"name": name, "ok": bool(ok), "detail": detail})
    print("[{}] {} {}".format("PASS" if ok else "FAIL", name, detail if detail else ""))


def make_cloud(points, secs, nsecs):
    msg = PointCloud2()
    msg.header.stamp = rospy.Time(int(secs), int(nsecs))
    msg.header.frame_id = "innolidar"
    msg.height = 1
    msg.width = len(points)
    msg.is_bigendian = False
    msg.point_step = 16
    msg.row_step = 16 * len(points)
    msg.is_dense = True
    msg.fields = [PointField("x", 0, 7, 1), PointField("y", 4, 7, 1),
                  PointField("z", 8, 7, 1), PointField("intensity", 12, 7, 1)]
    buffer = np.zeros((len(points), 4), dtype="<f4")
    buffer[:, :3] = points
    buffer[:, 3] = 1.0
    msg.data = buffer.tobytes()
    return msg


def standing(top=0.1):
    z = np.linspace(-1.4, top, 80)
    return np.column_stack((np.full(80, 3.0), np.zeros(80), z))


def lying():
    x = np.linspace(2.3, 3.7, 80)
    z = np.full(80, -1.35)
    return np.column_stack((x, np.zeros(80), z))


class Harness:
    def __init__(self):
        self.lock = threading.Lock()
        self.candidates = None
        self.state = None
        self.acks = []
        self.events = []
        self.states_seen = []
        self.t = 1000.0

    def start(self):
        self.pub = rospy.Publisher(PREFIX + "/points", PointCloud2, queue_size=1)
        self.req = rospy.Publisher(PREFIX + "/selection_request", String, queue_size=10)
        rospy.Subscriber(PREFIX + "/candidates", String, self._on_candidates)
        rospy.Subscriber(PREFIX + "/state", String, self._on_state)
        rospy.Subscriber(PREFIX + "/selection_ack", String, self._on_ack)
        rospy.Subscriber(PREFIX + "/event", String, self._on_event)

    def _on_candidates(self, msg):
        with self.lock:
            try:
                self.candidates = json.loads(msg.data)
            except ValueError:
                self.candidates = None

    def _on_state(self, msg):
        with self.lock:
            try:
                self.state = json.loads(msg.data)
                self.states_seen.append(self.state.get("fall_status"))
            except ValueError:
                self.state = None

    def _on_ack(self, msg):
        with self.lock:
            try:
                self.acks.append(json.loads(msg.data))
            except ValueError:
                pass

    def _on_event(self, msg):
        with self.lock:
            try:
                self.events.append(json.loads(msg.data))
            except ValueError:
                pass

    def publish(self, points, count=1, dt=0.1, oob_stamp=None):
        for _ in range(count):
            if oob_stamp is not None:
                secs, nsecs = oob_stamp
            else:
                secs = int(self.t)
                nsecs = int(round((self.t - secs) * 1e9))
            self.pub.publish(make_cloud(points, secs, nsecs))
            self.t += dt
            rospy.sleep(dt)

    def send(self, request):
        self.req.publish(String(data=json.dumps(request)))
        return request.get("request_id")

    def wait(self, predicate, timeout=15.0, interval=0.1):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            with self.lock:
                value = predicate()
            if value:
                return value
            rospy.sleep(interval)
        return None

    def find_ack(self, request_id):
        for ack in self.acks:
            if ack.get("request_id") == request_id:
                return ack
        return None


def main():
    rospy.init_node("hf07_verify_harness", disable_signals=True)
    harness = Harness()
    harness.start()
    rospy.sleep(1.0)

    harness.publish(standing(), count=10, dt=0.1)
    candidates = harness.wait(lambda: harness.candidates, timeout=15.0)
    if not candidates or not candidates.get("candidates"):
        log("candidate_snapshot", False, "no candidates")
        return 2
    log("candidate_snapshot", True,
        {"count": len(candidates["candidates"]),
         "snapshot_id": candidates["snapshot_id"],
         "source": candidates["source"]})
    candidate = candidates["candidates"][0]
    report["captured"]["candidate"] = {
        "candidate_id": candidate["candidate_id"],
        "point_count": candidate["point_count"],
        "center_source_m": candidate["center_source_m"],
        "range_m": candidate["range_m"],
        "height_m": candidate["height_m"],
    }

    request = {"schema_version": 1, "request_id": "hf07-select-1", "action": "select",
               "session_id": candidates["session_id"],
               "time_epoch": candidates["time_epoch"],
               "snapshot_id": candidates["snapshot_id"],
               "candidate_id": candidate["candidate_id"], "selection_version": 0}
    harness.send(request)
    ack = harness.wait(lambda: harness.find_ack("hf07-select-1") or None, timeout=10.0)
    log("selection_ack", bool(ack and ack.get("accepted")), ack)
    if not ack or not ack.get("accepted"):
        return 3
    track_id = ack["track_id"]
    selection_version = ack["selection_version"]
    report["captured"]["selection_ack"] = ack

    harness.publish(standing(), count=8, dt=0.1)
    locked = harness.wait(lambda: (harness.state or {}).get("track_status") == "locked",
                          timeout=10.0)
    log("track_locked", bool(locked), (harness.state or {}).get("track_status"))
    if not locked:
        return 4

    capture = {"schema_version": 1, "request_id": "hf07-baseline-1",
               "action": "capture_baseline", "session_id": candidates["session_id"],
               "time_epoch": candidates["time_epoch"], "track_id": track_id,
               "selection_version": selection_version, "operator_confirmed": True}
    harness.send(capture)
    pending = harness.wait(lambda: harness.find_ack("hf07-baseline-1") or None, timeout=10.0)
    log("baseline_pending_ack", bool(pending and pending.get("accepted")), pending)
    if not pending:
        return 5

    deadline = time.monotonic() + 8.0
    ready = None
    while time.monotonic() < deadline:
        harness.publish(standing(), count=5, dt=0.1)
        with harness.lock:
            for item in harness.acks:
                if (item.get("action") == "capture_baseline"
                        and item.get("baseline", {}).get("status") in ("ready", "failed")):
                    ready = item
        if ready:
            break
    log("baseline_completion", bool(ready and ready["baseline"]["status"] == "ready"), ready)
    report["captured"]["baseline_ack"] = ready

    for top, count in ((0.1, 4), (-0.3, 4), (-0.7, 4), (-1.1, 4)):
        harness.publish(standing(top), count=count, dt=0.1)
    harness.publish(lying(), count=20, dt=0.1)
    with harness.lock:
        final_state = dict(harness.state or {})
        seen = list(harness.states_seen)
    confirmed_seen = any(item == "confirmed" for item in seen)
    fall_ok = final_state.get("fall_status") in ("descending",
                                                 "low_posture_unclassified",
                                                 "suspected", "unknown")
    log("fall_state_synthetic", fall_ok and not confirmed_seen,
        {"final": final_state.get("fall_status"),
         "seen": sorted({item for item in seen if item is not None}),
         "confirmed_seen": confirmed_seen})
    report["captured"]["fall_final"] = {
        "fall_status": final_state.get("fall_status"),
        "track_status": final_state.get("track_status"),
        "observability": final_state.get("observability"),
        "mode_verified": final_state.get("mode_verified"),
        "confirmed_enabled": final_state.get("confirmed_enabled"),
        "position_source_m": final_state.get("position_source_m"),
        "bbox_source_min_m": final_state.get("bbox_source_min_m"),
        "bbox_source_max_m": final_state.get("bbox_source_max_m"),
        "range_m": final_state.get("range_m"),
        "recent_events": len(final_state.get("recent_events") or []),
        "event_persistence": final_state.get("event_persistence"),
    }

    epoch_before = (harness.state or {}).get("time_epoch")
    harness.publish(standing(), count=1, dt=0.1, oob_stamp=(1, 0))
    harness.publish(standing(), count=3, dt=0.1)
    bumped = harness.wait(
        lambda: (harness.state or {}).get("time_epoch") not in (None, epoch_before),
        timeout=10.0)
    log("illegal_stamp_epoch_bump", bool(bumped),
        {"before": epoch_before, "after": (harness.state or {}).get("time_epoch"),
         "requires_reselection": (harness.state or {}).get("requires_reselection")})

    log("no_events_replayed_as_new", len(harness.events) == 0,
        {"event_count": len(harness.events)})

    report["ok"] = all(step["ok"] for step in report["steps"])
    os.makedirs(os.path.dirname(REPORT_PATH), exist_ok=True)
    with open(REPORT_PATH, "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, allow_nan=False)
    print("REPORT_OK=" + str(report["ok"]))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
