"""Read-only closure audit, including untracked inputs. Python -B -W error."""
from pathlib import Path
import hashlib,json

root=Path(__file__).resolve().parents[4]
here=Path(__file__).resolve().parent
before=json.loads((here/'00_baseline.json').read_text(encoding='utf-8-sig'))
changed=[]
for name,old in before['files'].items():
    if old.startswith('UNREADABLE:') or old=='MISSING_OR_SYMLINK': continue
    p=root/name
    if not p.is_file(): changed.append({'file':name,'before':old,'after':'MISSING'});continue
    h=hashlib.sha256()
    with p.open('rb') as stream:
        for block in iter(lambda:stream.read(1<<20),b''):h.update(block)
    if h.hexdigest()!=old:changed.append({'file':name,'before':old,'after':h.hexdigest()})
allowed={'docs/human_capture/README.md','docs/human_capture/returns/HR-W03.md'}
external={'pc_apps/console/README.txt'}  # Human-side date change observed during this turn; never edited here.
unexpected=[v for v in changed if v['file'] not in allowed|external and not v['file'].startswith('docs/human_capture/evidence/2026-10-07_hrw03_r38/')]
result={'baseline_files':len(before['files']),'changed':changed,'unexpected':unexpected,
        'allowed_docs':sorted(allowed),'external_preserved':sorted(external),
        'new_source_sha':{name:hashlib.sha256((root/'pc_apps/human_replay'/name).read_bytes()).hexdigest() for name in ['registration.js','registration_method.js','registration.test.js']}}
out=here/'07_scope_result.json'
with out.open('x',encoding='utf-8') as stream:json.dump(result,stream,ensure_ascii=False,indent=2)
print(json.dumps({'baseline_files':len(before['files']),'unexpected':unexpected},ensure_ascii=False))
raise SystemExit(bool(unexpected))
