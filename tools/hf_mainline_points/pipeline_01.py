from pathlib import Path
import sys,json,time,subprocess
r=Path('D:/Code/ldiar');e=r/'docs/human_fall/evidence/2026-10-14_hf_mainline_points_r1';ps=r/'sidequests/human_fusion_lab_next/pointset/r01'
while not (e/'BASELINE_REPRODUCTION.json').exists():time.sleep(2)
cmd=[sys.executable,'-X','utf8','-B','-W','error',str(ps/'research_retention.py'),'run','--run-id','run_01','--config',str(ps/'config_research_retention.json')]
with (e/'CANDIDATE_01.stdout').open('x') as out, (e/'CANDIDATE_01.stderr').open('x') as err:
 c=subprocess.run(cmd,cwd=r,stdout=out,stderr=err)
(e/'CANDIDATE_01_EXIT.json').write_text(json.dumps({'command':cmd,'exit':c.returncode}),encoding='utf8')
if c.returncode:sys.exit(c.returncode)
current={'run_id':'run_01','baseline_id':json.loads((e/'BASELINE_REPRODUCTION.json').read_text(encoding='utf8'))['baseline_id'],'variants':['local','reference','temporal','combined','r3','feedback'],'default':'R1_BASELINE','identity':'UNKNOWN'}
with (ps/'action_research_retention/CURRENT.json').open('x',encoding='utf8') as f:json.dump(current,f)
cmd=[sys.executable,'-X','utf8','-B','-W','error',str(r/'tools/hf_mainline_points/verify_retention.py'),'run_01']
with (e/'VERIFY_01.stdout').open('x') as out,(e/'VERIFY_01.stderr').open('x') as err:c=subprocess.run(cmd,cwd=r,stdout=out,stderr=err)
(e/'VERIFY_01_EXIT.json').write_text(json.dumps({'command':cmd,'exit':c.returncode}),encoding='utf8')
