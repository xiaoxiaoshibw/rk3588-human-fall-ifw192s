import pathlib,subprocess,sys,time,json
r=pathlib.Path('D:/Code/ldiar');e=r/'docs/human_fall/evidence/2026-10-14_hf_mainline_points_r1';run=r/'sidequests/human_fusion_lab_next/pointset/r01/action_research_retention/run_02'
while not (run/'GUARD_BINDING.json').exists():time.sleep(2)
commands=[['-X','utf8','-B','-W','error','tools/hf_mainline_points/split_guard_ledger.py','run_02'],['-X','utf8','-B','-W','error','tools/hf_mainline_points/finalize_ledger.py','run_02'],['-X','utf8','-B','-W','error','tools/hf_mainline_points/summarize_retention.py','run_02'],['-X','utf8','-B','-W','error','tools/hf_mainline_points/verify_retention_v2.py','run_02']]
for i,cmd in enumerate(commands):
 with (e/f'FINISH_02_{i}.stdout').open('x') as out,(e/f'FINISH_02_{i}.stderr').open('x') as err:c=subprocess.run([sys.executable]+cmd,cwd=r,stdout=out,stderr=err)
 (e/f'FINISH_02_{i}_EXIT.json').write_text(json.dumps({'command':cmd,'exit':c.returncode}),encoding='utf8')
 if c.returncode:sys.exit(c.returncode)
