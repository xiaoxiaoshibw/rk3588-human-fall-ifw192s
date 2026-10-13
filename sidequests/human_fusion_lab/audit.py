from pathlib import Path
import sys,json,hashlib
ROOT=Path(__file__).resolve().parents[2]; LAB=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'pc_apps/human_ml'))
from frozen_gt import audit_session,SIDS,sha
from audit_fusion_sessions import EXPECTED
rows=[]; docs={}
for sid,name,n in EXPECTED:
 try:
  r,d,m=audit_session(sid,ROOT/'pc_apps/human_replay/gt_store',ROOT/'captures/remote')
  end=0
  for f in m['frames']:
   assert f['offset_points']==end;end+=f['count_points']
  assert end==m['total_points'] and (ROOT/'captures/remote'/sid/'points.bin').stat().st_size==end*28
  r.update(activity=name,contract_ok=True,expected_frames=n)
  if r['eligible']:docs[sid]=d
 except Exception as e:r={'sid':sid,'eligible':False,'issues':[repr(e)],'activity':name}
 rows.append(r);print(sid,r['eligible'],r.get('version'),r['issues'],flush=True)
splits={'train':SIDS[:2]+SIDS[3:5],'validation':[SIDS[2]],'test':SIDS[6:8],'stress':[SIDS[5]],'blocked':[SIDS[8]]}
assert len(set(sum(splits.values(),[])))==9
out={'sessions':rows,'docs':docs,'splits':splits,'threshold':0.55,'candidate_label_policy':{'positive_person_purity_min':0.8,'negative_furniture_purity_min':0.8,'mixed_or_uncovered':'UNKNOWN'},'holdout_status':'RETROSPECTIVE_SESSION_HOLDOUT; historical test sessions previously inspected; prospective unseen actor/scene performance UNKNOWN','gt_limits':'Reviewed provenance is a metadata claim, not independent physical truth. Propagated observations are correlated.'}
(LAB/'results/AUDIT.json').write_text(json.dumps(out,ensure_ascii=False),encoding='utf8')
