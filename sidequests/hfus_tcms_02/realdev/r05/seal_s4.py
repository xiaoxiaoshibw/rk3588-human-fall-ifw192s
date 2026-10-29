"""S4 seal: baseline preservation (byte-exact) + MANIFEST + FINAL_SEAL."""
import hashlib
import json
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import s4core as C

BASE = C.S3 / 'BASELINE_FILES.jsonl'
EXCLUDE = {'MANIFEST.json', 'FINAL_SEAL.json', 'FINAL_SEAL.sha256'}
RETURN = C.ROOT / 'docs/human_fall/returns/HFUS-TCMS-02-REALDEV-02-S04.md'


def check(rec):
    p = C.ROOT / rec['path']
    if rec['path'] == 'docs/human_fall/WORKFLOW.md':
        data = p.read_bytes()
        return dict(path=rec['path'], PASS=hashlib.sha256(data[-rec['bytes']:]).hexdigest() == rec['sha256'],
                    method='original suffix bytes')
    if rec['path'] == 'docs/human_fall/REVIEW_LOG.md':
        data = p.read_bytes()
        return dict(path=rec['path'], PASS=hashlib.sha256(data[:rec['bytes']]).hexdigest() == rec['sha256'],
                    method='original prefix bytes')
    if rec['kind'] == 'file':
        return dict(path=rec['path'], PASS=p.is_file() and C.sha(p) == rec['sha256'], method='full sha256')
    if rec['kind'] == 'symlink':
        return dict(path=rec['path'], PASS=p.is_symlink() and str(p.readlink()) == rec['target'], method='link')
    return dict(path=rec['path'], PASS=(not p.is_file() and not p.is_symlink()), method='type')


if __name__ == '__main__':
    t0 = time.time()
    recs = [json.loads(x) for x in BASE.read_text(encoding='utf8').splitlines()]
    with ThreadPoolExecutor(max_workers=12) as ex:
        results = list(ex.map(check, recs))
    changed = [dict(path=r['path'], method=r['method']) for r in results if not r['PASS']]
    data_now = {k: C.sha(C.SOURCE / n) for k, n in [('meta', 'meta.json'), ('points', 'points.bin')]}
    s3_inputs = {rel: C.sha(C.S3 / rel) for rel in
                 ['FINAL_SEAL.json', 'TRANSFORM/TRANSFORM_S3.json', 'DOMAINS/domains_s3.npz', 'M0/M0.json',
                  'TRANSFORM/TRANSFORM_QUALIFICATION.json', 'DOMAINS/S3_DOMAINS.json']}
    expected = {'FINAL_SEAL.json': '601a7a2429a83d60327487c07629534e1ee566d58ce14f4c628aea37164a927b',
                'TRANSFORM/TRANSFORM_S3.json': C.FROZEN['transform'],
                'DOMAINS/domains_s3.npz': C.FROZEN['domains_npz'],
                'M0/M0.json': C.FROZEN['m0'],
                'TRANSFORM/TRANSFORM_QUALIFICATION.json': C.FROZEN['qualification'],
                'DOMAINS/S3_DOMAINS.json': C.FROZEN['domains']}
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=C.ROOT).decode().strip()
    C.write(C.OUT / 'PRESERVATION.json', dict(
        item=C.ITEM, baseline=str(BASE.relative_to(C.ROOT)), records=len(recs), changed=changed,
        source=dict(now=data_now, unchanged=bool(data_now == dict(meta=C.FROZEN['meta'], points=C.FROZEN['points']))),
        s3_frozen=dict(now=s3_inputs, expected=expected, unchanged=bool(s3_inputs == expected)),
        git_head=head, workflow_sha=C.sha(C.ROOT / 'docs/human_fall/WORKFLOW.md'),
        review_log_sha=C.sha(C.ROOT / 'docs/human_fall/REVIEW_LOG.md'),
        method='byte comparison of the S3 T0 baseline; the WORKFLOW original bytes must remain the suffix and the '
               'REVIEW_LOG original bytes the prefix after two appended rounds',
        seconds=time.time() - t0,
        PASS=bool(not changed and data_now == dict(meta=C.FROZEN['meta'], points=C.FROZEN['points'])
                  and s3_inputs == expected)))
    files = {}
    for p in sorted(C.OUT.rglob('*')):
        if p.is_file():
            rel = str(p.relative_to(C.OUT)).replace('\\', '/')
            if rel in EXCLUDE:
                continue
            files[rel] = dict(sha256=C.sha(p), bytes=p.stat().st_size)
    src = Path(__file__).resolve().parent
    code = {p.name: C.sha(p) for p in sorted(src.iterdir()) if p.is_file()}
    C.write(C.OUT / 'MANIFEST.json', dict(item=C.ITEM, files=files, count=len(files),
                                          output_bytes=sum(v['bytes'] for v in files.values()),
                                          source_code=code, source_code_sha=C.digest(code),
                                          note='excludes MANIFEST/FINAL_SEAL to avoid self-reference'))
    seal = dict(item=C.ITEM, status='SUBMITTED', sealed_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                acceptance_sha=C.sha(C.OUT / 'ACCEPTANCE_V1.md'),
                protocol_sha=C.sha(C.OUT / 'PROTOCOL_V1.json'),
                report_sha=C.sha(C.OUT / 'REPORT.md'),
                tail_sha=C.sha(C.OUT / 'TAIL_DECOMPOSITION.json'),
                f430_sha=C.sha(C.OUT / 'F430_DECOMPOSITION.json'),
                abcd_sha=C.sha(C.OUT / 'ABCD.json'),
                contact_sha=C.sha(C.OUT / 'CONTACT_DEFINITION.json'),
                audit_sha=C.sha(C.OUT / 'DECOMPOSITION_AUDIT.json'),
                browser_sha=C.sha(C.OUT / 'BROWSER/BROWSER_RESULTS.json'),
                preservation_sha=C.sha(C.OUT / 'PRESERVATION.json'),
                document_append_sha=C.sha(C.OUT / 'DOCUMENT_APPEND.json'),
                inherited=dict(transform=C.FROZEN['transform_id'], m0=C.FROZEN['m0_map_id'],
                               s3_seal='601a7a2429a83d60327487c07629534e1ee566d58ce14f4c628aea37164a927b'),
                findings=dict(tail_zero_frames=[765, 767, 769, 770, 771, 772, 773, 774, 776, 777, 778, 779],
                              tail_contact_rows=325967, tail_contact_bg=325417,
                              root_cause='M0 background absorption of near-floor rows',
                              state='S4 diagnostic only; does not change GEOMETRY_VALIDATED_LOCAL'),
                source_code_sha=C.digest(code),
                manifest_sha=C.sha(C.OUT / 'MANIFEST.json'), manifest_files=len(files),
                return_sha=C.sha(RETURN) if RETURN.is_file() else None,
                item_state=dict(geometry='unchanged (S3 GEOMETRY_VALIDATED_LOCAL)', identity='BLOCKED',
                                physical='BLOCKED', human_effect='UNKNOWN', independent_D='BLOCKED',
                                s5='NOT_RUN', skeleton='NOT_RUN'),
                note='seal excludes itself and MANIFEST.json')
    C.write(C.OUT / 'FINAL_SEAL.json', seal)
    with (C.OUT / 'FINAL_SEAL.sha256').open('xb') as f:
        f.write(('%s  FINAL_SEAL.json\n' % C.sha(C.OUT / 'FINAL_SEAL.json')).encode('utf8'))
    print(json.dumps(dict(checked=len(recs), changed=len(changed), files=len(files),
                          seal=C.sha(C.OUT / 'FINAL_SEAL.json'))))
