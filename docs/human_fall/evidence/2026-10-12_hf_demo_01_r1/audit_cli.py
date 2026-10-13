"""Specified read-only OpenCode audit; persist actual child exit even if export fails."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT=Path.cwd()
OUT=ROOT/'docs/human_fall/evidence/2026-10-12_hf_demo_01_r1'
brief=Path(sys.argv[1]).resolve();label=sys.argv[2]
binary=r'C:\Users\30680\AppData\Roaming\npm\node_modules\opencode-ai\bin\opencode.exe'
model='opencode-go/deepseek-v4.1-flash'
prompt=brief.read_text(encoding='utf-8');carrier='Please read '+brief.as_posix()+' and follow all instructions in that file. Return the review in Chinese.'
env=os.environ.copy();env['OPENCODE_DISABLE_AUTOUPDATE']='true'
env['OPENCODE_CONFIG_CONTENT']=json.dumps({'permission':{'*':'deny','read':'allow','glob':'allow','grep':'allow','list':'allow','external_directory':{'C:/Users/30680/.codex/skills/ponytail/*':'allow'}}})
command=[binary,'run','--agent','plan','-m',model,'--format','json',carrier];started=time.time()
with (OUT/(label+'.jsonl')).open('x',encoding='utf-8') as log:
    process=subprocess.Popen(command,cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT)
    pid=process.pid
    try:code=process.wait(timeout=900);timeout=False
    except subprocess.TimeoutExpired:
        subprocess.run(['taskkill','/PID',str(pid),'/T','/F'],stdout=log,stderr=subprocess.STDOUT);process.wait();code=process.returncode;timeout=True
events=[]
for line in (OUT/(label+'.jsonl')).read_text(encoding='utf-8').splitlines():
    try:events.append(json.loads(line))
    except json.JSONDecodeError:pass
parts=[e.get('part',{}) for e in events if e.get('type')=='tool_use']
text='\n\n'.join(e.get('part',{}).get('text','') for e in events if e.get('type') in ('text','part.text'))
with (OUT/(label+'.md')).open('x',encoding='utf-8') as f:f.write(text)
status={'pid':pid,'command':command[:-1],'requested_model':model,'exit_code':code,'timed_out':timeout,'elapsed_s':time.time()-started,'readonly':True,'tools':sorted({p.get('tool') for p in parts}),'instruction_sha256':hashlib.sha256(prompt.encode()).hexdigest(),'instruction_unchanged':brief.read_text(encoding='utf-8')==prompt,'instruction_read':any(p.get('tool')=='read' and p.get('state',{}).get('input',{}).get('filePath','').replace('\\','/').lower()==brief.as_posix().lower() and p['state']['status']=='completed' and not p['state'].get('metadata',{}).get('truncated',False) for p in parts),'skill_read':any(p.get('tool')=='read' and 'ponytail' in p.get('state',{}).get('input',{}).get('filePath','') for p in parts),'complete_text':'REVIEW_COMPLETE' in text}
try:
    sid=next(e['sessionID'] for e in events if e.get('sessionID'));export=subprocess.run([binary,'export',sid],cwd=ROOT,capture_output=True,encoding='utf-8',timeout=180)
    with (OUT/(label+'_EXPORT.json')).open('x',encoding='utf-8') as f:f.write(export.stdout)
    messages=json.loads(export.stdout)['messages'];status['export_exit']=export.returncode
    status['actual_models']=sorted({m['info'].get('providerID','')+'/'+m['info'].get('modelID','') for m in messages if m['info'].get('role')=='assistant'})
    users=['\n'.join(p.get('text','') for p in m.get('parts',[]) if p.get('type')=='text').strip('"') for m in messages if m['info'].get('role')=='user'];status['carrier_verified']=carrier in users
except Exception as e:status['export_error']=str(e)
ok=code==0 and not timeout and status['instruction_read'] and status['skill_read'] and status['instruction_unchanged'] and status['complete_text'] and status.get('actual_models')==[model] and status.get('carrier_verified') and set(status['tools'])<={'read','glob','grep','list'}
status['dispatch_status']='PASS' if ok else 'FAIL'
with (OUT/(label+'_STATUS.json')).open('x',encoding='utf-8') as f:json.dump(status,f,ensure_ascii=False,indent=2)
print(json.dumps(status,ensure_ascii=False));raise SystemExit(0 if ok else 1)
