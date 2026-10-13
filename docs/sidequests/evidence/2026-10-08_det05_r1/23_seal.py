"""DET-05 23 final seal: verify every artifact index entry and seal key evidence files. No execution."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


index = json.loads((HERE / '17_artifact_index.json').read_text(encoding='utf-8'))
for rec in index['files']:
    assert sha(ROOT / rec['path']) == rec['sha256'], rec['path']
seal = dict(status='SUBMITTED', accepted=False, index_entries_verified=len(index['files']),
            sha256=[dict(path=str(p.relative_to(ROOT)), sha256=sha(p)) for p in [
                HERE / '17_artifact_index.json', HERE / '22_acceptance_and_scope.json',
                HERE / '22_final_checks.log', HERE / '17_run_manifest.json', HERE / '18_integrity.json']],
            self_excluded='23_final_seal.json')
with (HERE / '23_final_seal.json').open('x', encoding='utf-8') as f:
    json.dump(seal, f, ensure_ascii=False, indent=2)
print('PASS: final seal; %d index entries verified' % len(index['files']))
