"""Finalize S2: source code SHAs, evidence manifest, independent seal."""
import hashlib
import json
import sys
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from bootstrap import OUT, ROOT, sha

CODE = ROOT / 'sidequests/hfus_tcms_02/realdev/r03'
EXCLUDE = {'MANIFEST.json', 'FINAL_SEAL.json', 'FINAL_SEAL.sha256'}

if __name__ == '__main__':
    files = sorted(p for p in CODE.iterdir() if p.is_file() and p.suffix in ('.py', '.js', '.html', '.md'))
    code = {p.name: dict(sha256=sha(p), bytes=p.stat().st_size) for p in files}
    (OUT / 'SOURCE_SHA.json').write_text(json.dumps(dict(root=str(CODE.relative_to(ROOT)), files=code), indent=2), encoding='utf8')
    manifest = {}
    total = 0
    for p in sorted(OUT.rglob('*')):
        if p.is_file() and p.name not in EXCLUDE:
            rel = str(p.relative_to(OUT)).replace('\\', '/')
            manifest[rel] = dict(sha256=sha(p), bytes=p.stat().st_size)
            total += p.stat().st_size
    (OUT / 'MANIFEST.json').write_text(json.dumps(dict(item='HFUS-TCMS-02-REALDEV-02-S02', files=manifest,
        count=len(manifest), total_bytes=total), indent=2), encoding='utf8')
    seal = dict(item='HFUS-TCMS-02-REALDEV-02-S02', status='SUBMITTED', sealed_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                acceptance_sha=sha(OUT / 'ACCEPTANCE_V1.md'), protocol_sha=sha(OUT / 'PROTOCOL_V4.json'),
                source=dict(meta='eeb336b895e2a147a09f23f9d69cdecb9490e020c2d91467e2ab5a84bd082ad4',
                            points='254c481fb4faad01f6d30d4630b471dcbc74a25985caba0949ea6d40705f84f1'),
                source_code_sha=sha(OUT / 'SOURCE_SHA.json'), manifest_sha=sha(OUT / 'MANIFEST.json'),
                manifest_files=len(manifest), output_bytes=total,
                workflow_sha=sha(ROOT / 'docs/human_fall/WORKFLOW.md'), review_log_sha=sha(ROOT / 'docs/human_fall/REVIEW_LOG.md'),
                return_sha=sha(ROOT / 'docs/human_fall/returns/HFUS-TCMS-02-REALDEV-02-S02.md'),
                note='seal excludes FINAL_SEAL.json/sha256 and MANIFEST.json to avoid self-reference')
    (OUT / 'FINAL_SEAL.json').write_text(json.dumps(seal, indent=2), encoding='utf8')
    (OUT / 'FINAL_SEAL.sha256').write_text(sha(OUT / 'FINAL_SEAL.json') + '  FINAL_SEAL.json\n', encoding='utf8')
    print(json.dumps(dict(files=len(manifest), bytes=total, seal=seal['manifest_sha'])))
