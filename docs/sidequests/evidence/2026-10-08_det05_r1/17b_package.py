"""DET-05 17b: refresh 17_run_manifest.json after the return gained its per-ID self-check table (missed in first packaging pass). No re-copy, no re-append of footers. No inference."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
CODE = ROOT / 'sidequests/human_detectors'


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


old = json.loads((HERE / '17_run_manifest.json').read_text(encoding='utf-8'))
assert old['report_sha256'] == sha(HERE / 'README.md')
assert old['acceptance_submission_sha256'] == sha(ROOT / 'docs/sidequests/DET05_ACCEPTANCE.md')
assert old['script_final_sha256'] == sha(CODE / 'det05.py')
for rec in old['code']:
    assert sha(ROOT / rec['path']) == rec['sha256'], rec['path']
new = dict(old)
new['return_sha256'] = sha(ROOT / 'docs/sidequests/returns/DET-05.md')
new['note'] = '17b refresh: return gained its per-ID self-check table after the first packaging pass; all other bound SHAs reverified; no other changes'
(HERE / '17_run_manifest.json').write_text(json.dumps(new, ensure_ascii=False, indent=2), encoding='utf-8')
print('PASS: 17b manifest refresh; return_sha256 updated; all other bound SHAs reverified; no inference')
