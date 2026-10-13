from pathlib import Path
import subprocess
base=Path('docs/human_capture/evidence/2026-10-10_human_unify_rework_r2')
with (base/'opencode_probe_01.txt').open('w',encoding='utf-8') as out:
 p=subprocess.Popen([r'C:\Users\30680\AppData\Roaming\npm\opencode.cmd','run','--agent','plan','-m','opencode-go/deepseek-v4.1-flash','--format','json','Reply PROBE_OK only. Do not use any tools.'],stdout=out,stderr=subprocess.STDOUT)
 try:
  status=p.wait(timeout=55)
  out.write('\nREAL_EXIT='+str(status)+'\n')
 except subprocess.TimeoutExpired:
  subprocess.run(['taskkill','/PID',str(p.pid),'/T','/F'],stdout=out,stderr=subprocess.STDOUT)
  p.wait();out.write('\nPROBE_TIMEOUT=55 seconds; REAL_EXIT='+str(p.returncode)+'\n')
print('probe done')
