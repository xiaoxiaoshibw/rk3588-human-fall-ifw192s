"""Baseline includes tracked and untracked files; focused independent commands."""
import ast
import hashlib
import json
import subprocess
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[5]
OUT=Path(__file__).resolve().parent
def git(*args):
    return subprocess.check_output(['git',*args],cwd=ROOT)
def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()
def baseline():
    paths=git('ls-files','--cached','--others','--exclude-standard','-z').decode('utf-8').split('\0')
    files={};unreadable=[]
    for name in sorted(set(paths)-{''}):
        try:files[name]=sha(ROOT/name)
        except OSError:unreadable.append(name)
    return {'head':git('rev-parse','HEAD').decode().strip(),
        'branch':git('branch','--show-current').decode().strip(),
        'status':git('status','--porcelain=v1','-uall').decode('utf-8'),
        'files':files,'unreadable':unreadable}
def save(name,data):
    (OUT/name).write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
before=baseline();save('00_baseline.json',before)
manifest=json.loads((OUT.parent/'22_source_manifest.json').read_text(encoding='utf-8'))
matches={k:sha(ROOT/k)==v for section in ('sources','data','acceptance')
         for k,v in manifest[section].items()}
save('01_submitted_sha.json',matches)
assert all(matches.values()),matches
results={}
jobs=[('10_r6_matrix',['docs/human_fall/evidence/2026-10-02_gl03_r6/codex_review_01/input_matrix_checks.py']),
      ('11_structure',['docs/human_fall/evidence/2026-10-02_gl03_r7/codex_review_01/structure_checks.py']),
      ('12_fall',['-m','unittest','discover','-s','src/human_fall_detection/tests','-v'])]
for name,args in jobs:
    command=[sys.executable,'-B','-W','error']+args
    with (OUT/(name+'.txt')).open('w',encoding='utf-8') as log:
        log.write('COMMAND: '+repr(command)+'\n');log.flush()
        result=subprocess.run(command,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
        log.write('\nEXIT='+str(result.returncode)+'\n')
    results[name]=result.returncode;print(name,result.returncode,flush=True)
for k in manifest['sources']:
    if k.startswith('src/'):
        ast.parse((ROOT/k).read_text(encoding='utf-8'),feature_version=(3,8))
results['py38_ast']='PASS (syntax only)'
a=ROOT/'docs/human_fall/evidence/2026-10-02_gl03_r3/21_o01_planes_ablation_r3.json'
b=OUT.parent/'24_o01_planes_ablation_r7.json'
results['O01_byte_equal']=a.read_bytes()==b.read_bytes()
results['O01_sha']=sha(b)
save('13_results.json',results)
after=baseline()
deltas={k:{'before':v,'after':after['files'].get(k)} for k,v in before['files'].items()
        if after['files'].get(k)!=v}
save('14_end_deltas.json',{'head_before':before['head'],'head_after':after['head'],
    'changed_existing':deltas,'new':sorted(set(after['files'])-set(before['files'])),
    'submitted_source_unchanged':{k:sha(ROOT/k)==v for k,v in manifest['sources'].items()}})
print(json.dumps(results),flush=True)
