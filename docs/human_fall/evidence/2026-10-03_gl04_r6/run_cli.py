import datetime, json, os, pathlib, subprocess, sys, time
root = pathlib.Path(__file__).resolve().parents[4]
out = pathlib.Path(__file__).parent
phase = sys.argv[1]
if 'OPENCODE_DB' in os.environ:
    raise SystemExit('OPENCODE_DB override present; no dispatch')
message = 'No tools or file changes. Reply only PROBE_OK.' if phase == 'probe' else 'Read docs/human_fall/AI_PROMPT_GL04_OPENCODE_R6.md and carry out that single in-scope R6 work item. First complete required design mapping and ponytail read; preserve all frozen paths. Finish by appending your return and stop writing.'
if phase == 'resume':
    message = 'Continue the SAME GL04 R6 session after verified official compaction, same model/default DB. Your 00_diag and partial lib.js edit are preserved. Do not reread full historical docs: use the summary, current 00_diag, and docs/human_fall/evidence/2026-10-03_gl04_r6/CODEX_CONTEXT_RECOVERY.md. First append diagnostic mappings for its C08/C14/C15 additional combinations, then finish the in-scope root-cause repairs, self-checks and SUBMITTED return. Preserve original 44/48 assertions and all frozen paths. Empty-candidate valid occluded source predictions keep grey diagnostic box/age with unknown current/fall; lost/ambiguous/unselected in BOTH modes reject stale current geometry; explicit negative actual-observation flags do not endorse physical fall; fixture plane offset must equal t[2] when normal=R[2]; wrong explicit source units cannot qualify current list/drag selection, legacy missing units stays supported. Record model/session/SHA/ponytail. Stop writing after submission.'
name = '01_service_probe' if phase == 'probe' else '03_opencode'
if len(sys.argv) > 2:
    name = sys.argv[2]
if any((out / (name + suffix)).exists() for suffix in ('.jsonl','.stderr.txt','_meta.json')):
    raise SystemExit('Evidence output already exists; choose a new log prefix')
cmd = [r'C:\Users\30680\AppData\Roaming\npm\node_modules\opencode-ai\bin\opencode.exe','run','-m','opencode-go/deepseek-v4.1-flash','--format','json',message]
if phase == 'resume':
    cmd[2:2] = ['--attach','http://127.0.0.1:18092','--session','ses_f01ba3f48ffepSrGKkcHrb3onk','--dir','D:/Code/ldiar']
start = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat()
t = time.monotonic()
with (out / (name+'.jsonl')).open('wb') as stdout, (out / (name+'.stderr.txt')).open('wb') as stderr:
    p = subprocess.Popen(cmd,cwd=root,stdout=stdout,stderr=stderr,creationflags=subprocess.CREATE_NO_WINDOW)
    timed_out=False
    try: code=p.wait(timeout=55 if phase=='probe' else None)
    except subprocess.TimeoutExpired:
        timed_out=True
        subprocess.run(['taskkill','/PID',str(p.pid),'/T','/F'],stdout=stderr,stderr=stderr)
        code=p.wait()
meta={'phase':phase,'start':start,'end':datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),'elapsed_s':time.monotonic()-t,'exit':code,'timed_out':timed_out,'model':'opencode-go/deepseek-v4.1-flash','db':'default','pid':p.pid}
(out/(name+'_meta.json')).write_text(json.dumps(meta,indent=2),encoding='utf-8')
print(json.dumps(meta))
sys.exit(1 if timed_out else code)
