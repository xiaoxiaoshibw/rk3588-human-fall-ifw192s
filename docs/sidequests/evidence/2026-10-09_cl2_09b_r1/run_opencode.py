"""Actual specified-model read-only review; process-local permissions only."""
import json,os,shlex,subprocess
from prepare import E,save,load
B='D:/APPS/Git/bin/bash.exe'

def cli(label,command,env=None):
    argv=[B,'-c',command]
    with (E/(label+'.stdout')).open('xb') as out,(E/(label+'.stderr')).open('xb') as err:
        p=subprocess.run(argv,cwd=E,env=env,stdout=out,stderr=err)
    save(label+'_command.json',dict(argv=argv,cwd=str(E),exit_code=p.returncode))
    return p.returncode

for label,command in [('cli_version','opencode --version'),('cli_help','opencode run --help'),('cli_models','opencode models opencode-go')]:
    assert cli(label,command)==0
assert 'opencode-go/deepseek-v4.1-flash' in (E/'cli_models.stdout').read_text(encoding='utf8')
assert load(E/'candidate_regression_05_command.json')['exit_code']==0
allowed=[E/n for n in ['PONYTAIL_SKILL.md','00_SCOPE_AND_ACCEPTANCE.md','02_fix.patch','03_session121647.json',
    '04_benchmark.json','test_selector.py','candidate_version.json','candidate_regression.stderr',
    'candidate_regression_02.stderr','candidate_regression_03.stderr','candidate_regression_04.stderr','candidate_regression_05.stderr','session_probe.py','benchmark.py']]
allowed+=[p for root in [E/'frozen',E/'candidate'] for p in root.rglob('*.py')]
read={'*':'deny'}
for p in allowed:
    for name in [str(p),p.as_posix(),str(p.relative_to(E)),p.relative_to(E).as_posix()]:read[name]='allow'
permission={'*':'deny','read':read,'external_directory':'deny'}
cfg={'permission':permission,'agent':{'cl209baudit':{'description':'Strict read-only CL2-09B candidate review',
    'mode':'primary','permission':permission,'prompt':'Use read only. Do not edit, execute, dispatch, access network or external paths. Inspect source and evidence; actively seek counterexamples. No physical or SHA execution claims.'}},'mcp':{},'plugin':[]}
save('opencode_readonly_config.json',cfg)
env=os.environ.copy();env['OPENCODE_CONFIG_CONTENT']=json.dumps(cfg);env['OPENCODE_DISABLE_AUTOUPDATE']='true'
assert cli('cli_effective_agent','opencode debug agent cl209baudit --pure',env)==0
agent=load(E/'cli_effective_agent.stdout');assert agent['tools']['read'] and not any(v for k,v in agent['tools'].items() if k!='read')
save('opencode_permissions.json',dict(tools=agent['tools'],files=[str(p) for p in allowed],scope='Only read, exact project-relative and absolute whitelist; CLI itself has normal runtime DB/log writes.'))
prompt='''你是CL2-09B独立只读审计员。实际指定模型opencode-go/deepseek-v4.1-flash。直接读取PONYTAIL_SKILL.md、唯一验收表、冻结及candidate源码、patch、test_selector、回归日志和session/benchmark证据。不得写文件、运行shell或派子任务；请只给报告。
逐B01–B08审计，主动找反例：原成功完整dict是否逐字保留？小/大候选失败后是否搜索所有可行四元组？叉积共线剪枝或数值/重复key会否误删合格组合？原间距/独立/条件门是否不变？调用者v2/v3/15cm行为范围与源码SHA版本是否诚实？原TLS/ROI121647是否保持BLOCKED？最坏O(n4)性能是否限制交付/生产接入？测试是否有覆盖漏洞？输入/历史完整性没有执行SHA时必须UNKNOWN。
本轮只交付隔离candidate，不接生产；原profile阈值不改；不能要求通过降门控或换ROI使121647放行。你没有执行数值，日志是作者执行证据，不冒称你重跑。报告全部FAIL/未知，给具体行/反例及范围内最小修复建议；没有FAIL也要写限制。完整中文报告，结束AUDIT_COMPLETE。
文件绝对路径（用read的filePath）:\n'''+ '\n'.join(p.as_posix() for p in allowed)
(E/'opencode_prompt.txt').write_text(prompt,encoding='utf8')
code=cli('05_opencode_raw_output','opencode run --pure --agent cl209baudit --format json --model opencode-go/deepseek-v4.1-flash '+shlex.quote(prompt),env)
events=[]
for line in (E/'05_opencode_raw_output.stdout').read_text(encoding='utf8',errors='replace').splitlines():
    try:events.append(json.loads(line))
    except json.JSONDecodeError:pass
report='\n\n'.join(x.get('part',{}).get('text','') for x in events if x.get('type')=='text')
(E/'06_opencode_review.md').write_text(report,encoding='utf8')
sessions=sorted({x['sessionID'] for x in events if x.get('sessionID')})
save('opencode_completion.json',dict(exit_code=code,marker='AUDIT_COMPLETE' in report,session_ids=sessions,
    tool_events=[x['part'] for x in events if x.get('type')=='tool_use']))
if len(sessions)==1:
    cli('opencode_session_export','opencode export '+shlex.quote(sessions[0]),env)
    x=load(E/'opencode_session_export.stdout');infos=[m['info'] for m in x['messages'] if m.get('info',{}).get('role')=='assistant']
    save('opencode_actual_model.json',dict(models=sorted({m.get('providerID','')+'/'+m.get('modelID','') for m in infos}),
        session=sessions[0],last_finish=infos[-1].get('finish'),CLI_version=(E/'cli_version.stdout').read_text().strip(),exit_code=code))
print('OPENCODE_EXIT',code,'REPORT_CHARS',len(report),flush=True)
