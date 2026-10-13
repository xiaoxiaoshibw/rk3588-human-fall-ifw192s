"""Short prompt retry, preserve first failed CLI attempt and all original files."""
import json
import os
import shlex
import subprocess
from prepare import E,load,save

SHELL='D:/APPS/Git/bin/bash.exe'
cfg=load(E/'opencode_readonly_config.json')
env=os.environ.copy();env['OPENCODE_CONFIG_CONTENT']=json.dumps(cfg);env['OPENCODE_DISABLE_AUTOUPDATE']='true'
prompt=f'''CL2-10 独立只读审计。工作证据根 {E.as_posix()}。
先read根下PONYTAIL_SKILL.md、00_SCOPE_AND_ACCEPTANCE.md、00_EXPERIMENT_PLAN.md、01_root_cause.md、04_audit_summary.json、04_source_summary.json。
然后read diagnostics.py、cross_checks.py、test_diagnostics.py、03_regression_results.txt，并对照 candidate/leveling_quality.py、candidate/leveling_estimators/tls.py 和 inputs/cap_20261009_121647/report.json。需要原始数值时read 02_shadow_ab_results.json、01_reproduction.json、04_audit_numeric_bundle.json；可以按offset/limit分段。每个filePath使用上述证据根绝对前缀；它们均在原严格read白名单。
作者当前BLOCKED：无真实物理根因证据，无CL2-10修复；candidate只是冻结09C源，未接生产。请主动反驳：因果过强、FIT/holdout泄漏、局部多平面冒称刚体TLS、阈值/样本/ROI隐改、目标过拟合、ROI等权隐藏144失败、刚体控制被误当真实外参正确、跨capture误当GT、已有成功回归遗漏。
逐T100–T111/TLS01/E01/D01评审，有逻辑FAIL给反例/行/最小修复；未亲自运行数值/SHA标UNKNOWN，不能伪造执行。检查整体是否仍应BLOCKED及是否具备算法修复资格。最终return/manifest在独审后封存，目前仅前置guard。先前CLI因shell引号错误exit2、未进模型，失败IO保留；此为新实际会话。结尾AUDIT_COMPLETE。
'''
(E/'opencode_prompt_02.txt').write_text(prompt,encoding='utf8')
argv=[SHELL,'-c','opencode run --pure --agent cl210audit --format json --model opencode-go/deepseek-v4.1-flash '+shlex.quote(prompt)]
with (E/'04_opencode_raw_02.stdout').open('xb') as out,(E/'04_opencode_raw_02.stderr').open('xb') as err:
    process=subprocess.run(argv,cwd=E,env=env,stdout=out,stderr=err)
save('04_opencode_raw_02_command.json',dict(argv=argv,cwd=str(E),exit_code=process.returncode,
     permissions_unchanged=True,configuration='opencode_readonly_config.json'))
events=[]
for line in (E/'04_opencode_raw_02.stdout').read_text(encoding='utf8',errors='replace').splitlines():
    try:events.append(json.loads(line))
    except json.JSONDecodeError:pass
report='\n\n'.join(x.get('part',{}).get('text','') for x in events if x.get('type')=='text')
(E/'04_independent_review_02.md').write_text(report,encoding='utf8')
sessions=sorted({x['sessionID'] for x in events if x.get('sessionID')})
save('opencode_completion_02.json',dict(exit_code=process.returncode,marker='AUDIT_COMPLETE' in report,
     session_ids=sessions,tool_events=[x['part'] for x in events if x.get('type')=='tool_use']))
if len(sessions)==1:
    export_argv=[SHELL,'-c','opencode export '+shlex.quote(sessions[0])]
    with (E/'opencode_session_export_02.stdout').open('xb') as out,(E/'opencode_session_export_02.stderr').open('xb') as err:
        ex=subprocess.run(export_argv,cwd=E,env=env,stdout=out,stderr=err)
    save('opencode_session_export_02_command.json',dict(argv=export_argv,cwd=str(E),exit_code=ex.returncode))
    infos=[x['info'] for x in load(E/'opencode_session_export_02.stdout')['messages'] if x.get('info',{}).get('role')=='assistant']
    save('opencode_actual_model_02.json',dict(models=sorted({m.get('providerID','')+'/'+m.get('modelID','') for m in infos}),
      session=sessions[0],last_finish=infos[-1].get('finish'),exit_code=process.returncode,export_exit_code=ex.returncode,
      CLI_version=(E/'cli_version.stdout').read_text().strip()))
print('ACTUAL_AUDIT_RETRY_EXIT',process.returncode,'REPORT_CHARS',len(report),flush=True)
