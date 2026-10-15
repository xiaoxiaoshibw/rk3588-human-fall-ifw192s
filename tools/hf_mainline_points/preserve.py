"""End rehash over original snapshot. Authorized shared-page/docs edits are reported separately."""
from pathlib import Path
import sys,time,json,hashlib
ROOT=Path(__file__).resolve().parents[2];E=ROOT/'docs/human_fall/evidence/2026-10-14_hf_mainline_points_r1';PS='sidequests/human_fusion_lab_next/pointset/r01/'
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def main():
 old=json.loads((E/'BASELINE_BEFORE.json').read_text(encoding='utf8'))['files'];changed=[];missing=[];errors=[];verified=0;authorized=[]
 own={PS+n for n in ['app.js','index.html','server.py','research_retention.py','test_retention.py','config_research_retention.json']}
 own.update(['docs/human_fall/WORKFLOW.md','docs/human_capture/README.md','docs/human_fall/REVIEW_LOG.md','docs/human_fall/returns/HF-MAINLINE-POINTS-01.md'])
 for n,h in old.items():
  if n in own or n.startswith('tools/hf_mainline_points/') or n.startswith(PS+'action_research_retention/'):
   authorized.append(n);continue
  p=ROOT/n
  if not p.exists():missing.append(n);continue
  try:actual=sha(p)
  except OSError as e:errors.append([n,str(e)]);continue
  if actual!=h:changed.append({'path':n,'before':h,'after':actual})
  else:verified+=1
  if verified%5000==0:print('REHASH',verified,flush=True)
 deps=json.loads((E/'DEPENDENCY_BINDINGS.json').read_text(encoding='utf8'));drift=[b['path'] for b in deps if sha(Path(b['path']))!=b['expected']]
 with (E/'PRESERVATION_REHASH.json').open('x',encoding='utf8') as f:json.dump({'verified':verified,'changed':changed,'missing':missing,'errors':errors,'authorized_and_own_new_paths':authorized,
    'dependency_drift':drift,'end_time_unix':time.time(),'scope':'Original files observed in initial sequential snapshot; current own output excluded; shared-page scene changes preserved and separately recorded; do not claim atomic full-tree freeze'},f,ensure_ascii=False,indent=2)
 print('PRESERVATION',verified,'changed',len(changed),'missing',len(missing),'errors',len(errors),'dependency_drift',drift,flush=True)
if __name__=='__main__':main()
