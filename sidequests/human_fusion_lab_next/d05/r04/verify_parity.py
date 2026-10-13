"""Full sequential replay equivalence; compare every point/decision, never generated from GT."""
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[4]
OLD=ROOT/'docs/human_capture/evidence/2026-10-11_hfus_d05_r2'
OUT=ROOT/'docs/human_capture/evidence/2026-10-12_hfus_d05_r4'
def load(p):return json.loads(p.read_text(encoding='utf-8'))
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
    return h.hexdigest()
def rows(p):
    with p.open(encoding='utf-8') as f:
        for line in f:yield json.loads(line)
keys=['sid','segment','timestamp_s','frame_index','timestamp','raw_n','valid_n','qualification','exhaustive','gt','candidates','raw_components','pre_components','stages','split_log','model_calls','tracks','visible_candidates','strict','legacy','bg','foreground_count']
old=load(OLD/'runs/full/split/R02_split_SUMMARY.json');new=load(OUT/'runs/fast/R04_fast_SUMMARY.json');assert len(old['sessions'])==len(new['sessions'])==9
results=[]
with (OUT/'FRAME_PARITY.jsonl').open('x',encoding='utf-8') as log:
    for a,b in zip(old['sessions'],new['sessions'],strict=True):
        assert a['sid']==b['sid'];p=Path(a['ledger']['path']);q=Path(b['ledger']['path']);assert sha(p)==a['ledger']['sha256'] and sha(q)==b['ledger']['sha256']
        for k in ['input_sha256','gt_manifest_sha256','model_sha256','config','frames','qualified_frames','gt_persons','unknown_frames','candidate_count','proposal','accepted','observed_confirmed','legacy_accepted','legacy_confirmed']:assert a[k]==b[k],(a['sid'],k)
        n=0
        for x,y in zip(rows(p),rows(q),strict=True):
            n+=1
            for k in keys:assert x[k]==y[k],(a['sid'],x['frame_index'],k)
            payload=json.dumps({k:x[k] for k in keys},sort_keys=True,separators=(',',':')).encode()
            log.write(json.dumps({'sid':a['sid'],'frame_index':x['frame_index'],'timestamp':x['timestamp'],'status':'EXACT_PARITY','decision_pointset_sha256':hashlib.sha256(payload).hexdigest()})+'\n')
        assert n==a['frames'];results.append({'sid':a['sid'],'frames':n,'status':'PASS','reference_ledger_sha256':a['ledger']['sha256'],'current_ledger_sha256':b['ledger']['sha256']});print(a['sid'],n,'EXACT_PARITY',flush=True)
for source in new['sources']:assert sha(ROOT/source['path'])==source['sha256']
with (OUT/'PARITY_SUMMARY.json').open('x',encoding='utf-8') as f:json.dump({'status':'PASS','frames':sum(s['frames'] for s in results),'sessions':results,'fields':keys,'limits':'same partial GT and remaining failures as R02; timing excluded; no inference using GT'},f,indent=2)
cases=load(OLD/'analysis_v2/CASE_INDEX.json')+load(ROOT/'docs/human_capture/evidence/2026-10-12_hfus_d05_r3/analysis_v1/CASE_INDEX.json')
cases=[c for c in cases if c['variant']=='gate']+load(OLD/'analysis_v2/CASE_INDEX.json')
cases += [{**c,'variant':'fast','exact_replay_parity':'R02 split'} for c in cases if c['variant']=='split']
with (OUT/'CASE_INDEX.json').open('x',encoding='utf-8') as f:json.dump(cases,f,ensure_ascii=False,indent=2)
