"""Bind reproducible source snapshots, environment and read-only-change audit."""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import shutil
import sys
import time
import joblib
import numpy as np
import sklearn
from train_public_lidar import sha


def run(evidence,models):
    baseline=json.loads((evidence/'BASELINE.json').read_text(encoding='utf-8'))
    changes=[];checked=0
    for row in baseline['files']:
        path=Path(row['path']);name=path.as_posix()
        # Concentrate concurrent-write detection on all source/config/docs outside historical artifacts.
        if path.suffix.lower() not in ['.py','.js','.html','.yaml','.yml','.json','.md','.cpp','.hpp','.h','.txt','.bat','.sh']:
            continue
        if '/evidence/' in name or name.startswith(('dist/','data/','captures/')):continue
        checked+=1
        current=sha(path) if path.is_file() else 'MISSING'
        if current!=row['sha256']:changes.append({'path':name,'before':row['sha256'],'after':current})
    source_dir=evidence/'source_snapshot';source_dir.mkdir(exist_ok=False)
    source={}
    for p in Path('ML/src').glob('*.py'):
        shutil.copyfile(p,source_dir/p.name);source[str(p)]=sha(p)
    full=joblib.load(models/'w30_final.joblib')['model']
    freeze=json.loads((evidence/'FREEZE.json').read_text(encoding='utf-8'))
    baseline_models=Path('ML/models/public_lidar_20261022/mmfi')
    assert all(sha(baseline_models/name)==value for name,value in freeze['baseline_models'].items())
    assert all(sha(models/name)==value for name,value in freeze['models'].items())
    assert all(sha(Path('ML/src')/name)==value for name,value in freeze['source'].items())
    original=json.loads((baseline_models/'SUMMARY.json').read_text(encoding='utf-8'))
    assert json.loads((evidence/'E01_cache/INPUT.json').read_text(encoding='utf-8'))['sha256']==original['input'][0]['sha256']
    ground_path=Path('docs/human_fall/evidence/2026-10-18_hfus_project_dev_r1/leveling_02/TRANSFORM.json')
    ground=json.loads(ground_path.read_text(encoding='utf-8'))
    replay=json.loads((evidence/'raw_replay/SUMMARY.json').read_text(encoding='utf-8'))
    assert ground['sid']==replay['session']
    assert ground['source_sha256']=={'meta':replay['meta_sha256'],'points':replay['points_sha256']}
    result={'created_unix_s':time.time(),'python':platform.python_version(),'numpy':np.__version__,
            'sklearn':sklearn.__version__,'joblib':joblib.__version__,'platform':platform.platform(),
            'models':{str(p):sha(p) for p in models.glob('*') if p.is_file()},'source':source,
            'complete_RF_parameters':full.get_params(),'concurrent_source_audit':{'checked':checked,'changes':changes,
            'scope':'baseline hashes may span this session edits; own ML files expected; other changes retained and isolated'},
            'target_ground_binding_verified':True,'ground_physical_qualification':ground.get('qualification'),
            'original_and_frozen_model_SHA_unchanged':True,
            'target_meta_human_annotations':{p.parent.name:json.loads(p.read_text(encoding='utf-8')).get('human_annotations')
                                            for p in Path('data/sessions').glob('*/meta.json')},
            'failures_retained':[
                {'log':'develop.log','reason':'multi-thread predict_proba summation difference 1.11e-16; failed v1 kept; v2 tolerance 1e-14 and exact classes'},
                {'log':'targets.log','reason':'one metadata-only session missing points.bin; v2 records MISSING rather than inventing bytes'}],
            'unknown':['IFW192S action accuracy','IFW192S real fall recall','physical validity','native board performance',
                       'verified MM-Fi action onset intervals','cross-sensor coordinate alignment'],
            'no_deployment':True}
    with (evidence/'FINAL.json').open('x',encoding='utf-8') as f:json.dump(result,f,indent=2,ensure_ascii=False)
    hashes={str(p.relative_to(evidence)):sha(p) for p in evidence.rglob('*') if p.is_file()}
    with (evidence/'EVIDENCE_SHA256.json').open('x',encoding='utf-8') as f:json.dump(hashes,f,indent=2,ensure_ascii=False)
    print('final',len(hashes),'artifacts; source changes',changes,flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--evidence',type=Path,required=True);p.add_argument('--models',type=Path,required=True)
    a=p.parse_args();run(a.evidence,a.models)
