"""Compare all pre-existing regular files against the before snapshot."""
import json
from pathlib import Path
from run import ROOT, EVIDENCE, sha, dump

baseline = json.loads((EVIDENCE/'BASELINE_BEFORE.json').read_text(encoding='utf-8'))
changed, missing, errors = [], [], []
for i, (name, record) in enumerate(baseline['files'].items()):
    path = ROOT/name
    if not path.exists():
        missing.append(name)
        continue
    try:
        now = sha(path)
        if now != record['sha256']:
            changed.append({'path': name, 'before': record['sha256'], 'after': now})
    except OSError as exc:
        errors.append({'path': name, 'error': str(exc)})
    if i % 2000 == 0:
        print('verify', i, len(baseline['files']), flush=True)
dump(EVIDENCE/'PREEXISTING_FILES_AFTER.json', {'baseline_files': len(baseline['files']), 'changed': changed,
                                             'missing': missing, 'errors': errors,
                                             'note': 'Any drift outside this item is reported, never reset or overwritten.'})
print('Asset comparison finished', len(changed), len(missing), len(errors), flush=True)
