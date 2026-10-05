import datetime,json,os,pathlib,subprocess,sys,time
root=pathlib.Path(__file__).resolve().parents[4];out=pathlib.Path(__file__).parent;phase=sys.argv[1]
if 'OPENCODE_DB' in os.environ:raise SystemExit('DB override present')
name='01_service_probe' if phase=='probe' else '03_opencode'
if any((out/(name+s)).exists() for s in ('.jsonl','.stderr.txt','_meta.json')):raise SystemExit('No evidence overwrite')
msg='No tools or file changes. Reply only PROBE_OK.' if phase=='probe' else 'Continue the SAME GL04 work item/session after verified compaction, now R7. Read docs/human_fall/AI_PROMPT_GL04_OPENCODE_R7.md and r7/PLAN_REVIEW.md. Do not reread full historical source/logs. Use summary and targeted current consumers. First actual ponytail read and complete r7/00_diag, then smallest source-provenance readout fix with original 54 assertions preserved, self-checks, accurate per-ID return/SHA and stop writing. Only two provenance FAIL are blocking; five exploratory grey-diagnostic hide assertions were rejected by Codex as outside frozen requirements. Keep grey diagnostics and bbox-only-negative actual raw center intact. No formal/core/driver/old-evidence/GL05/deploy/capture/board-network/commit/reset/model/DB changes.'
cmd=[r'C:\Users\30680\AppData\Roaming\npm\node_modules\opencode-ai\bin\opencode.exe','run','-m','opencode-go/deepseek-v4.1-flash','--format','json',msg]
if phase!='probe':cmd[2:2]=['--attach','http://127.0.0.1:18092','--session','ses_f01ba3f48ffepSrGKkcHrb3onk','--dir','D:/Code/ldiar']
t=time.monotonic();r={'start':datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),'phase':phase,'model':'opencode-go/deepseek-v4.1-flash','db':'default'}
with (out/(name+'.jsonl')).open('wb') as so,(out/(name+'.stderr.txt')).open('wb') as se:
    p=subprocess.Popen(cmd,cwd=root,stdout=so,stderr=se,creationflags=subprocess.CREATE_NO_WINDOW)
    try:r.update(exit=p.wait(timeout=55 if phase=='probe' else None),timed_out=False)
    except subprocess.TimeoutExpired:
        subprocess.run(['taskkill','/PID',str(p.pid),'/T','/F'],stdout=se,stderr=se);r.update(exit=p.wait(),timed_out=True)
r.update(end=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),elapsed_s=time.monotonic()-t,pid=p.pid)
(out/(name+'_meta.json')).write_text(json.dumps(r,indent=2),encoding='utf-8');print(json.dumps(r));sys.exit(1 if r['timed_out'] else r['exit'])
