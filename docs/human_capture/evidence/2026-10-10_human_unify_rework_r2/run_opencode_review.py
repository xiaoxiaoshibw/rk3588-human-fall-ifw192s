from pathlib import Path
import subprocess,json,hashlib
base=Path('docs/human_capture/evidence/2026-10-10_human_unify_rework_r2')
files=sorted(Path('pc_apps/human_core').glob('*'))
(base/'submitted_source_sha.json').write_text(json.dumps({str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in files if p.is_file()},indent=2),encoding='utf-8')
prompt=(base/'opencode_review_prompt_01.md').read_text(encoding='utf-8-sig')
with (base/'opencode_review_01.jsonl').open('w',encoding='utf-8') as out:
 p=subprocess.Popen([r'C:\Users\30680\AppData\Roaming\npm\opencode.cmd','run','--agent','plan','-m','opencode-go/deepseek-v4.1-flash','--format','json',prompt],stdout=out,stderr=subprocess.STDOUT)
 try:
  status=p.wait(timeout=600)
  out.write('\nREAL_EXIT='+str(status)+'\n')
 except subprocess.TimeoutExpired:
  subprocess.run(['taskkill','/PID',str(p.pid),'/T','/F'],stdout=out,stderr=subprocess.STDOUT)
  p.wait();out.write('\nAUDIT_TIMEOUT=600 seconds; REAL_EXIT='+str(p.returncode)+'\n')
print('audit done')
