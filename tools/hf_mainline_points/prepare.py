"""Immutable preparation and preservation audit for HF-MAINLINE-POINTS-01."""
import hashlib,json,platform,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
E=ROOT/'docs/human_fall/evidence/2026-10-14_hf_mainline_points_r1'
PS=ROOT/'sidequests/human_fusion_lab_next/pointset/r01'
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def write(p,x):
 with p.open('x',encoding='utf8') as f:json.dump(x,f,ensure_ascii=False,indent=2)
def main():
 E.mkdir(exist_ok=False)
 for n in ['server.py','app.js','index.html']:(E/(n+'.before')).write_bytes((PS/n).read_bytes())
 (E/'GIT_STATUS_BEFORE.txt').write_bytes(subprocess.check_output(['git','status','--short','--untracked-files=all'],cwd=ROOT))
 write(E/'ENVIRONMENT.json',{'python':sys.version,'platform':platform.platform(),'branch':subprocess.check_output(['git','branch','--show-current'],cwd=ROOT,text=True).strip(),'HEAD':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'writer':'Codex only','skills':['C:/Users/30680/.codex/skills/ponytail/SKILL.md','C:/Users/30680/.codex/skills/scientific-toolkit-skill/SKILL.md']})
 deps=json.loads((ROOT/'docs/human_fall/evidence/2026-10-14_hf_mainline_points_plan_r1/CROSS_REPO_DEPENDENCY_SHA_AT_PLAN.json').read_text(encoding='utf8'))
 check=[{'path':r['Path'],'expected':r['Hash'].lower(),'actual':sha(Path(r['Path']))} for r in deps]
 write(E/'DEPENDENCY_BINDINGS.json',check)
 assert all(r['expected']==r['actual'] for r in check),'Cross-repo binding failure blocks Python'
 hashes={};errors=[]
 for p in ROOT.rglob('*'):
  if '.git' in p.parts or p.is_symlink() or not p.is_file() or E in p.parents:continue
  try:hashes[p.relative_to(ROOT).as_posix()]=sha(p)
  except OSError as ex:errors.append([str(p),str(ex)])
 write(E/'BASELINE_BEFORE.json',{'files':hashes,'errors':errors,'time_unix':time.time()})
 print('baseline',len(hashes),'files; errors',errors,flush=True)
if __name__=='__main__':main()
