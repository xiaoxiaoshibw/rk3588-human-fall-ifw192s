import sys, numpy as np
sys.path.insert(0, "src/human_fall_detection")
sys.path.insert(0, "src/human_fall_detection/scripts")
sys.path.insert(0, "src/human_fall_detection/tests")
from test_gl03_candidates_geometry import *
ground = flat_ground()
block = build_ground_derived(ground, [1.0, 0.0, 0.0])
cal = calibration_with(ground, block)
rng = np.random.RandomState(21)
dense = rng.normal((3.0, 0.0, -0.6), (0.05,0.05,0.05), (280,3))
outliers = rng.normal((3.0, 2.2, -0.6), (0.05,0.3,0.05), (40,3))
points = np.vstack((dense, outliers))
snap = snapshot(points, ground=ground, calibration=cal)
c = snap["candidates"][0]
print("n_cand", len(snap["candidates"]), c["point_count"])
ev = points[np.asarray(c["evidence_indices"])]
mm = np.median(apply_ground_derived(ev, block), axis=0)
sm = apply_ground_derived(np.asarray(c["center_source_m"])[None,:], block)[0]
print("mapped_median", mm)
print("source_median_mapped", sm)
print("diff", mm-sm)
print("center_ground", c["center_ground_m"])
