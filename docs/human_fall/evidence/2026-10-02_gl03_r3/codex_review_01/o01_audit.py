"""Recompute O01 statistics without running or overwriting submitted script."""
import csv
import hashlib
import json
import sys
import tarfile
from collections import Counter
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[5]
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'src/human_fall_detection'))
from core.lidar_candidates import _connected_clusters, _horizontal_coords, ground_plane_basis

report = json.loads((OUT.parent / '21_o01_planes_ablation_r3.json').read_text())
data = ROOT / 'docs/human_fall/evidence/2026-10-01_gl00_r1'
with tarfile.open(data / '14_current_sample.csv.tgz') as archive:
    points = np.loadtxt(archive.extractfile('14_current_sample.csv'), delimiter=',', skiprows=1)
with (data / '14_current_roi_points.csv').open(encoding='utf-8-sig', newline='') as f:
    roi = Counter(row['frame_seq'] for row in csv.DictReader(f))
planes = json.loads((data / '14_current_planes.json').read_text())['competing_planes']
rows = []
def arm(array, basis):
    clusters = _connected_clusters(_horizontal_coords(array, basis), .25)
    largest = max(clusters, key=len)
    block = array[np.asarray(largest)]
    return dict(component_count=len(clusters), sizes_desc=sorted(map(len,clusters),reverse=True)[:10],
                largest=dict(size=len(largest),aabb_min_m=block.min(axis=0).tolist(),
                             aabb_max_m=block.max(axis=0).tolist()))
for index, plane in enumerate(planes):
    normal = np.asarray(plane['normal']); normal /= np.linalg.norm(normal)
    residual = np.sum(points * normal, axis=1) + plane['offset_m']
    keep = abs(residual) <= .05
    count = int(keep.sum())
    rms = float(np.sqrt(np.sum(residual[keep]**2)/count))
    row = report['ablations'][index]
    assert count == row['current_pool_support_count']
    assert abs(count / len(points) - row['current_pool_support_fraction']) < 1e-12
    assert abs(rms - row['current_pool_support_rms_m']) < 1e-12
    basis = ground_plane_basis(dict(status='valid',normal=plane['normal'],offset_m=plane['offset_m']))
    full, ablated = arm(points,basis), arm(points[~keep],basis)
    assert full == row['all_points'] and ablated == row['non_plane_points']
    assert row['role'] == 'unknown_unverified_hypothesis'
    rows.append(dict(plane=index,count=count,fraction=count/len(points),rms=rms,
                     components=[full['component_count'],ablated['component_count']]))
assert len(points)==97411 and sum(roi.values())==6000 and len(roi)==2
assert report['separation_decision']['enabled'] is False
assert report['corrected_claims']['ground_bridging_excluded'] is False
for section in ['pool','roi_points','planes_source']:
    item = report[section]
    assert hashlib.sha256((ROOT/item['path']).read_bytes()).hexdigest()==item['sha256']
print(json.dumps(dict(result='PASS',rows=rows,roi_frames=dict(roi)),indent=2))
