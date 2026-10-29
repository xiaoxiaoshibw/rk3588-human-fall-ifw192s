"""T8: prove the workspace outside this item is unchanged (binary, byte-exact baseline check)."""
import hashlib
import json
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import s3core as C


def check(rec):
    p = C.ROOT / rec['path']
    path = rec['path']
    if path == 'docs/human_fall/WORKFLOW.md':
        data = p.read_bytes()
        ok = hashlib.sha256(data[-rec['bytes']:]).hexdigest() == rec['sha256'] if rec.get('bytes') else False
        return dict(path=path, PASS=bool(ok), method='original suffix bytes (entry prepended)')
    if path == 'docs/human_fall/REVIEW_LOG.md':
        data = p.read_bytes()
        ok = hashlib.sha256(data[:rec['bytes']]).hexdigest() == rec['sha256'] if rec.get('bytes') else False
        return dict(path=path, PASS=bool(ok), method='original prefix bytes (entry appended)')
    kind = rec['kind']
    if kind == 'file':
        ok = p.is_file() and C.sha(p) == rec['sha256']
        return dict(path=path, PASS=bool(ok), method='full SHA256')
    if kind == 'symlink':
        ok = p.is_symlink() and str(p.readlink()) == rec['target']
        return dict(path=path, PASS=bool(ok), method='link target')
    ok = (not p.is_file()) and (not p.is_symlink())
    return dict(path=path, PASS=bool(ok), method='type (missing_or_nonfile)')


if __name__ == '__main__':
    t0 = time.time()
    recs = [json.loads(x) for x in (C.OUT / 'BASELINE_FILES.jsonl').read_text(encoding='utf8').splitlines()]
    with ThreadPoolExecutor(max_workers=12) as ex:
        results = list(ex.map(check, recs))
    changed = [dict(path=r['path'], method=r['method']) for r in results if not r['PASS']]
    base = C.load(C.OUT / 'BASELINE_GIT.json')
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=C.ROOT).decode().strip()
    branch = subprocess.check_output(['git', 'branch', '--show-current'], cwd=C.ROOT).decode().strip()
    data_now = {k: C.sha(C.SOURCE / n) for k, n in [('meta', 'meta.json'), ('points', 'points.bin')]}
    frozen = dict(meta=C.FROZEN['meta'], points=C.FROZEN['points'])
    source_files = {}
    for rel in ['docs/human_fall/evidence/2026-10-17_hfus_tcms_02_s02_r1/FINAL_SEAL.json',
                'data/leveled/61cb6976b0f8479394641850d9a7c6ca/tls/transform.json',
                'docs/human_fall/evidence/2026-10-17_hfus_tcms_02_s02_r1/full_r1/CANDIDATES.json',
                'docs/human_fall/evidence/2026-10-17_hfus_tcms_02_s02_r1/full_r1/VALIDATION.json']:
        source_files[rel] = C.sha(C.ROOT / rel)
    expected = {'docs/human_fall/evidence/2026-10-17_hfus_tcms_02_s02_r1/FINAL_SEAL.json': C.FROZEN['s2_seal'],
                'data/leveled/61cb6976b0f8479394641850d9a7c6ca/tls/transform.json': C.FROZEN['hist_sha'],
                'docs/human_fall/evidence/2026-10-17_hfus_tcms_02_s02_r1/full_r1/CANDIDATES.json': C.FROZEN['s2_candidates'],
                'docs/human_fall/evidence/2026-10-17_hfus_tcms_02_s02_r1/full_r1/VALIDATION.json': C.FROZEN['s2_validation']}
    C.write(C.OUT / 'PRESERVATION.json', dict(
        item=C.ITEM, baseline=dict(path='BASELINE_FILES.jsonl', records=len(recs),
                                   git_head=base['head'], git_branch=base['branch']),
        checked=len(results), changed=changed,
        git=dict(head_before=base['head'], head_now=head, branch_before=base['branch'], branch_now=branch,
                 unchanged=bool(head == base['head'] and branch == base['branch'])),
        source=dict(frozen=frozen, now=data_now, unchanged=bool(data_now == frozen)),
        frozen_assets=dict(now=source_files, expected=expected, unchanged=bool(source_files == expected)),
        workflow=dict(path='docs/human_fall/WORKFLOW.md', bytes=C.sha(C.ROOT / 'docs/human_fall/WORKFLOW.md'),
                      rule='original bytes must survive as the suffix'),
        review_log=dict(path='docs/human_fall/REVIEW_LOG.md', bytes=C.sha(C.ROOT / 'docs/human_fall/REVIEW_LOG.md'),
                        rule='original bytes must survive as the prefix'),
        method='binary byte comparison for 34,408 tracked+untracked files; data/ hashed separately, never written',
        seconds=time.time() - t0,
        PASS=bool(not changed and data_now == frozen and source_files == expected
                  and head == base['head'] and branch == base['branch'])))
    print(json.dumps(dict(checked=len(results), changed=len(changed), source_ok=data_now == frozen,
                          git_ok=head == base['head'], seconds=round(time.time() - t0, 1))))
