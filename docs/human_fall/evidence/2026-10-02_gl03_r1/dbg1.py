import sys, numpy as np
sys.path.insert(0, "src/human_fall_detection")
sys.path.insert(0, "src/human_fall_detection/scripts")
sys.path.insert(0, "src/human_fall_detection/tests")
from test_gl03_candidates_geometry import *
transform = reference_transform()
points = blob()
snap = snapshot(points, transform=transform)
c = snap["candidates"][0]
mapped = apply_transform(points, transform)
print("n_candidates", len(snap["candidates"]), "count", c["point_count"], "total", len(points))
print("exp max", mapped.max(axis=0))
print("got max", c["bbox_reference_max_m"])
print("cand points vs mapped (first 3)", )
ev = points[np.asarray(c["evidence_indices"])]
print("evidence count", len(ev))
print("ev max", ev.max(axis=0))
print("bbox_source_max", c["bbox_source_max_m"])
print("ref transform", transform["rotation"])
