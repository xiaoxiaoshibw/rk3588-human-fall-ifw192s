"""Read-only continuation with actual commands/SHA/source and review-requested tests."""
import json,os,shlex,subprocess
from prepare import E,R,load,save
B='D:/APPS/Git/bin/bash.exe'
cfg=load(E/'opencode_readonly_config_02.json')
extra=[E/n for n in ['test_selector.py','run_tests.py','candidate_regression_06_command.json','candidate_regression_06.stderr',
 'candidate_regression_05_command.json','benchmark_no_feasible.py','04_benchmark_no_feasible.json','08_REVIEW_RESPONSE.md',
 '01_baseline.json','prepare.py','09_integrity.json','source_summary.json','snapshot_bindings.json','submission_manifest.json',
 'cli_version.stdout','cli_help.stdout','cli_models.stdout','cli_effective_agent_02.stdout','opencode_permissions.json',
 'opencode_actual_model_02.json','05_opencode_raw_output_02_command.json','extra_fixture_bindings.json','validation_fixture_binding.json',
 'input_snapshot/report.json','input_snapshot/meta.json','input_snapshot/manifest.json']]
for p in extra:
    for n in [str(p),p.as_posix(),str(p.relative_to(E)),p.relative_to(E).as_posix(),str(p.relative_to(R)),p.relative_to(R).as_posix()]:
        cfg['permission']['read'][n]='allow';cfg['agent']['cl209baudit']['permission']['read'][n]='allow'
save('opencode_readonly_config_03.json',cfg)
env=os.environ.copy();env['OPENCODE_CONFIG_CONTENT']=json.dumps(cfg);env['OPENCODE_DISABLE_AUTOUPDATE']='true'
sid=load(E/'opencode_actual_model_02.json')['session']
prompt='''补充审查请求：保持只读、同指定模型。先直接read 08_REVIEW_RESPONSE.md，再读新具名回归command/stderr、非共线无可行项benchmark/source、source_summary及必要原01/09、输入report/meta副本、CLI事实记录。它们原已存在但之前未进白名单的记录现已明确允许，不能以未读到推断不存在。
candidate生产源码/02_fix.patch没改；新增3个回归，35项具名全过，实际argv/PYTHONPATH/-W error/test及candidateSHA记录供你自行核查。新增无可行项完整枚举计数和SVD调用实测（含counter开销），不是绝对最坏时间上界。复核route边界说明、重复/并列测试是否解决原意见。
B07是实际CLI运行事实，由Codex session export与日志核验；你不需伪装执行SHA或证明自身。最终return/完整seal在你结束后追加，当前submission_manifest是前置闭合，不冒称最终seal已完成。
请给完整更新的B01–B08逐项报告，主动保留真正代码FAIL；仅文档/权限/作者执行未亲自复算的UNKNOWN与逻辑FAIL区分。最后AUDIT_COMPLETE。新可读绝对路径:\n'''+ '\n'.join(p.as_posix() for p in extra)
(E/'opencode_prompt_03.txt').write_text(prompt,encoding='utf8')
command='opencode run --pure --agent cl209baudit --format json --model opencode-go/deepseek-v4.1-flash --session '+shlex.quote(sid)+' '+shlex.quote(prompt)
argv=[B,'-c',command]
save('05_opencode_raw_output_03_command.json',dict(argv=argv,cwd=str(E),configuration='opencode_readonly_config_03.json'))
with (E/'05_opencode_raw_output_03.stdout').open('xb') as out,(E/'05_opencode_raw_output_03.stderr').open('xb') as err:
    p=subprocess.run(argv,cwd=E,env=env,stdout=out,stderr=err)
events=[]
for line in (E/'05_opencode_raw_output_03.stdout').read_text(encoding='utf8',errors='replace').splitlines():
    try:events.append(json.loads(line))
    except json.JSONDecodeError:pass
report='\n\n'.join(x.get('part',{}).get('text','') for x in events if x.get('type')=='text')
(E/'06_opencode_review_03.md').write_text(report,encoding='utf8')
save('opencode_completion_03.json',dict(exit_code=p.returncode,marker='AUDIT_COMPLETE' in report,session=sid,tool_events=[x['part'] for x in events if x.get('type')=='tool_use']))
with (E/'opencode_session_export_03.stdout').open('xb') as out,(E/'opencode_session_export_03.stderr').open('xb') as err:
    ex=subprocess.run([B,'-c','opencode export '+shlex.quote(sid)],cwd=E,env=env,stdout=out,stderr=err)
infos=[m['info'] for m in load(E/'opencode_session_export_03.stdout')['messages'] if m.get('info',{}).get('role')=='assistant']
save('opencode_actual_model_03.json',dict(models=sorted({m.get('providerID','')+'/'+m.get('modelID','') for m in infos}),session=sid,last_finish=infos[-1].get('finish'),exit_code=p.returncode,export_exit_code=ex.returncode,CLI_version=(E/'cli_version.stdout').read_text().strip()))
print('SUPPLEMENT_REVIEW_EXIT',p.returncode,'CHARS',len(report))
