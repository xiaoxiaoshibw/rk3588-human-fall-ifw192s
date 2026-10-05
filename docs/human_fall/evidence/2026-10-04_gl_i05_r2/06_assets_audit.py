"""Bounded local recording/index and no-cache dependency evidence."""
import datetime
import hashlib
import json
from pathlib import Path
import sys
import argparse
import numpy as np

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
sys.path.insert(0,str(ROOT/'src/human_fall_detection'))
from core import ground as g

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat()
parser=argparse.ArgumentParser()
parser.add_argument('--output-file',default='06_assets_audit.json')
args=parser.parse_args()
metas = []
for path in sorted((ROOT/'captures/remote').glob('*/meta.json')):
    value = json.loads(path.read_text(encoding='utf8'))
    frames = value.get('frames',[])
    times = [x['bag_time_sec'] for x in frames if 'bag_time_sec' in x]
    metas.append(dict(path=str(path.relative_to(ROOT)),sha256=sha(path),
        modified=datetime.datetime.fromtimestamp(path.stat().st_mtime,
            datetime.timezone(datetime.timedelta(hours=8))).isoformat(),
        recording_bag_time_window=[min(times),max(times)] if times else None,
        metadata_keys=sorted(value),synthetic='synth' in path.parent.name,
        recording_config_binding='unknown',extrinsic_from_to='unknown',
        purpose='bounded local index; not physical proof; current target remains 163621'))
diagpath=ROOT/'docs/human_fall/evidence/2026-10-03_gl_i04_r1/12_real_final/diagnostic.json'
diagnostic=json.loads(diagpath.read_text(encoding='utf8'))
source=diagnostic['source_manifest']['source']
frames=diagnostic['source_manifest']['frames']
times=[f['bag_time_sec'] for f in frames]
target_meta=Path(source['meta_path'])
target=json.loads(target_meta.read_text(encoding='utf8'))
points=np.array([[0.,0.,-1.4],[1.,0.,-1.4],[0.,1.,-1.4],[2.,2.,-1.7]])
s=g.resolve_constrained_settings()
def mask(offset):return np.abs(points[:3]@np.array([0.,0.,1.])+offset)<=s['inlier_threshold_m']
same=mask(1.4);similar=mask(1.41);different=mask(1.7)
assert np.array_equal(same,similar) and not np.array_equal(same,different)
result=dict(kind='gli05_recording_and_no_cache_audit',time=now,
    bounded_search='only captures/remote/*/meta.json filenames and metadata; no remote or full-history scan',
    local_metadata=metas,reference_independent_audit='../2026-10-04_gl_i05_r1/opencode_second_review_01/05b_full_tree_diff.json',
    recording_evidence=dict(recording_window_unix_s=[min(times),max(times)],
        extraction_metadata_keys=sorted(target),metadata_sha256=sha(target_meta),
        binary_sha256=source['bin_sha256'],binary_sha_verified_by_baseline=True,
        source_bag_hash_verified=source['source_bag_hash_verified'],
        extraction_time=target.get('created_iso','unknown'),
        configuration_sha_binding='unknown; historical 2026-09-30 log cannot bind 2026-10-02 recording',
        sdk_chain='SDK XYZ -> ROS publisher -> bag2session -> capture_input; local adapter has no X flip',
        measured_source_to_world_rotation='unknown',optical_window_height_is_not_origin=True,
        diagnostic_sha256=sha(diagpath)),
    no_cache=dict(implemented=False,hits=0,misses=0,refine_reuse=False,
        same_sample_inlier_mask_observed=True,different_mask_observed=True,
        mask_sha256=[hashlib.sha256(m.tobytes()).hexdigest() for m in (same,similar,different)],
        necessary_dependencies=['full source bytes','full fit membership/content','sample row mapping/bytes',
            'up','height','resolved settings','refiner implementation SHA','exact mask member bytes'],
        identical_sample_mask_insufficient='full-fit support depends on non-sampled rows and priors/settings/code; no reuse attempted',
        caller_changes='every call recomputes; report mutation does not affect later calls',
        collision_and_full_cache='N/A: no lookup/table/cache exists',
        dtype_materialization='once per call; no persistent result or refinement cache'),
    B01='BLOCKED',B02='BLOCKED',D01='NOT_RUN',D02='NOT_RUN')
baseline=json.loads((OUT/'00_before_baseline.json').read_text(encoding='utf8'))
rel=Path(source['bin_path']).relative_to(ROOT).as_posix()
result['recording_evidence']['binary_sha_verified_by_baseline'] = (
    baseline['files'][rel]['sha256']==source['bin_sha256'])
target_output=OUT/args.output_file
if target_output.parent.resolve()!=OUT:
    raise ValueError('output must be in current root')
with target_output.open('x',encoding='utf8') as f:json.dump(result,f,indent=2,ensure_ascii=False)
print(json.dumps(dict(metadata_records=len(metas),same_mask=True,different_mask=True,
                     recording_config_binding='unknown',B01='BLOCKED',B02='BLOCKED')))
