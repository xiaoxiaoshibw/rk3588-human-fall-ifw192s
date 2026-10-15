"""Recompute existing leveling/registration algorithms into exclusive new artifacts."""
import argparse
import json
import subprocess
import sys
import uuid
from pathlib import Path

ROOT=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(ROOT/'pc_apps/human_replay'))
import leveling

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',required=True);args=p.parse_args()
    out=Path(args.out).resolve();jobs={}
    for sid,reportfile in [('cap_20261013_094333','2026-10-13_hf_real_01_r1'),('cap_20261013_131958','2026-10-13_hf_real_02_r1')]:
        old=json.loads((ROOT/'docs/human_fall/evidence'/reportfile/(sid+'_leveling.json')).read_text(encoding='utf8'))
        # Existing algorithmic regions are reused, but freeze_domain/three fits/export run anew.
        config={**old['config'],'mode':'frozen_algorithm_regions',
                'basis':'Recomputed frozen algorithm candidate regions; no new physical ground review',
                'ground_confirmed':False,'ground_identification':'algorithm_candidate'}
        job=uuid.uuid4().hex
        source=leveling.source(ROOT/'captures/remote',sid)[2]
        report,artifacts=leveling.run_job(ROOT/'captures/remote',ROOT/'captures/leveled',
            {'sid':sid,'source':source,'config':config},job,lambda msg:print(sid,msg,flush=True))
        jobs[sid]={'job_id':job,'recommended':report['recommended'],'source':source,
                   'path':str(ROOT/'captures/leveled'/job),'region_origin':str(ROOT/'docs/human_fall/evidence'/reportfile/(sid+'_leveling.json'))}
        with (out/(sid+'_leveling_recomputed.json')).open('x',encoding='utf8') as f:json.dump(jobs[sid],f,indent=2)
    cmd=['node',str(ROOT/'pc_apps/human_replay/registration.js'),
         '--source=cap_20261013_094333','--reference=cap_20261013_131958',
         '--source-job='+jobs['cap_20261013_094333']['job_id'],'--reference-job='+jobs['cap_20261013_131958']['job_id'],
         '--outdir='+str(out/'registration_094333_131958_v1')]
    run=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True,encoding='utf8')
    (out/'REGISTRATION_REBUILD.log').write_text(run.stdout+run.stderr,encoding='utf8')
    with (out/'REGISTRATION_REBUILD_RUN.json').open('x',encoding='utf8') as f:json.dump({'command':cmd,'exit_code':run.returncode,'jobs':jobs},f,indent=2)
    print(run.stdout,run.stderr,flush=True)
    sys.exit(run.returncode)
