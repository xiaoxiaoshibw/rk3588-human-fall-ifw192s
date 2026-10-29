"""Read-only OpenCode dispatch and actual-model audit, per-process settings."""
import json
import os
import subprocess
import sys
import time
from register import ROOT, HERE, EV, sha, put

def main(label):
    request=EV/(label+'_REQUEST.md')
    binary=r'C:\Users\30680\AppData\Roaming\npm\node_modules\@opencode\cli\bin\opencode.exe'
    permission={'*':'deny','read':'allow','glob':'allow','grep':'allow','list':'allow','external_directory':{'C:/Users/30680/.codex/skills/**':'allow','D:/Code/ldiar/**':'allow'}}
    env=os.environ.copy();env['OPENCODE_DISABLE_AUTOUPDATE']='true'
    env['OPENCODE_CONFIG_CONTENT']=json.dumps(dict(snapshot=False,permission=permission,agent=dict(plan=dict(permission=permission))))
    cmd=[binary,'run','--standalone','--agent','plan','-m','opencode-go/deepseek-v4.1-flash','--format','json','Please read '+request.as_posix()+' and perform the complete read-only review. Return findings in Chinese.']
    before={p.name:sha(p) for p in HERE.glob('*.py')}
    t=time.perf_counter();timeout=False
    with (EV/(label+'.jsonl')).open('x',encoding='utf8') as out,(EV/(label+'.stderr')).open('x',encoding='utf8') as err:
        process=subprocess.Popen(cmd,cwd=ROOT,env=env,stdout=out,stderr=err)
        try:code=process.wait(timeout=1200)
        except subprocess.TimeoutExpired:
            timeout=True
            subprocess.run(['taskkill','/PID',str(process.pid),'/T','/F'],stdout=err,stderr=err)
            code=process.wait()
    events=[]
    for line in (EV/(label+'.jsonl')).read_text(encoding='utf8').splitlines():
        try:events.append(json.loads(line))
        except ValueError:pass
    text='\n\n'.join(e.get('part',{}).get('text','') for e in events if e.get('type')=='text')
    put(EV/(label+'.md'),text)
    sessions=sorted({e['sessionID'] for e in events if e.get('sessionID')})
    models=[]
    if sessions:
        cp=subprocess.run([binary,'session','export','--standalone',sessions[0]],cwd=ROOT,env=env,capture_output=True,text=True,encoding='utf8',timeout=45)
        put(EV/(label+'_EXPORT.json'),cp.stdout)
        if cp.returncode==0:
            messages=json.loads(cp.stdout).get('messages',[])
            models=sorted({m['model']['providerID']+'/'+m['model'].get('modelID',m['model'].get('id','')) for m in messages if m.get('type')=='assistant' and isinstance(m.get('model'),dict)})
    toolparts=[e.get('part',{}) for e in events if e.get('type')=='tool_use']
    after={p.name:sha(p) for p in HERE.glob('*.py')}
    reads=[p.get('state',{}).get('input',{}).get('path',p.get('state',{}).get('input',{}).get('filePath','')).replace('\\','/').lower() for p in toolparts if p.get('tool')=='read' and p.get('state',{}).get('status')=='completed']
    status=dict(command=cmd,exit_code=code,timed_out=timeout,seconds=time.perf_counter()-t,sessions=sessions,actual_models=models,source_before=before,source_after=after,source_unchanged=before==after,request_sha=sha(request),request_read_observed=request.as_posix().lower() in reads,ponytail_read_observed=any('ponytail/skill.md' in p for p in reads),tools=sorted({p.get('tool','') for p in toolparts}),tool_calls=len(toolparts),independent_execution='NOT_RUN',text_chars=len(text))
    put(EV/(label+'_STATUS.json'),status);print(json.dumps(status),flush=True)

if __name__=='__main__':main(sys.argv[1])
