import sys, numpy as np, math
sys.path.insert(0, "src/human_fall_detection")
sys.path.insert(0, "src/human_fall_detection/scripts")
sys.path.insert(0, "src/human_fall_detection/tests")
from test_gl03_candidates_geometry import *
tilt=0.35; az=0.6
n = np.array([math.sin(tilt)*math.cos(az), math.sin(tilt)*math.sin(az), math.cos(tilt)])
ground = flat_ground(offset=1.4, normal=n)
block = build_ground_derived(ground, [1.0, 0.0, 0.0])
cal = calibration_with(ground, block)
rng = np.random.RandomState(3)
# L-shape single cluster: arm A along x, arm B along y, asymmetric lengths
a = np.column_stack([np.linspace(-0.5,0.5,200), np.zeros(200), np.full(200,-0.5)])
b = np.column_stack([np.zeros(120), np.linspace(-0.5,0.9,120), np.full(120,-0.5)])
off = np.array([3.0,0.3,0.0])
pts = np.vstack([a,b])+off + rng.normal(0,0.02,((320,3)))
snap = snapshot(pts, ground=ground, calibration=cal, settings={"cluster_cell_m":0.5})
print("n_cand", len(snap["candidates"]))
for c in snap["candidates"]:
    ev = pts[np.asarray(c["evidence_indices"])]
    mm = np.median(apply_ground_derived(ev, block), axis=0)
    sm = apply_ground_derived(np.asarray(c["center_source_m"])[None,:], block)[0]
    print("count",c["point_count"],"diff",mm-sm, "differ", not np.allclose(mm,sm,atol=1e-6))
