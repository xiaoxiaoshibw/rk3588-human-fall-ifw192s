"""Freeze an explicit reviewed-inference candidate pointer; R1 remains the page default."""
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];PS=ROOT/'sidequests/human_fusion_lab_next/pointset/r01';sys.path.insert(0,str(PS))
from actions import read,dump
from research_retention import RESULT,E
def main():
    root=RESULT/'run_02';verify=read(root/'ALL_FRAME_VERIFICATION.json')
    assert all(r['frames']==1966 and r['prefix_member_equal']==1966 for r in verify['variants'].values())
    old={'r3':{'run_id':'run_01','variant':'r3','status':'FAILED_AUXILIARY_AXIS_REGRESSION_RETAINED; UNKNOWN; NOT_DEFAULT'},
         'failed_combined':{'run_id':'run_01','variant':'combined','status':'FAILED_GEOMETRIC_RISK_CONTROL_FIRST_RUN_RETAINED; UNKNOWN; NOT_DEFAULT'}}
    for v in ['local','reference','temporal']:old[v]={'run_id':'run_01','variant':v,'status':'FIRST_RUN_ABLATION_ONLY; UNKNOWN; NOT_DEFAULT'}
    current={'run_id':'run_02','baseline_id':read(E/'BASELINE_REPRODUCTION.json')['baseline_id'],
       'variants':['combined','feedback']+list(old),'variant_sources':old,'default':'R1_BASELINE','identity':'UNKNOWN',
       'status':'FROZEN_GUARDED_V2; REUSED_REGRESSION; HUMAN_BENEFIT_UNVERIFIED; NOT_DEFAULT'}
    dump(RESULT/'CURRENT_V2.json',current)
    print('CURRENT_V2 source-bound; R1 default unchanged',flush=True)
if __name__=='__main__':main()
