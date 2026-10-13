"""Non-atomic full-tree boundary audit including tracked/untracked/ignored files."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time

ROOT=Path(__file__).resolve().parents[4]
OUT=ROOT/'docs/human_capture/evidence/2026-10-12_hfus_d05_r4'
target=OUT/'FINAL_TREE_SHA.json';assert not target.exists()
started=time.time();categories={}
for kind,args in [('tracked',['ls-files','-z']),('untracked',['ls-files','--others','--exclude-standard','-z']),('ignored',['ls-files','--others','--ignored','--exclude-standard','-z'])]:
    for p in subprocess.check_output(['git',*args],cwd=ROOT).decode('utf-8').split('\0'):
        if p:categories[p]=kind
files=[];errors=[];drift=[]
for base,dirs,names in os.walk(ROOT):
    dirs[:]=[d for d in dirs if d!='.git']
    for name in names:
        p=Path(base)/name;rel=p.relative_to(ROOT).as_posix()
        if p==target:continue
        try:
            a=p.stat();h=hashlib.sha256()
            with p.open('rb') as f:
                for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
            z=p.stat();files.append({'path':rel,'category':categories.get(rel,'unclassified'),'sha256':h.hexdigest(),'size':a.st_size,'mtime_ns':a.st_mtime_ns})
            if (a.st_size,a.st_mtime_ns)!=(z.st_size,z.st_mtime_ns):drift.append(rel)
        except Exception as e:errors.append({'path':rel,'error':str(e)})
report={'branch':subprocess.check_output(['git','branch','--show-current'],cwd=ROOT).decode().strip(),'head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT).decode().strip(),'status':subprocess.check_output(['git','status','--porcelain=v1','--untracked-files=all'],cwd=ROOT).decode('utf-8'),'files':files,'errors':errors,'drift':drift,'started_unix':started,'finished_unix':time.time(),'scope':'all tracked/untracked/ignored; .git internals excluded; non-atomic; own evidence/browser outputs may grow and are listed separately'}
with target.open('x',encoding='utf-8') as f:json.dump(report,f,ensure_ascii=False,indent=2)
allowed=['sidequests/human_fusion_lab_next/d05/r02/','sidequests/human_fusion_lab_next/d05/r03/','sidequests/human_fusion_lab_next/d05/r04/','docs/human_capture/evidence/2026-10-11_hfus_d05_r2/','docs/human_capture/evidence/2026-10-12_hfus_d05_r3/','docs/human_capture/evidence/2026-10-12_hfus_d05_r4/']
def own(p):return any(p.startswith(a) for a in allowed) or p in ['docs/human_capture/README.md','docs/human_capture/returns/HFUS-D05.md']
current={r['path']:r for r in files};results=[]
for directory in ['2026-10-11_hfus_d05_r2','2026-10-12_hfus_d05_r3','2026-10-12_hfus_d05_r4']:
    old=json.loads((ROOT/'docs/human_capture/evidence'/directory/'BASELINE_BEFORE.json').read_text(encoding='utf-8'));before={r['path']:r for r in old['files']}
    changed=[p for p,r in before.items() if p in current and r['sha256']!=current[p]['sha256']];missing=sorted(set(before)-set(current));added=sorted(set(current)-set(before))
    results.append({'baseline':directory,'baseline_files':len(before),'head_unchanged':old['head']==report['head'],'branch_unchanged':old['branch']==report['branch'],'changed_in_scope':[p for p in changed if own(p)],'changed_outside_scope':[p for p in changed if not own(p)],'missing':missing,'added_in_scope':[p for p in added if own(p)],'added_outside_scope':[p for p in added if not own(p)]})
with (OUT/'BOUNDARY_COMPARISON.json').open('x',encoding='utf-8') as f:json.dump({'tree_manifest':'FINAL_TREE_SHA.json','comparisons':results,'errors':errors,'drift':drift,'not_atomic':True,'later_own_records':'final report/return/OpenCode/browser evidence written after scan must be independently SHA-recorded, not claimed in this snapshot'},f,ensure_ascii=False,indent=2)
print(json.dumps({'files':len(files),'errors':errors,'drift':drift,'comparisons':[{k:r[k] for k in ['baseline','head_unchanged','branch_unchanged','changed_outside_scope','missing','added_outside_scope']} for r in results],'seconds':time.time()-started},ensure_ascii=False))
