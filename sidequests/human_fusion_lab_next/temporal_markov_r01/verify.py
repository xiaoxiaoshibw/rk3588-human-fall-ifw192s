"""Read-only delivery audit. Writes one new evidence record, never source data."""
import ast
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.error import HTTPError
import numpy as np
from experiment import HERE,ROOT,OLD,EVIDENCE,read,sha,write
from temporal import sequence,POSTURES,EVENTS


def main():
    run=EVIDENCE/'run_r3';manifest=read(run/'INPUT_MANIFEST.json');cfg=read(run/'FROZEN_CONFIG.json');checks={}
    for sid,s in manifest['sources'].items():
        p=ROOT/'captures/remote'/sid
        checks[sid+'_source_unchanged']=dict(meta=sha(p/'meta.json'),points=sha(p/'points.bin'))==s['sha256']
        checks[sid+'_annotations_absent']=len(read(p/'meta.json').get('human_annotations',[]))==0
    checks['no_new_labels']=not list((OLD/'labels').glob('*.json'))
    catalog=read(run/'catalog.json');repro={};description={}
    for s in catalog:
        sid=s['sid'];rows=read(run/sid/'features.json');actual=sequence(rows,cfg);frozen=read(run/sid/'predictions.json')
        repro[sid]=actual==frozen
        description[sid]=dict(rf_range=[min([r['rf'] for r in rows if r['rf'] is not None],default=None),max([r['rf'] for r in rows if r['rf'] is not None],default=None)],
                              event_hmm_states={name:sum(int(np.argmax(o['event_hmm']))==i for o in frozen) for i,name in enumerate(EVENTS)},
                              single_frame_posture_switches=sum(int(np.argmax(a['emission']))!=int(np.argmax(b['emission'])) for a,b in zip(frozen,frozen[1:]) if not b['reset']))
        prefix=sequence(rows[:min(50,len(rows))],cfg)
        checks[sid+'_causal_prefix']=all({k:v for k,v in a.items() if k!='offline_viterbi'}=={k:v for k,v in b.items() if k!='offline_viterbi'} for a,b in zip(prefix,frozen))
    checks['fresh_temporal_reproduction']=all(repro.values())
    checks['python38_syntax']=all(ast.parse((HERE/n).read_text(encoding='utf8'),feature_version=(3,8)) for n in ['temporal.py','experiment.py','server.py'])
    baseline=read(EVIDENCE/'BASELINE.json');changes={p:dict(before=h,after=sha(ROOT/p) if (ROOT/p).exists() else None) for p,h in baseline['files'].items() if not (ROOT/p).exists() or sha(ROOT/p)!=h}
    # HTTP checks do not create human labels or modify frozen results.
    base='http://127.0.0.1:8947'
    def get(url):
        with urlopen(base+url,timeout=30) as r:return json.load(r)
    def post(url,body):
        req=Request(base+url,data=json.dumps(body).encode(),headers={'Content-Type':'application/json'})
        with urlopen(req,timeout=60) as r:return json.load(r)
    checks['http_catalog']=len(get('/api/catalog')['sessions'])==9
    sid=catalog[0]['sid'];session=get('/api/session?sid='+sid);cloud=get('/api/cloud?sid='+sid+'&fi=0')
    checks['http_same_frame']=cloud['sid']==sid and cloud['fi']==session['rows'][0]['fi']
    recompute=post('/api/infer',dict(sid=sid,start=20,params={'ema_tau_s':.6}))
    checks['http_reset_start']=recompute['predictions'][0]['fi']==session['rows'][20]['fi'] and recompute['predictions'][0]['feature']['vertical_velocity'] is None
    for name,url,body in [('bad_param','/api/infer',dict(sid=sid,params={'ema_tau_s':float('nan')})),('bad_reviewer','/api/review',dict(sid=sid,fi=0,reviewer=['AI'],posture='UNKNOWN',event='UNKNOWN'))]:
        try:post(url,body);checks[name+'_rejected']=False
        except HTTPError as ex:checks[name+'_rejected']=ex.code==400
    results=dict(checks=checks,temporal_reproduction=repro,descriptive=description,baseline_changes=changes,
                 note='Changed baseline files, if any, are concurrent user work; this item only writes isolated new subtree/evidence and appends track entry/return.',
                 human_reviews_not_created=not (EVIDENCE/'human_reviews').exists())
    write(EVIDENCE/'VERIFICATION_R1.json',results)
    print(json.dumps(results,ensure_ascii=False,indent=2))
    if not all(checks.values()):raise SystemExit(1)


if __name__=='__main__':main()
