from pathlib import Path
import subprocess,json,hashlib
base=Path('docs/human_capture/evidence/2026-10-10_human_unify_rework_r2')
probe_log=base/'opencode_probe_02.txt'
with probe_log.open('w',encoding='utf-8') as out:
 p=subprocess.Popen([r'C:\Users\30680\AppData\Roaming\npm\opencode.cmd','run','--agent','plan','-m','opencode-go/deepseek-v4.1-flash','--format','json','Reply PROBE_OK only. Do not use tools.'],stdout=out,stderr=subprocess.STDOUT)
 try:status=p.wait(timeout=55)
 except subprocess.TimeoutExpired:
  subprocess.run(['taskkill','/PID',str(p.pid),'/T','/F'],stdout=out,stderr=subprocess.STDOUT);p.wait();status=p.returncode
 out.write('\nREAL_EXIT='+str(status)+'\n')
if status!=0 or 'PROBE_OK' not in probe_log.read_text(encoding='utf-8'):raise SystemExit('probe blocked')
files=sorted(Path('pc_apps/human_core').glob('*'))
(base/'submitted_source_sha_02.json').write_text(json.dumps({str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in files if p.is_file()},indent=2),encoding='utf-8')
prompt=(base/'opencode_review_prompt_02.md').read_text(encoding='utf-8')
with (base/'opencode_review_02.jsonl').open('w',encoding='utf-8') as out:
 p=subprocess.Popen([r'C:\Users\30680\AppData\Roaming\npm\opencode.cmd','run','--agent','plan','-m','opencode-go/deepseek-v4.1-flash','--format','json',prompt],stdout=out,stderr=subprocess.STDOUT)
 try:status=p.wait(timeout=600)
 except subprocess.TimeoutExpired:
  subprocess.run(['taskkill','/PID',str(p.pid),'/T','/F'],stdout=out,stderr=subprocess.STDOUT);p.wait();status=p.returncode
 out.write('\nREAL_EXIT='+str(status)+'\n')
print('second audit done',status)
