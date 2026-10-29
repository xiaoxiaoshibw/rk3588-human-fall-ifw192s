"""Seal the S3 r2 follow-up (independent of the sealed r1 root)."""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'r04'))
import s3core as C

R1 = C.OUT
OUT = C.ROOT / 'docs/human_fall/evidence/2026-10-17_hfus_tcms_02_s03_r2'
REVIEW = C.ROOT / 'docs/human_fall/evidence/2026-10-17_hfus_tcms_02_s03_review_r1'
EXCLUDE = {'MANIFEST.json', 'FINAL_SEAL.json', 'FINAL_SEAL.sha256'}


def write(path, value):
    p = Path(path)
    with p.open('x', encoding='utf8', newline='\n') as f:
        json.dump(value, f, ensure_ascii=False, indent=2, allow_nan=False)


if __name__ == '__main__':
    files = {}
    for p in sorted(OUT.rglob('*')):
        if p.is_file():
            rel = str(p.relative_to(OUT)).replace('\\', '/')
            if rel in EXCLUDE:
                continue
            files[rel] = dict(sha256=C.sha(p), bytes=p.stat().st_size)
    write(OUT / 'MANIFEST.json', dict(item='HFUS-TCMS-02-REALDEV-02-S03', round='r2', files=files,
                                      count=len(files), output_bytes=sum(v['bytes'] for v in files.values()),
                                      note='excludes MANIFEST/FINAL_SEAL to avoid self-reference'))
    manifest_sha = C.sha(OUT / 'MANIFEST.json')
    src = Path(__file__).resolve().parent
    code = {p.name: C.sha(p) for p in sorted(src.iterdir()) if p.is_file()}
    seal = dict(item='HFUS-TCMS-02-REALDEV-02-S03', round='r2', status='SUBMITTED',
                sealed_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                parent_r1=dict(r1_seal='601a7a2429a83d60327487c07629534e1ee566d58ce14f4c628aea37164a927b',
                               untouched=bool(C.sha(R1 / 'FINAL_SEAL.json') == '601a7a2429a83d60327487c07629534e1ee566d58ce14f4c628aea37164a927b')),
                review=dict(item='HFUS-TCMS-02-REALDEV-02-S03-REVIEW-R1',
                            request_sha=C.sha(REVIEW / 'OPENCODE_REQUEST_R1.md'),
                            result_sha=C.sha(REVIEW / 'OPENCODE_R1.md'),
                            summary_sha=C.sha(REVIEW / 'REVIEW_SUMMARY.json')),
                findings_closed=['D1', 'D2', 'D3', 'D4'],
                browser_result_sha=C.sha(OUT / 'BROWSER/BROWSER_RESULTS_R2.json'),
                provenance_sha=C.sha(OUT / 'TRANSFORM_S2_PROVENANCE.json'),
                errata_sha=C.sha(OUT / 'ERRATA.md'),
                report_sha=C.sha(OUT / 'REPORT_R2.md'),
                source_code=code, source_code_sha=C.digest(code),
                manifest_sha=manifest_sha, manifest_files=len(files),
                note='r2 only closes review findings; the application chain was not re-run and no numeric result changed')
    write(OUT / 'FINAL_SEAL.json', seal)
    with (OUT / 'FINAL_SEAL.sha256').open('xb') as f:
        f.write(('%s  FINAL_SEAL.json\n' % C.sha(OUT / 'FINAL_SEAL.json')).encode('utf8'))
    print(json.dumps(dict(files=len(files), seal=C.sha(OUT / 'FINAL_SEAL.json'))))
