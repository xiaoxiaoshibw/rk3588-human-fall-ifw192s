import pathlib,subprocess,sys,time,json
r=pathlib.Path('D:/Code/ldiar');e=r/'docs/human_fall/evidence/2026-10-14_hf_mainline_points_r1';run=r/'sidequests/human_fusion_lab_next/pointset/r01/action_research_retention/run_01'
while not (run/'FRAME_METRICS.json').exists():time.sleep(2)
cmd=[sys.executable,'-X','utf8','-B','-W','error','tools/hf_mainline_points/summarize_retention.py','run_01']
with (e/'SUMMARIZE_01.stdout').open('x') as out,(e/'SUMMARIZE_01.stderr').open('x') as err:c=subprocess.run(cmd,cwd=r,stdout=out,stderr=err)
(e/'SUMMARIZE_01_EXIT.json').write_text(json.dumps({'command':cmd,'exit':c.returncode}),encoding='utf8')
