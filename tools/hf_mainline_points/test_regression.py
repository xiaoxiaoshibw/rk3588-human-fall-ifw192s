from pathlib import Path
import subprocess,sys,json
r=Path('D:/Code/ldiar');e=r/'docs/human_fall/evidence/2026-10-14_hf_mainline_points_r1'
commands=[(r/'pc_apps/human_replay',['node','human_pipe_lib.test.js']),(r/'pc_apps/human_replay',['node','registration.test.js']),(r/'pc_apps/console',['node','console_html.test.js']),(r/'pc_apps/console',[sys.executable,'-X','utf8','-B','-W','error','console_test.py']),(r,[sys.executable,'-X','utf8','-B','-W','error','-m','unittest','discover','-s','sidequests/human_fusion_lab_next/pointset/r01','-p','test_retention.py'])]
results=[]
for i,(cwd,cmd) in enumerate(commands):
 with (e/f'REGRESSION_{i}.log').open('x',encoding='utf8') as f:p=subprocess.run(cmd,cwd=cwd,stdout=f,stderr=subprocess.STDOUT)
 results.append({'cwd':str(cwd),'cmd':cmd,'exit':p.returncode,'log':f'REGRESSION_{i}.log'})
 print(i,p.returncode,flush=True)
with (e/'REGRESSION_RUNS.json').open('x',encoding='utf8') as f:json.dump(results,f,ensure_ascii=False,indent=2)
