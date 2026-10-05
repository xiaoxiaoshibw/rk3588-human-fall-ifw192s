"""Codex independent GL-P01 checks; pure/local software, no ROS/board."""
import copy
import hashlib
import importlib.machinery
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).parent
PACKAGE = ROOT / 'src/human_fall_detection'
sys.path[:0] = [str(PACKAGE), str(PACKAGE/'scripts'), str(PACKAGE/'tests')]
from core.calibration import build_ground_derived, validate_geometry_calibration
from core.lidar_candidates import build_snapshot
from core.node_runtime import FallNodeCore, dumps_strict, project_snapshot_for_ros
from test_gl03_candidates_geometry import blob, calibration_with, snapshot, tilted_ground

JS = "const HF=require('./webui/human_fall_preview/human_fall_lib.js');let s='';process.stdin.on('data',c=>s+=c);process.stdin.on('end',()=>console.log(JSON.stringify(HF.parseGroundRender(JSON.parse(s)))));"
def consumer(value):
    run = subprocess.run(['node','-e',JS], input=dumps_strict(project_snapshot_for_ros(value)),
                         cwd=ROOT, text=True, capture_output=True, check=True)
    return json.loads(run.stdout)

ground = tilted_ground(offset=1.6, normal=(0.25, -0.15, 0.9565563234854496))
derived = build_ground_derived(ground, [1.0, 0.0, 0.0])
artifact = calibration_with(ground, derived)
points = blob(center=(3.0, .5, -.6), count=240)
records = []
def check(name, ids, action):
    try:
        action()
        records.append({'name':name,'ids':ids,'result':'PASS'})
    except Exception as error:
        records.append({'name':name,'ids':ids,'result':'FAIL','actual':str(error)})
def require(ok, detail):
    if not ok:
        raise AssertionError(detail)

def pipeline():
    core = FallNodeCore('codex-glp01', calibration=copy.deepcopy(artifact))
    result = core.process(points, 100.0, seq=7, stamp_secs=100, stamp_nsecs=123,
                          frame_id='innolidar', now=100.0)
    produced = result['snapshot']
    parsed = consumer(produced)
    require(parsed['status']=='ready', 'actual FallNodeCore pipeline: '+str(parsed))
    require(parsed['R']==derived['R'] and parsed['t']==derived['t'], 'changed R/t')
    require(parsed['support']['status']=='unavailable', 'invented support')
    require(result['state']['coordinate']==produced['coordinate'], 'state projection changed')
    projected = project_snapshot_for_ros(produced)
    require(all('evidence_indices' not in c for c in projected['candidates']), 'ROS evidence retained')
    require(all('evidence_indices' in c for c in produced['candidates']), 'producer cache mutated')
    for candidate in produced['candidates']:
        rows = points[np.asarray(candidate['evidence_indices'])]
        mapped = rows @ np.asarray(derived['R']).T + np.asarray(derived['t'])
        require(np.allclose(mapped.min(axis=0),candidate['bbox_ground_min_m']), 'ground bbox changed')
        require(np.allclose(mapped.max(axis=0),candidate['bbox_ground_max_m']), 'ground bbox changed')
    same = core.apply_ground_context(calibration=copy.deepcopy(artifact))
    require(same['changed'] is False, 'same-context reload changed')
check('actual_node_tilted_nonzero_t_ros_json_js', ['P01','P03','P04','P05','P06','M02','M05','M12'], pipeline)

def tuple_path():
    typed = copy.deepcopy(artifact)
    typed['ground_derived']['R'] = tuple(tuple(row) for row in derived['R'])
    typed['ground_derived']['t'] = tuple(derived['t'])
    validate_geometry_calibration(typed)
    produced = snapshot(points, calibration=typed, ground=ground)
    require(any(c['bbox_ground_from']=='actual_points' for c in produced['candidates']), 'tuple source invalid')
    require(produced['coordinate']['ground'] is not None, 'validator accepted tuple R/t, but projection returned null')
    require(consumer(produced)['status']=='ready', 'tuple accepted but JS refused')
check('existing_legal_tuple_artifact', ['P01','P02','P03','M02','M09'], tuple_path)

for name, context, expected in [
    ('artifact_only', {'calibration':artifact}, 'unqualified'),
    ('legacy_ground_only', {'ground':ground}, 'unavailable'),
    ('none', {}, 'unavailable'),
    ('foreign_frame', {'calibration':artifact,'ground':ground,'frame_id':'foreign'}, 'unavailable'),
    ('different_parent', {'calibration':artifact,'ground':tilted_ground(offset=1.9)}, 'unavailable'),
]:
    def null_case(context=context, expected=expected, name=name):
        value = snapshot(points, **context)
        require(consumer(value)['status']==expected, name+' parse status')
        if name=='artifact_only':
            require(value['ground'] is None and value['calibration']['ground_status']=='unknown', 'legacy qualification changed')
    check(name, ['P02','P03','P06','M03','M04','M08'], null_case)

def empty_case():
    value = snapshot(np.empty((0,3)), calibration=artifact, ground=ground)
    require(not value['candidates'], 'fabricated candidates')
    require(consumer(value)['status']=='ready', 'empty candidates lost transform')
check('empty_candidate_transform', ['P01','P03','M01'], empty_case)

for label, mutate in [
    ('parent_kind', lambda a:a.update(kind='broken')),
    ('parent_schema', lambda a:a.update(schema_version=2)),
    ('parent_id', lambda a:a.update(calibration_id='')),
    ('child_schema', lambda a:a['ground_derived'].update(schema_version=2)),
    ('child_units', lambda a:a['ground_derived'].update(units='mm')),
    ('child_id', lambda a:a['ground_derived'].update(ground_derived_id='broken')),
    ('child_R', lambda a:a['ground_derived']['R'][0].__setitem__(0, 2.0)),
    ('child_t', lambda a:a['ground_derived']['t'].__setitem__(2, 2.9)),
    ('physical_flag', lambda a:a['ground_derived'].update(physical_verified=True)),
]:
    def bad_case(mutate=mutate):
        bad = copy.deepcopy(artifact)
        mutate(bad)
        value = snapshot(points, calibration=bad, ground=ground)
        require(value['coordinate']['ground'] is None, 'invalid artifact published transform')
        require(consumer(value)['status']!='ready', 'invalid artifact enabled rendering')
    check('bad_'+label, ['P02','M09'], bad_case)

def isolation():
    before = copy.deepcopy(artifact)
    first = snapshot(points, calibration=artifact, ground=ground)
    first['coordinate']['ground']['R'][0][0] = 99
    first['coordinate']['ground']['t'][2] = 99
    next_value = snapshot(points, calibration=artifact, ground=ground)
    require(artifact==before, 'artifact was mutated')
    require(next_value['coordinate']['ground']['R']==derived['R'], 'next R polluted')
    require(next_value['coordinate']['ground']['t']==derived['t'], 'next t polluted')
check('output_isolation', ['P02','P04','M07'], isolation)

def compatibility():
    loader = importlib.machinery.SourceFileLoader('codex_glp01_old', str(OUT/'02_lidar_candidates_before.txt'))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    old = importlib.util.module_from_spec(spec)
    loader.exec_module(old)
    args = dict(session_id='comparison', time_epoch=0, snapshot_id='sample',
                seq=7, stamp_secs=100, stamp_nsecs=123, ground=ground, calibration=artifact)
    original = old.build_snapshot(points, **args)
    current = build_snapshot(points, **args)
    raw_length = len(dumps_strict(current))-len(dumps_strict(original))
    current['coordinate'].pop('ground')
    for key in ('support_polygon','support_polyline','support_reason'):
        current['ground'].pop(key)
    require(current==original, 'non-additive source/reference/candidate change')
    require(raw_length>0 and raw_length<2048, 'unexpected wire growth '+str(raw_length))
    records.append({'name':'wire_size_delta','result':'PASS','bytes':raw_length,'ids':['P06']})
check('old_message_compatibility', ['P06','M12'], compatibility)

report = {'source_sha256':hashlib.sha256((PACKAGE/'core/lidar_candidates.py').read_bytes()).hexdigest(),
          'checks':records,'device':'NOT_RUN','physics':'NOT_RUN'}
target = OUT/'93_codex_independent_results.json'
with target.open('x',encoding='utf-8') as handle:
    json.dump(report,handle,ensure_ascii=False,indent=2)
print(json.dumps({'checks':len(records),'failures':[r for r in records if r['result']=='FAIL']}))
sys.exit(1 if any(r['result']=='FAIL' for r in records) else 0)

