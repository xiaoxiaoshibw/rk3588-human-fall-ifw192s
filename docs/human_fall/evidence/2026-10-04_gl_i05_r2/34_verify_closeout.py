"""Final source freeze, ID statuses and immutable-review check after administrative closeout."""
import hashlib
import json
from pathlib import Path

OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[3]
manifest=json.loads((OUT/'research_01/11_submission_manifest.json').read_text(encoding='utf8'))
admin={'docs/human_fall/GLI05_ACCEPTANCE.md','docs/human_fall/GLI05_TASK.md','docs/human_fall/returns/GL-I05.md'}
differences=[p for p,h in manifest['files'].items()
    if hashlib.sha256((ROOT/p).read_bytes()).hexdigest()!=h]
assert set(differences)<=admin,differences
exe=json.loads((OUT/'opencode_second_review_02/execution_manifest.json').read_text(encoding='utf8'))
assert exe['checker_bytes_unchanged'] and exe['all_exit_zero'] and exe['start_sha']==exe['end_sha']
for name,h in exe['end_sha'].items():
    assert hashlib.sha256((OUT/'opencode_second_review_02'/name).read_bytes()).hexdigest()==h
events=[json.loads(line) for line in (OUT/'28_immutable_revalidation.jsonl').read_text(encoding='utf8').splitlines()]
mutations=[e['part'] for e in events if e['type']=='tool_use' and e['part']['tool'] in ('edit','write','apply_patch')]
assert len(mutations)==1 and mutations[0]['tool']=='write'
assert Path(mutations[0]['state']['input']['filePath']).name=='00_review.md'
statuses={}
for line in (ROOT/'docs/human_fall/GLI05_ACCEPTANCE.md').read_text(encoding='utf8').splitlines():
    if not line.startswith('| '):continue
    cells=line.split('|');key=cells[1].strip()
    if key in ('ID','行','---'):continue
    if key.startswith(('C0','E0','S0','B0','D0','Q0','Q10')):
        statuses[key]=cells[-2].strip()
software={'C01','C02','C03','C04','C05','C06','E01','E02','S01'}|{'Q%02d'%i for i in range(1,11)}
assert all(statuses[k].startswith('PASS') for k in software)
assert all(statuses[k].startswith('BLOCKED') for k in ('B01','B02'))
assert all(statuses[k].startswith('NOT_RUN') for k in ('D01','D02'))
result=dict(kind='gli05_final_closeout_verification',status='SOFTWARE_PASS_NOT_ACCEPTED',
    administrative_manifest_differences=differences,immutable_code_data_evidence_unchanged=True,
    checker_bytes_unchanged=True,review_only_report_written_once=True,acceptance_statuses=statuses,
    final_head=json.loads((OUT/'33_final_baseline.json').read_text(encoding='utf8'))['head'],
    final_cli=json.loads((OUT/'28_immutable_revalidation_meta.json').read_text(encoding='utf8')))
with (OUT/'34_verify.json').open('x',encoding='utf8') as f:json.dump(result,f,indent=2,ensure_ascii=False)
print(json.dumps(dict(status=result['status'],admin=differences,checker_bytes_unchanged=True,
                     source_unchanged=True,ids=len(statuses))))
