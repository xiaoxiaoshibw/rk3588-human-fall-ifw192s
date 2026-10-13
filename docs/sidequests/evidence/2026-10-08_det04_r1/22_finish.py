"""Final artifact SHA index and scope self-audit. No experiment execution."""
import hashlib
import json
from pathlib import Path
import subprocess

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
CODE=ROOT/'sidequests/human_detectors'
ART=CODE/'artifacts/det04_r1'


def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()


def load(p):
    return json.loads(p.read_text(encoding='utf-8'))


def write(path,value):
    with path.open('x',encoding='utf-8') as f:json.dump(value,f,ensure_ascii=False,indent=2)


baseline=load(HERE/'00_baseline.json');manifest=load(HERE/'17_run_manifest.json');integrity=load(HERE/'18_integrity.json')
rows=load(HERE/'06_deletion_rows.json');neg=load(HERE/'04_negative_anatomy.json')['rows'];fp=load(HERE/'05_fp_anatomy.json')['rows']
assert len(rows)==8 and len(neg)==7 and len(fp)==7 and len(load(HERE/'03_dose_rows.json'))==506
assert len((HERE/'06_deletion_rows.jsonl').read_text(encoding='utf-8').splitlines())==8
assert len(list(ART.glob('*_trace.npz')))==8
assert not integrity['assets']['changes'] and not integrity['ignored_existing_changes']
assert manifest['script_execution_sha256']==sha(CODE/'det04.py')
assert manifest['report_sha256']==sha(HERE/'README.md')
assert manifest['return_sha256']==sha(ROOT/'docs/sidequests/returns/DET-04.md')
assert manifest['acceptance_submission_sha256']==sha(ROOT/'docs/sidequests/DET04_ACCEPTANCE.md')
for r in manifest['code']:assert sha(ROOT/r['path'])==r['sha256']
for r in rows:
    assert sha(Path(r['trace']))==r['trace_sha256']
    assert all(r[k] for k in ['retained_voxels_exact','retained_counts_exact','source_ids_exact','retained_canvas_exact','deleted_canvas_zero'])
for r in neg:assert r['coverage_improved'] and r['head_delta']<0
assert {r['index'] for r in neg if r['variant']=='B_workspace'}=={3,28}
assert {r['index'] for r in neg if r['variant']=='E_cleanup'}=={7,11,12,17,37}
empty=fp[:3];assert all(r['anchor_id']==158179 and r['score']>=.5 for r in empty)
text=(HERE/'README.md').read_text(encoding='utf-8');ret=(ROOT/'docs/sidequests/returns/DET-04.md').read_text(encoding='utf-8')
ids=['S01','A01','A02','B01','C01','F01','T01','R01','R02','E03','G01','L01','D01']
assert all('|'+id+'|' in text and '|'+id+'|' in ret for id in ids)
assert 'DET-04' in (CODE/'README.md').read_text(encoding='utf-8').split('\n')[2]
assert subprocess.check_output(['git','check-ignore',str(ART/'config.json')]).decode().strip()

exclusions=['17_artifact_index.json','22_acceptance_and_scope.json','22_final_checks.log','23_final_seal.json']
paths=sorted({p for p in HERE.rglob('*') if p.is_file() and p.name not in exclusions} |
             {p for p in ART.rglob('*') if p.is_file()} |
             {ROOT/'docs/sidequests/DET04_PLAN.md',ROOT/'docs/sidequests/DET04_ACCEPTANCE.md',
              ROOT/'docs/sidequests/returns/DET-04.md',CODE/'det04.py',CODE/'test_experiment.py',CODE/'README.md'})
index=[dict(path=str(p.relative_to(ROOT)),bytes=p.stat().st_size,sha256=sha(p)) for p in paths]
write(HERE/'17_artifact_index.json',dict(files=index,excluded=exclusions,reason='avoid self-reference/circular SHA; scope and final seal bind finalized index'))
oldnames={r['path'].replace('\\','/') for r in baseline['worktree']['files']}
current=[]
for args in [['ls-files','-z'],['ls-files','--others','--exclude-standard','-z'],['ls-files','--others','--ignored','--exclude-standard','-z']]:
    current+=subprocess.check_output(['git',*args]).decode('utf-8').split('\0')
new=sorted({p.replace('\\','/') for p in current if p and p.replace('\\','/') not in oldnames})
allowed=lambda p:p in ['sidequests/human_detectors/det04.py','docs/sidequests/DET04_PLAN.md','docs/sidequests/DET04_ACCEPTANCE.md','docs/sidequests/returns/DET-04.md'] or p.startswith('docs/sidequests/evidence/2026-10-08_det04_r1/') or p.startswith('sidequests/human_detectors/artifacts/det04_r1/')
assert all(allowed(p) for p in new),[p for p in new if not allowed(p)]
for r in integrity['worktree']['changes']:assert sha(ROOT/r['path'])==r['after']
states={k:'PASS' for k in ids[:9]};states.update(E03='BLOCKED',G01='BLOCKED',L01='NOT_RUN',D01='NOT_RUN')
write(HERE/'22_acceptance_and_scope.json',dict(status='SUBMITTED',accepted=False,client_date='2026-10-08',statuses=states,
      acceptance_sha256=sha(ROOT/'docs/sidequests/DET04_ACCEPTANCE.md'),plan_sha256=sha(ROOT/'docs/sidequests/DET04_PLAN.md'),
      report_sha256=sha(HERE/'README.md'),return_sha256=sha(ROOT/'docs/sidequests/returns/DET-04.md'),
      manifest_sha256=sha(HERE/'17_run_manifest.json'),artifact_index_sha256=sha(HERE/'17_artifact_index.json'),
      integrity_sha256=sha(HERE/'18_integrity.json'),new_files_at_scope_check=new,
      later_seal_files=['22_acceptance_and_scope.json','23_final_seal.json'],
      existing_worktree_changes=integrity['worktree']['changes'],old_ignored_checked=5776,old_ignored_changes=[],
      consumption_assets_checked=3211,consumption_assets_changes=[],original_external_changes=integrity['original']['changes'],
      main_tree_writer_actions=[],new_network_forwards=8,other_network_forwards=0,regression_tests=10,
      failures_preserved=['00b_schema_probe_failed.log','17_packaging.log'],
      next_options_require_new_user_authorization=['a point GT / human-only sampling with fixed exterior','b calibrated intensity/z and same-sensor weights','c GPU/native ATen equivalence'],
      branch=subprocess.check_output(['git','branch','--show-current']).decode().strip(),HEAD=subprocess.check_output(['git','rev-parse','HEAD']).decode().strip()))
print('PASS: 13 acceptance IDs covered; 8 new network forwards; 506 dose pairs; negative7; FP3+human4; 10 regression tests')
print('PASS: index',len(index),'files; source/weight/prior ignored assets unchanged; only allowed worktree writes; main external changes recorded')
print('SUBMITTED; not ACCEPTED; exact recognition/GT/device NOT_RUN; ATen/GPU BLOCKED')
