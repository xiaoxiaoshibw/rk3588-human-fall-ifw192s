"""T8: MANIFEST + FINAL_SEAL (excludes itself to avoid self-reference)."""
import hashlib
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import s3core as C

EXCLUDE = {'MANIFEST.json', 'FINAL_SEAL.json', 'FINAL_SEAL.sha256'}
RETURN = C.ROOT / 'docs/human_fall/returns/HFUS-TCMS-02-REALDEV-02-S03.md'


if __name__ == '__main__':
    files = {}
    for p in sorted(C.OUT.rglob('*')):
        if p.is_file():
            rel = str(p.relative_to(C.OUT)).replace('\\', '/')
            if rel in EXCLUDE:
                continue
            files[rel] = dict(sha256=C.sha(p), bytes=p.stat().st_size)
    output_bytes = sum(v['bytes'] for v in files.values())
    src = C.HERE
    code = {}
    for p in sorted(src.rglob('*')):
        if p.is_file():
            code[str(p.relative_to(src)).replace('\\', '/')] = C.sha(p)
    C.write(C.OUT / 'MANIFEST.json', dict(
        item=C.ITEM, files=files, count=len(files), output_bytes=output_bytes,
        source_code=code, source_code_sha=C.digest(code),
        note='excludes MANIFEST.json/FINAL_SEAL.json/FINAL_SEAL.sha256 to avoid self-reference'))
    manifest_sha = C.sha(C.OUT / 'MANIFEST.json')
    seal = dict(
        item=C.ITEM, status='SUBMITTED', sealed_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        acceptance_sha=C.sha(C.OUT / 'ACCEPTANCE_V1.md'),
        protocol_sha=C.sha(C.OUT / 'PROTOCOL_V2.json'),
        protocol_v1_sha=C.sha(C.OUT / 'PROTOCOL_V1.json'),
        transform_sha=C.sha(C.OUT / 'TRANSFORM/TRANSFORM_S3.json'),
        transform_id=C.load(C.OUT / 'TRANSFORM/TRANSFORM_S3.json')['transform_id'],
        qualification_sha=C.sha(C.OUT / 'TRANSFORM/TRANSFORM_QUALIFICATION.json'),
        domains_sha=C.sha(C.OUT / 'DOMAINS/S3_DOMAINS.json'),
        domains_npz_sha=C.sha(C.OUT / 'DOMAINS/domains_s3.npz'),
        m0_sha=C.sha(C.OUT / 'M0/M0.json'),
        m0_map_id=C.load(C.OUT / 'M0/M0.json')['primary']['map_id'],
        verification_sha=C.sha(C.OUT / 'RUN/VERIFICATION.json'),
        frames_jsonl_sha=C.sha(C.OUT / 'RUN/frames.jsonl'),
        conservation_sha=C.sha(C.OUT / 'RUN/FRAME_CONSERVATION.json'),
        objects_sha=C.sha(C.OUT / 'OBJECTS_CHECK.json'),
        browser_results_sha=C.sha(C.OUT / 'BROWSER/BROWSER_RESULTS.json'),
        report_sha=C.sha(C.OUT / 'REPORT.md'),
        handoff_sha=C.sha(C.OUT / 'HANDOFF.md'),
        source=C.FROZEN,
        source_code_sha=C.digest(code),
        manifest_sha=manifest_sha, manifest_files=len(files), output_bytes=output_bytes,
        workflow_sha=C.sha(C.ROOT / 'docs/human_fall/WORKFLOW.md'),
        review_log_sha=C.sha(C.ROOT / 'docs/human_fall/REVIEW_LOG.md'),
        return_sha=C.sha(RETURN) if RETURN.is_file() else None,
        item_state=dict(geometry='GEOMETRY_VALIDATED_LOCAL from fi 271',
                        identity='BLOCKED', physical='BLOCKED', independent_D='BLOCKED',
                        human_effect='NOT_RUN', device='NOT_RUN', s4='NOT_RUN', s5='NOT_RUN'),
        note='seal excludes FINAL_SEAL.json/FINAL_SEAL.sha256/MANIFEST.json to avoid self-reference')
    C.write(C.OUT / 'FINAL_SEAL.json', seal)
    seal_sha = C.sha(C.OUT / 'FINAL_SEAL.json')
    with (C.OUT / 'FINAL_SEAL.sha256').open('xb') as f:
        f.write(('%s  FINAL_SEAL.json\n' % seal_sha).encode('utf8'))
    print('manifest_files=%d output_bytes=%d seal=%s' % (len(files), output_bytes, seal_sha))
