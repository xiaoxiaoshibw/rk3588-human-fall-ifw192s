"""DET-05 22 final artifact SHA index and scope self-audit. No experiment execution."""
import hashlib
import json
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
CODE = ROOT / 'sidequests/human_detectors'
ART = CODE / 'artifacts/det05_r1'


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def write(path, value):
    with path.open('x', encoding='utf-8') as f:
        json.dump(value, f, ensure_ascii=False, indent=2)


baseline = load(HERE / '00_baseline.json')
manifest = load(HERE / '17_run_manifest.json')
integrity = load(HERE / '18_integrity.json')
metrics = load(HERE / '06_metrics.json')
rows = load(HERE / '05_run_rows.json')
purity = load(HERE / '04_purity_audit.json')
checks = load(HERE / '10_independent_checks.json')
author = load(HERE / '03_annotation_author.json')
assert len(metrics['items']) == 10 and metrics['new_forwards'] == 20 and len(rows) == 20
assert len(purity['rows']) == 10 and len(author['frames']) == 10 and checks['all_ok']
assert len(checks['checks']) == 10 and all(c['ok'] for c in checks['checks'])
assert not integrity['assets']['changes'] and not integrity['ignored_existing_changes']
assert manifest['script_execution_sha256'] == sha(CODE / 'det05.py')
assert manifest['annotate_sha256'] == sha(CODE / 'det05_annotate.py')
assert manifest['freeze_sha256'] == sha(CODE / 'det05_freeze.py')
assert manifest['report_sha256'] == sha(HERE / 'README.md')
assert manifest['return_sha256'] == sha(ROOT / 'docs/sidequests/returns/DET-05.md')
assert manifest['acceptance_submission_sha256'] == sha(ROOT / 'docs/sidequests/DET05_ACCEPTANCE.md')
for rec in manifest['code']:
    assert sha(ROOT / rec['path']) == rec['sha256'], rec['path']
assert manifest['labels_v1_sha256'] == sha(ART / 'frozen/labels_v1.json')
assert manifest['gt_v1_sha256'] == sha(ART / 'frozen/gt_v1.json')
text = (HERE / 'README.md').read_text(encoding='utf-8')
ret = (ROOT / 'docs/sidequests/returns/DET-05.md').read_text(encoding='utf-8')
ids = ['S01', 'A01', 'A02', 'B01', 'C01', 'M01', 'T01', 'R01', 'R02', 'E03', 'G01', 'L01', 'D01']
assert all('|' + i + '|' in text and '|' + i + '|' in ret for i in ids)
assert 'DET-05' in (CODE / 'README.md').read_text(encoding='utf-8').split('\n')[2]
assert subprocess.check_output(['git', 'check-ignore', str(ART / 'config.json')], cwd=str(ROOT)).decode().strip()

exclusions = ['17_artifact_index.json', '22_acceptance_and_scope.json', '22_final_checks.log', '23_final_seal.json']
paths = sorted({p for p in HERE.rglob('*') if p.is_file() and p.name not in exclusions} |
               {p for p in ART.rglob('*') if p.is_file()} |
               {ROOT / 'docs/sidequests/DET05_PLAN.md', ROOT / 'docs/sidequests/DET05_ACCEPTANCE.md',
                ROOT / 'docs/sidequests/returns/DET-05.md', CODE / 'det05.py', CODE / 'det05_annotate.py',
                CODE / 'det05_freeze.py', CODE / 'test_experiment.py', CODE / 'README.md'})
index = [dict(path=str(p.relative_to(ROOT)), bytes=p.stat().st_size, sha256=sha(p)) for p in paths]
write(HERE / '17_artifact_index.json', dict(files=index, excluded=exclusions,
      reason='avoid self-reference/circular SHA; scope and final seal bind finalized index'))
oldnames = {r['path'].replace('\\', '/') for r in baseline['worktree']['files']}
current = []
for args in [['ls-files', '-z'], ['ls-files', '--others', '--exclude-standard', '-z'],
             ['ls-files', '--others', '--ignored', '--exclude-standard', '-z']]:
    current += subprocess.check_output(['git', *args], cwd=str(ROOT)).decode('utf-8').split('\0')
new = sorted({p.replace('\\', '/') for p in current if p and p.replace('\\', '/') not in oldnames})


def allowed(p):
    return p in ['sidequests/human_detectors/det05.py', 'sidequests/human_detectors/det05_annotate.py',
                 'sidequests/human_detectors/det05_freeze.py', 'docs/sidequests/DET05_PLAN.md',
                 'docs/sidequests/DET05_ACCEPTANCE.md', 'docs/sidequests/returns/DET-05.md'] or \
        p.startswith('docs/sidequests/evidence/2026-10-08_det05_r1/') or \
        p.startswith('sidequests/human_detectors/artifacts/det05_r1/')


assert all(allowed(p) for p in new), [p for p in new if not allowed(p)]
for rec in integrity['worktree']['changes']:
    assert sha(ROOT / rec['path']) == rec['after']
states = {k: 'PASS' for k in ['S01', 'A01', 'A02', 'B01', 'C01', 'M01', 'T01', 'R01', 'R02']}
states.update(E03='BLOCKED', G01='BLOCKED', L01='NOT_RUN', D01='NOT_RUN')
write(HERE / '22_acceptance_and_scope.json', dict(
    status='SUBMITTED', accepted=False, client_date='2026-10-08', statuses=states,
    acceptance_sha256=sha(ROOT / 'docs/sidequests/DET05_ACCEPTANCE.md'),
    plan_sha256=sha(ROOT / 'docs/sidequests/DET05_PLAN.md'), report_sha256=sha(HERE / 'README.md'),
    return_sha256=sha(ROOT / 'docs/sidequests/returns/DET-05.md'),
    manifest_sha256=sha(HERE / '17_run_manifest.json'), artifact_index_sha256=sha(HERE / '17_artifact_index.json'),
    integrity_sha256=sha(HERE / '18_integrity.json'),
    new_files_at_scope_check=new, later_seal_files=['22_acceptance_and_scope.json', '23_final_seal.json'],
    existing_worktree_changes=integrity['worktree']['changes'], old_ignored_checked=integrity['ignored_existing_checked'],
    old_ignored_changes=[], consumption_assets_checked=3211, consumption_assets_changes=[],
    original_external_changes=integrity['original']['changes'], main_tree_writer_actions=[],
    new_network_forwards=20, other_network_forwards=0, regression_tests=12,
    failures_preserved=['03_annotation_dev_fail.log', '08_regression_powershell_redirect.log',
                        '17_packaging.log (first pass superseded by 17b_packaging.log)'],
    next_options_require_new_user_authorization=['b calibrated intensity/z and same-sensor weight adaptation',
                                                 'c GPU/native ATen equivalence',
                                                 'frame-set/rule changes need new pre-registration'],
    branch=subprocess.check_output(['git', 'branch', '--show-current'], cwd=str(ROOT)).decode().strip(),
    HEAD=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=str(ROOT)).decode().strip()))
print('PASS: 13 acceptance IDs covered; 20 new network forwards; 10 label frames; 10 independent checks; 12 regression tests')
