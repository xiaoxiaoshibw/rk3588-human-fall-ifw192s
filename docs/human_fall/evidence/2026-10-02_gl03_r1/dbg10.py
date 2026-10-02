import sys, numpy as np
sys.path.insert(0, "src/human_fall_detection")
sys.path.insert(0, "src/human_fall_detection/scripts")
sys.path.insert(0, "src/human_fall_detection/tests")
from test_gl03_candidates_geometry import *
ground = flat_ground(); block = trusted_block(ground)
from core.node_runtime import FallNodeCore
settings = {"candidates":{"min_cluster_points":10,"preferred_cluster_points":20},
 "tracking":{"occlusion_timeout_s":1.5,"lost_timeout_s":3.0},
 "fall":{"mode_verified":False,"allow_confirmed":False}}
core = FallNodeCore("s1", settings, ground=ground, calibration=node_calibration(ground, block), expected_frame=FROM_FRAME)
def frame(pts, recv, seq): return core.process(pts, recv, seq=seq, stamp_secs=100, stamp_nsecs=int(2e8*seq), frame_id=FROM_FRAME, now=recv)
f=frame(target_frame(),1.0,1)
print("obs",f["state"]["observability"])
req={"schema_version":1,"request_id":"r1","action":"select","session_id":"s1","time_epoch":f["state"]["time_epoch"],"snapshot_id":f["snapshot"]["snapshot_id"],"candidate_id":pick_target(f["snapshot"])["candidate_id"],"selection_version":0}
print("ack",core.handle_request(req,1.01).get("accepted"))
for i,recv in enumerate((1.4,2.8,4.6),start=2):
    r=frame(ground_plane(),recv,i)
    print(recv, r["state"]["track_status"], r["state"]["track_id"], "obs",r["state"]["observability"], "pred",r["state"]["position_predicted"])
