"""Package completed evidence; no inference. UTF-8 explicit on Windows."""
import difflib
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

ROOT=Path(__file__).resolve().parents[4]
HERE=Path(__file__).resolve().parent
CODE=ROOT/'sidequests/human_detectors'
ART=CODE/'artifacts/det04_r1'


def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()


def read(path):
    return path.read_text(encoding='utf-8')


def write_json(path,value):
    with path.open('x',encoding='utf-8') as f:json.dump(value,f,ensure_ascii=False,indent=2)


config=json.loads(read(HERE/'02_config.json'))
integrity=json.loads(read(HERE/'18_integrity.json'))
assert not integrity['assets']['changes'] and not integrity['ignored_existing_changes']
acc=ROOT/'docs/sidequests/DET04_ACCEPTANCE.md'
initial=read(acc).split('\n\n## R1 最终作者自验')[0]
assert hashlib.sha256(initial.encode('utf-8')).hexdigest()==config['acceptance_sha256']
with (HERE/'02_acceptance_prerun.md').open('x',encoding='utf-8') as f:f.write(initial)
shutil.copy2(ROOT/'docs/sidequests/DET04_PLAN.md',HERE/'02_plan_prerun.md')
shutil.copy2(ART/'rows.jsonl',HERE/'06_deletion_rows.jsonl')
final=HERE/'code_final';final.mkdir(exist_ok=False)
for path in CODE.glob('*.py'):shutil.copy2(path,final/path.name)
shutil.copy2(CODE/'README.md',final/'README.md')
diff=[]
for path in sorted(list(CODE.glob('*.py'))+[CODE/'README.md']):
    before=HERE/'code_before'/path.name
    a=read(before).splitlines(keepends=True) if before.exists() else []
    diff.extend(difflib.unified_diff(a,read(path).splitlines(keepends=True),
                                   fromfile='baseline/'+path.name if before.exists() else '/dev/null',tofile='final/'+path.name))
with (HERE/'17_code_diff.patch').open('x',encoding='utf-8') as f:f.write(''.join(diff))
baseline=json.loads(read(HERE/'00_baseline.json'))
old=[r for r in baseline['worktree']['files'] if r['path'].replace('\\','/').startswith('sidequests/human_detectors/artifacts/')]
assert not any('outside_zero' in r['path'] for r in old)
write_json(HERE/'01b_artifact_inventory.json',dict(preexisting_artifact_files=len(old),
           directories=sorted({r['path'].replace('\\','/').split('/')[3] for r in old}),same_family_filename_matches=[],
           full_inventory_binding='00_baseline.json worktree ignored SHA list',rows_content_search='01_artifact_audit.json',
           det03_rows_jsonl_sha256=sha(ROOT/'docs/sidequests/evidence/2026-10-08_det03_r1/det03_all_r1_rows.jsonl')))

footer='''

## 最终完整性实录

18复核：原3211消费资产变化清单为空；已有5776忽略文件（含DET-03大数组/上游/旧资产）全部SHA不变。实验树10606基线项仅README/test_experiment.py两文件变化，本轮新文件见22清单。主树5190基线项观察到两份外部文档变化：docs/human_capture/FUSION_PRIORITY_RULE_DRAFT.md、docs/human_capture/HUMAN_RECOGNITION_REVIEW_AND_PLAN.md；本轮全部写入路径均在指定worktree，未写或回滚这两份文档，不能声称原树字节全未变。两树branch/HEAD均保持基线。

17首次打包因Windows默认gbk读取中文验收表而UnicodeDecodeError，exit1日志保留在17_packaging.log。17b显式UTF-8修复打包后通过，未重跑任何网络前向。config记录的是预运行验收SHA；02_acceptance_prerun.md验证该SHA并保留，最终追加自验的验收SHA另见17/22。
'''
for path in [HERE/'README.md',ROOT/'docs/sidequests/returns/DET-04.md']:
    with path.open('a',encoding='utf-8') as f:f.write(footer)

commands=[dict(log='08_regression.log',command='python -B -W error -m unittest discover -s sidequests/human_detectors -p test_experiment.py -v',exit_code=0),
          dict(log='09_experiment.log',command='python -B -W error sidequests/human_detectors/det04.py --out sidequests/human_detectors/artifacts/det04_r1',exit_code=0),
          dict(log='10_independent_checks.log',command='python -B -W error - (canonical voxels/counts/prepared IDs/raw rows/finite stored heads)',exit_code=0),
          dict(log='11_report.log',command='python -B -W error docs/sidequests/evidence/2026-10-08_det04_r1/11_report.py',exit_code=0),
          dict(log='18_integrity.log',command='python -B -W error - (current-baseline tracked/untracked/ignored SHA; same3211 asset list)',exit_code=0),
          dict(log='00b_schema_probe_failed.log',command='python -B -W error - (read schema, erroneous dict[0])',exit_code=1),
          dict(log='17_packaging.log',command='python -B -W error - (initial packaging, default gbk failed)',exit_code=1),
          dict(log='17b_packaging.log',command='python -B -W error docs/sidequests/evidence/2026-10-08_det04_r1/17_package.py',exit_code=0)]
manifest=dict(client_date='2026-10-08',writer='Codex only',skill='C:/Users/30680/.codex/skills/ponytail/SKILL.md',intensity='full',
              commands=commands,new_network_forwards=8,HB_HC_HD_network_forwards=0,regression_tests=10,
              code=[dict(path=str(p.relative_to(ROOT)),sha256=sha(p)) for p in sorted(CODE.glob('*.py'))],
              script_execution_sha256=config['script_sha256'],script_final_sha256=sha(CODE/'det04.py'),
              checkpoint_sha256=config['checkpoint_sha256'],plan_sha256=sha(ROOT/'docs/sidequests/DET04_PLAN.md'),
              acceptance_prerun_sha256=config['acceptance_sha256'],acceptance_submission_sha256=sha(acc),
              report_sha256=sha(HERE/'README.md'),return_sha256=sha(ROOT/'docs/sidequests/returns/DET-04.md'),
              consumed_assets_checked=3211,consumed_assets_changes=[],ignored_existing_checked=5776,ignored_existing_changes=[],
              additional_consumption='DET03 archived rows/config/trace/pillars and shared .py: current baseline SHA protected; new code/config/plan also bound here',
              original_external_changes=integrity['original']['changes'],integrity_sha256=sha(HERE/'18_integrity.json'),
              index_policy='17 index excludes itself/22 scope/23 seal/final-check and active packaging log to avoid cyclic or incomplete hashes')
assert manifest['script_execution_sha256']==manifest['script_final_sha256']
write_json(HERE/'17_run_manifest.json',manifest)
print('PASS: package with explicit UTF-8; code diff/prerun SHA/return/integrity manifest recorded; no inference')
