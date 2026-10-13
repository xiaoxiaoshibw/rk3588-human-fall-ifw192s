import os,json,hashlib,subprocess,time
from pathlib import Path
root=Path(__file__).resolve().parents[4]
out=root/'docs/human_capture/evidence/2026-10-13_hfus_pointset_01_r1'
files=[]
for base,dirs,names in os.walk(root):
 dirs[:]=[d for d in dirs if d!='.git']
 for name in names:
  p=Path(base)/name
  if p.is_file() and not p.is_symlink() and not p.is_relative_to(out) and not p.is_relative_to(Path(__file__).parent): files.append(p)
rows={};errors=[]
for i,p in enumerate(files):
 try:
  h=hashlib.sha256()
  with p.open('rb') as f:
   for b in iter(lambda:f.read(4*1024*1024),b''):h.update(b)
  rows[str(p.relative_to(root))]={'sha256':h.hexdigest(),'bytes':p.stat().st_size}
 except OSError as e:errors.append({'path':str(p),'error':str(e)})
 if i%1000==0:print('baseline',i,len(files),flush=True)
git=lambda *a:subprocess.check_output(['git','-C',str(root),*a],text=True,encoding='utf-8',errors='replace').strip()
(out/'BASELINE_BEFORE.json').write_text(json.dumps({'branch':git('branch','--show-current'),'head':git('rev-parse','HEAD'),'git_status':git('status','--short'),'files':rows,'errors':errors,'scope':'all regular files including ignored/untracked; .git and new item outputs excluded'},ensure_ascii=False,indent=1),encoding='utf-8')
print('baseline complete',len(rows),len(errors),flush=True)


