"""DET-05 17 packaging: UTF-8 explicit; prerun copies, code snapshots/diff, manifest; no inference."""
import difflib
import hashlib
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
CODE = ROOT / 'sidequests/human_detectors'
ART = CODE / 'artifacts/det05_r1'
DET04_CODE = ROOT / 'docs/sidequests/evidence/2026-10-08_det04_r1/code_final'


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def read(path):
    return path.read_text(encoding='utf-8')


def write_json(path, value):
    with path.open('x', encoding='utf-8') as f:
        json.dump(value, f, ensure_ascii=False, indent=2)


config = json.loads(read(HERE / '02_config.json'))
integrity = json.loads(read(HERE / '18_integrity.json'))
assert not integrity['assets']['changes'] and not integrity['ignored_existing_changes']
acc = ROOT / 'docs/sidequests/DET05_ACCEPTANCE.md'
initial = read(acc).split('\n\n## R1 最终作者自验')[0]
assert hashlib.sha256(initial.encode('utf-8')).hexdigest() == config['acceptance_sha256']
with (HERE / '02_acceptance_prerun.md').open('x', encoding='utf-8') as f:
    f.write(initial)
shutil.copy2(ROOT / 'docs/sidequests/DET05_PLAN.md', HERE / '02_plan_prerun.md')

final = HERE / 'code_final'
final.mkdir(exist_ok=False)
for path in CODE.glob('*.py'):
    shutil.copy2(path, final / path.name)
shutil.copy2(CODE / 'README.md', final / 'README.md')
before = HERE / 'code_before'
before.mkdir(exist_ok=False)
for path in sorted(DET04_CODE.iterdir()):
    if path.is_file():
        shutil.copy2(path, before / path.name)
diff = []
for path in sorted(list(CODE.glob('*.py')) + [CODE / 'README.md']):
    old = before / path.name
    a = read(old).splitlines(keepends=True) if old.exists() else []
    diff.extend(difflib.unified_diff(a, read(path).splitlines(keepends=True),
                                     fromfile='baseline/' + path.name if old.exists() else '/dev/null',
                                     tofile='final/' + path.name))
with (HERE / '17_code_diff.patch').open('x', encoding='utf-8') as f:
    f.write(''.join(diff))

baseline = json.loads(read(HERE / '00_baseline.json'))
old_art = [r for r in baseline['worktree']['files'] if r['path'].replace('\\', '/').startswith('sidequests/human_detectors/artifacts/')]
assert not any('det05' in r['path'] for r in old_art)
write_json(HERE / '01b_artifact_inventory.json', dict(
    preexisting_artifact_files=len(old_art),
    directories=sorted({r['path'].replace('\\', '/').split('/')[3] for r in old_art}),
    same_family_filename_matches=[], full_inventory_binding='00_baseline.json worktree ignored SHA list',
    det05_new_files=integrity['worktree']['new_files']))

wt_changes = [(c['path'], c['before'][:8] + '->' + (c['after'] or 'missing')[:8]) for c in integrity['worktree']['changes']]
footer = '''

## 最终完整性实录

18复核：原3211消费资产变化清单为空；已有 %d 个基线忽略文件（含 DET-03/04 大数组/上游/旧资产）全部SHA不变。实验树 %d 基线项中既有文件变化仅 %s，本轮新文件 %d 项见22清单。主树 %d 基线项变化清单为空（本轮未写主树）。两树branch/HEAD均保持基线。

17记录：02预运行副本/代码前后快照与diff/17 manifest/逐文件SHA索引；03标注首跑相对路径bug失败保留（03_annotation_dev_fail.log），修复后重跑通过；08回归、09实验（20前向）、10独立检查、18完整性均 exit0。
''' % (integrity['ignored_existing_checked'], integrity['worktree']['checked'], wt_changes,
       integrity['worktree']['new_files'], integrity['original']['checked'])
for path in [HERE / 'README.md', ROOT / 'docs/sidequests/returns/DET-05.md']:
    with path.open('a', encoding='utf-8') as f:
        f.write(footer)

commands = [dict(log='00_baseline.log', command='python -B -W error docs/sidequests/evidence/2026-10-08_det05_r1/00_baseline.py', exit_code=0),
            dict(log='03_annotation_run.log', command='python -B -W error sidequests/human_detectors/det05_annotate.py --out sidequests/human_detectors/artifacts/det05_r1/annotate --evidence docs/sidequests/evidence/2026-10-08_det05_r1', exit_code=0),
            dict(log='03_annotation_dev_fail.log', command='python -B -W error sidequests/human_detectors/det05_annotate.py (first run; relative-to bug)', exit_code=1),
            dict(log='03c_freeze.json', command='python -B -W error sidequests/human_detectors/det05_freeze.py --out sidequests/human_detectors/artifacts/det05_r1/frozen --evidence docs/sidequests/evidence/2026-10-08_det05_r1 --confirm-file <utf8 file>', exit_code=0),
            dict(log='08_regression.log', command='python -B -W error -m unittest discover -s sidequests/human_detectors -p test_experiment.py -v', exit_code=0),
            dict(log='09_experiment.log', command='python -B -W error sidequests/human_detectors/det05.py --out sidequests/human_detectors/artifacts/det05_r1/runs --evidence docs/sidequests/evidence/2026-10-08_det05_r1', exit_code=0),
            dict(log='10_independent_checks.log', command='python -B -W error docs/sidequests/evidence/2026-10-08_det05_r1/10_independent_checks.py', exit_code=0),
            dict(log='18_integrity.log', command='python -B -W error docs/sidequests/evidence/2026-10-08_det05_r1/18_integrity.py', exit_code=0),
            dict(log='17_packaging.log', command='python -B -W error docs/sidequests/evidence/2026-10-08_det05_r1/17_package.py', exit_code=0)]
src = config['source_hashes']
labels_sha = next(v for k, v in src.items() if k.replace('\\', '/').endswith('frozen/labels_v1.json'))
gt_sha = next(v for k, v in src.items() if k.replace('\\', '/').endswith('frozen/gt_v1.json'))
manifest = dict(client_date='2026-10-08', writer='OpenCode only (opencode-go/deepseek-v4.1-flash)',
                skill='opencode skill tool (id=ponytail, intensity=full); base C:/Users/30680/.config/opencode/skills/ponytail; SKILL.md verified',
                commands=commands, new_network_forwards=20, regression_tests=12,
                code=[dict(path=str(p.relative_to(ROOT)), sha256=sha(p)) for p in sorted(list(CODE.glob('*.py')) + [CODE / 'README.md'])],
                script_execution_sha256=config['script_sha256'], script_final_sha256=sha(CODE / 'det05.py'),
                annotate_sha256=config['shared_sha256']['det05_annotate.py'], freeze_sha256=config['shared_sha256']['det05_freeze.py'],
                checkpoint_sha256=config['checkpoint_sha256'], plan_sha256=sha(ROOT / 'docs/sidequests/DET05_PLAN.md'),
                acceptance_prerun_sha256=config['acceptance_sha256'], acceptance_submission_sha256=sha(acc),
                labels_v1_sha256=labels_sha,
                gt_v1_sha256=gt_sha,
                report_sha256=sha(HERE / 'README.md'), return_sha256=sha(ROOT / 'docs/sidequests/returns/DET-05.md'),
                consumed_assets_checked=3211, consumed_assets_changes=[],
                ignored_existing_checked=integrity['ignored_existing_checked'], ignored_existing_changes=[],
                additional_consumption='DET03/04 archived rows/traces/pillars, FG/PRE inputs, seed: protected by 00 baseline; new det05 code/config/plan/frozen bound here',
                original_external_changes=integrity['original']['changes'], integrity_sha256=sha(HERE / '18_integrity.json'),
                index_policy='17 index excludes itself/22 scope/final-check and active packaging log to avoid cyclic or incomplete hashes')
assert manifest['script_execution_sha256'] == manifest['script_final_sha256']
write_json(HERE / '17_run_manifest.json', manifest)
print('PASS: package with explicit UTF-8; prerun copies/diff/snapshots/manifest recorded; no inference')
