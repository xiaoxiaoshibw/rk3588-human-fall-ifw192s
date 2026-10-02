import sys, numpy as np
sys.path.insert(0, "src/human_fall_detection")
sys.path.insert(0, "src/human_fall_detection/scripts")
sys.path.insert(0, "src/human_fall_detection/tests")
from test_gl03_candidates_geometry import *
ground = flat_ground()
block = build_ground_derived(ground, [1.0, 0.0, 0.0])
from core.node_runtime import FallNodeCore
settings = {"candidates": {"min_cluster_points":10,"preferred_cluster_points":20},
 "tracking":{"occlusion_timeout_s":1.5,"lost_timeout_s":3.0},
 "fall":{"mode_verified":False,"allow_confirmed":False}}
core = FallNodeCore("s1", settings, ground=ground, calibration=node_calibration(ground, block), expected_frame=FROM_FRAME)
res = core.process(blob(), 1.0, seq=1, stamp_secs=101, stamp_nsecs=0, frame_id=FROM_FRAME, now=1.0)
st = res["state"]
cand = res["snapshot"]["candidates"][0]
print("cand ground_from", cand["bbox_ground_from"])
print("cand center_ground", cand["center_ground_m"])
print("state ground_from", st["bbox_ground_from"])
print("state center_ground", st["center_ground_m"])
print("state gdid", st["ground_derived_id"], "snap gdid", res["snapshot"]["coordinate"]["ground_derived_id"])
print("state pos_src_from", st["position_source_from"])
print("snap cal gdid", res["snapshot"]["calibration"]["ground_derived_id"])
print("core gdid", core._ground_derived_id)
