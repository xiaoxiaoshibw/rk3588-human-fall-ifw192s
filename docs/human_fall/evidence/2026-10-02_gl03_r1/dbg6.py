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
first = core.process(blob(), 1.0, seq=1, stamp_secs=100, stamp_nsecs=0, frame_id=FROM_FRAME, now=1.0)
snap=first["snapshot"]
req={"schema_version":1,"request_id":"r1","action":"select","session_id":"s1","time_epoch":first["state"]["time_epoch"],"snapshot_id":snap["snapshot_id"],"candidate_id":snap["candidates"][0]["candidate_id"],"selection_version":0}
print(core.handle_request(req,1.01).get("accepted"))
res=core.process(blob(), 1.2, seq=2, stamp_secs=100, stamp_nsecs=0, frame_id=FROM_FRAME, now=1.2)
st=res["state"]
print("obs",st["observability"],"reasons",st["reason_codes"],"track",st["track_status"])
print("ground",st["center_ground_m"])
