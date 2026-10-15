"""Read-only live API/complete export check. No label or original source writes."""
import io,json,sys,urllib.request,urllib.error,time
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[2];PS=ROOT/'sidequests/human_fusion_lab_next/pointset/r01';sys.path.insert(0,str(PS))
from actions import read,dump,sha
E=ROOT/'docs/human_fall/evidence/2026-10-14_hf_mainline_points_r1'
def get(path):
 with urllib.request.urlopen('http://127.0.0.1:8944'+path) as r:return r.status,r.read()
def main():
 while not (PS/'action_research_retention/run_01/FINAL_TERMINAL_CONSERVATION.json').exists():time.sleep(2)
 status,b=get('/api/version');version=json.loads(b);assert status==200 and version['default']=='R1_BASELINE'
 sid='cap_20261013_083254';fi=92;q=f'sid={sid}&fi={fi}&dataset=actions&variant=ret_combined'
 _,b=get('/api/experiment?'+q);body=json.loads(b);members=body['body_3d'][0]['source_indices'];assert body['identity']=='UNKNOWN'
 _,b=get('/api/retention-diagnostic?'+q);diag=json.loads(b);assert len(diag['layers'])==9 and sum(diag['terminal_counts'].values())==body['source_frame']['count_points']
 _,b=get('/api/retention-members?'+q)
 with np.load(io.BytesIO(b)) as a:
  assert len(a['local_index'])==body['source_frame']['count_points'];assert np.array_equal(a['recovery_target'],members)
  assert np.array_equal(np.flatnonzero(a['recovery_final_terminal_reason']==10),members)
  records=len(a['global_row']);fields=a.files
 _,b=get('/api/retention-source?'+q+'&index=16959');point=json.loads(b)
 assert point['first_terminal_reason']=='BACKGROUND_MATCH' and point['recovery_state']==2 and point['candidate_final_terminal_reason']==10
 assert len(point['opaque_hex_12_27'])==32 and point['global_row']==body['source_frame']['offset_points']+16959
 invalid=['/api/experiment?sid=../escape&fi=0&variant=ret_combined','/api/experiment?'+q.replace('ret_combined','ret_unknown'),
     '/api/retention-source?'+q+'&index=-1','/api/retention-source?'+q+'&index=1.2',
     '/api/retention-diagnostic?'+q.replace('fi=92','fi=999999'),'/api/retention-members?'+q.replace('dataset=actions','dataset=legacy'),
     '/api/frame?sid=cap_20261013_131958&fi=0&dataset=actions']
 errors=[]
 for path in invalid:
  try:get(path)
  except urllib.error.HTTPError as ex:assert ex.code==400;errors.append({'path':path,'status':ex.code})
  else:raise AssertionError('Invalid request accepted '+path)
 dump(E/'API_CHECK.json',{'passed':True,'page_version':version,'complete_records':records,'export_fields':fields,'queried_restored_source':point,
      'invalid_inputs':errors,'GT_mutations':False,'bound_localhost_only':True,'code_sha':sha(Path(__file__))})
 print('API CHECK PASS',records,'full records',len(errors),'malformed requests',flush=True)
if __name__=='__main__':main()
