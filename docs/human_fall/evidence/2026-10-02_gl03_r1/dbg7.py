import sys, numpy as np
sys.path.insert(0, "src/human_fall_detection")
sys.path.insert(0, "src/human_fall_detection/scripts")
sys.path.insert(0, "src/human_fall_detection/tests")
from test_gl03_candidates_geometry import *
ground = flat_ground(); block = build_ground_derived(ground, [1.0,0.0,0.0])
from core.node_runtime import FallNodeCore
settings = {"candidates":{"min_cluster_points":10,"preferred_cluster_points":20},
 "tracking":{"occlusion_timeout_s":1.5,"lost_timeout_s":3.0},
 "fall":{"mode_verified":False,"allow_confirmed":False}}
core = FallNodeCore("s1", settings, ground=ground, calibration=node_calibration(ground, block), expected_frame=FROM_FRAME)
def frame(pts, recv, seq):
    return core.process(pts, recv, seq=seq, stamp_secs=100+seq, stamp_nsecs=0, frame_id=FROM_FRAME, now=recv)
first=frame(blob(),1.0,1)
req={"schema_version":1,"request_id":"r1","action":"select","session_id":"s1","time_epoch":first["state"]["time_epoch"],"snapshot_id":first["snapshot"]["snapshot_id"],"candidate_id":first["snapshot"]["candidates"][0]["candidate_id"],"selection_version":0}
print("ack",core.handle_request(req,1.01).get("accepted"))
res=frame(blob(),1.2,2)
st=res["state"]
print("obs",st["observability"],"reasons",st["reason_codes"],"track",st["track_status"])
print("ground",st["center_ground_m"])
