"""New material audit after fixing project-root permission paths; retain failed run."""
import json,os,shlex,subprocess
from prepare import E,R,save,load
B='D:/APPS/Git/bin/bash.exe'
cfg=load(E/'opencode_readonly_config.json')
for s in load(E/'opencode_permissions.json')['files']:
    p=__import__('pathlib').Path(s)
    for form in [str(p.relative_to(R)),p.relative_to(R).as_posix()]:
        cfg['permission']['read'][form]='allow';cfg['agent']['cl209baudit']['permission']['read'][form]='allow'
save('opencode_readonly_config_02.json',cfg)
env=os.environ.copy();env['OPENCODE_CONFIG_CONTENT']=json.dumps(cfg);env['OPENCODE_DISABLE_AUTOUPDATE']='true'

def cli(label,command):
    argv=[B,'-c',command]
    with (E/(label+'.stdout')).open('xb') as out,(E/(label+'.stderr')).open('xb') as err:
        p=subprocess.run(argv,cwd=E,env=env,stdout=out,stderr=err)
    save(label+'_command.json',dict(argv=argv,cwd=str(E),exit_code=p.returncode))
    return p.returncode

assert cli('cli_effective_agent_02','opencode debug agent cl209baudit --pure')==0
a=load(E/'cli_effective_agent_02.stdout');assert a['tools']['read'] and not any(v for k,v in a['tools'].items() if k!='read')
prompt=(E/'opencode_prompt.txt').read_text(encoding='utf8')+'''\n权限说明：OpenCode发现的Git project root是D:/Code/ldiar，而cwd是本轮evidence；read匹配按project-relative，现已增加docs/sidequests/evidence/...形式白名单。必须用提示绝对filePath逐个单独read，不调用parallel工具。首轮所有读取失败，不能算实质审计；本轮是全新session，不延续其结论。若首个合法skill read仍拒绝，请立即环境BLOCKED停止。读成功则必须完成实质源码/证据独审，不停在计划。'''
(E/'opencode_prompt_02.txt').write_text(prompt,encoding='utf8')
code=cli('05_opencode_raw_output_02','opencode run --pure --agent cl209baudit --format json --model opencode-go/deepseek-v4.1-flash '+shlex.quote(prompt))
events=[]
for line in (E/'05_opencode_raw_output_02.stdout').read_text(encoding='utf8',errors='replace').splitlines():
    try:events.append(json.loads(line))
    except json.JSONDecodeError:pass
report='\n\n'.join(x.get('part',{}).get('text','') for x in events if x.get('type')=='text')
(E/'06_opencode_review_02.md').write_text(report,encoding='utf8')
sessions=sorted({x['sessionID'] for x in events if x.get('sessionID')})
save('opencode_completion_02.json',dict(exit_code=code,marker='AUDIT_COMPLETE' in report,session_ids=sessions,
    tool_events=[x['part'] for x in events if x.get('type')=='tool_use']))
if len(sessions)==1:
    cli('opencode_session_export_02','opencode export '+shlex.quote(sessions[0]))
    infos=[m['info'] for m in load(E/'opencode_session_export_02.stdout')['messages'] if m.get('info',{}).get('role')=='assistant']
    save('opencode_actual_model_02.json',dict(models=sorted({m.get('providerID','')+'/'+m.get('modelID','') for m in infos}),session=sessions[0],last_finish=infos[-1].get('finish'),CLI_version=(E/'cli_version.stdout').read_text().strip(),exit_code=code))
print('MATERIAL_AUDIT_EXIT',code,'REPORT_CHARS',len(report))
