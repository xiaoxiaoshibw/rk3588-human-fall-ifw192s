import hashlib
import json
from pathlib import Path

OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[3]
before=json.loads((OUT/'00_before_baseline.json').read_text(encoding='utf8'))
after=json.loads((OUT/'19_final_baseline.json').read_text(encoding='utf8'))
allowed={'docs/human_fall/'+name for name in ('README.md','DISPATCH.md','WORKFLOW.md',
    'REVIEW_LOG.md','CLI_RECOVERY.md','GLE01_ACCEPTANCE.md','returns/GL-E01.md')}
prefix=OUT.relative_to(ROOT).as_posix()+'/'
changed=[p for p,v in before['files'].items() if after['files'].get(p)!=v]
unexpected=[p for p in changed if not p.startswith(prefix) and p not in allowed]
new=[p for p in after['files'] if p not in before['files']]
unexpected_new=[p for p in new if not p.startswith(prefix) and p not in allowed]
assert before['head']==after['head'] and not unexpected and not unexpected_new,(unexpected,unexpected_new)
manifest=json.loads((OUT/'09_submission_manifest.json').read_text(encoding='utf8'))
diff=[p for p,h in manifest['files'].items()
      if hashlib.sha256((ROOT/p).read_bytes()).hexdigest()!=h]
assert set(diff)<= {'docs/human_fall/GLE01_ACCEPTANCE.md','docs/human_fall/returns/GL-E01.md'},diff
events=[json.loads(line) for line in (OUT/'13_second_review.jsonl').read_text(encoding='utf8').splitlines()]
edits=[e['part']['state'].get('input',{}) for e in events if e['type']=='tool_use' and e['part']['tool']=='edit']
assert not edits,'review immutable script instruction was violated'
statuses={}
for line in (ROOT/'docs/human_fall/GLE01_ACCEPTANCE.md').read_text(encoding='utf8').splitlines():
    if line.startswith('| '):
        cells=line.split('|');key=cells[1].strip()
        if key.startswith(('A0','S0','B0','D0','Q0')):statuses[key]=cells[-2].strip()
assert all(statuses[k].startswith('PASS') for k in ['A01','A02','A03','A04','A05','S01','B01']+['Q%02d'%i for i in range(1,7)])
assert statuses['B02']=='BLOCKED' and statuses['D01']=='NOT_RUN' and statuses['D02']=='BLOCKED'
result=dict(kind='gle01_final_verify',status='SOURCE_CHAIN_PASS_PHYSICAL_BLOCKED',
    head=after['head'],administrative_changes=changed,unexpected_changes=unexpected,
    unexpected_new=unexpected_new,manifest_administrative_differences=diff,
    production_input_old_evidence_unchanged=True,review_checker_edits=edits,
    acceptance_statuses=statuses,cli=json.loads((OUT/'13_second_review_meta.json').read_text(encoding='utf8')))
with (OUT/'19_final_verify.json').open('x',encoding='utf8') as f:json.dump(result,f,indent=2,ensure_ascii=False)
print(json.dumps(dict(status=result['status'],unexpected=unexpected,ids=len(statuses),
                     old_assets_unchanged=True)))
