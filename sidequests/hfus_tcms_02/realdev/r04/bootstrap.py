"""T0 bootstrap: item registration, source re-verification, candidate freeze, workspace baseline.

Runs before any transform/domain/map work and writes only into the new S3 evidence root.
"""
import hashlib
import json
import platform
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import s3core as C


def git(*args):
    return subprocess.check_output(['git', *args], cwd=C.ROOT)


def source_state():
    meta, points = C.SOURCE / 'meta.json', C.SOURCE / 'points.bin'
    m = json.loads(meta.read_bytes().decode('utf8'))
    return dict(meta_sha=C.sha(meta), points_sha=C.sha(points), meta_bytes=meta.stat().st_size,
                points_bytes=points.stat().st_size, frames=len(m['frames']),
                rows=int(m['total_points']), duration_s=float(m['duration_sec']),
                created_iso=m['created_iso'], session_id=m['session_id'],
                stride=int(m['point_stride_bytes']),
                data_junction=(C.ROOT / 'captures/remote/cap_20261017_113516').resolve() == C.SOURCE.resolve())


def file_record(path):
    p = C.ROOT / path
    if p.is_symlink():
        return dict(path=path, kind='symlink', target=str(p.readlink()))
    if p.is_file():
        return dict(path=path, kind='file', sha256=C.sha(p), bytes=p.stat().st_size)
    return dict(path=path, kind='missing_or_nonfile')


if __name__ == '__main__':
    C.OUT.mkdir(exist_ok=True)
    st = source_state()
    if (st['meta_sha'], st['points_sha'], st['rows'], st['frames']) != (
            C.FROZEN['meta'], C.FROZEN['points'], C.FROZEN['rows'], C.FROZEN['frames']):
        raise SystemExit('SOURCE MISMATCH ' + json.dumps(st))
    if C.sha(C.HIST) != C.FROZEN['hist_sha']:
        raise SystemExit('HISTORICAL TRANSFORM DRIFT')
    s2 = dict(report=C.sha(C.S2 / 'REPORT.md'), seal=C.sha(C.S2 / 'FINAL_SEAL.json'),
              candidates=C.sha(C.S2 / 'full_r1/CANDIDATES.json'),
              validation=C.sha(C.S2 / 'full_r1/VALIDATION.json'),
              audit_domains=C.sha(C.S2 / 'audit/AUDIT_DOMAINS_V4.json'),
              audit_npz=C.sha(C.S2 / 'audit/domains_v4.npz'),
              protocol=C.sha(C.S2 / 'PROTOCOL_V4.json'))
    expected = dict(report=C.FROZEN['s2_report'], seal=C.FROZEN['s2_seal'], candidates=C.FROZEN['s2_candidates'],
                    validation=C.FROZEN['s2_validation'], audit_domains=C.FROZEN['s2_domains_json'],
                    audit_npz=C.FROZEN['s2_domains'], protocol=C.FROZEN['s2_protocol'])
    if s2 != expected:
        raise SystemExit('S2 BASIS DRIFT ' + json.dumps(s2))
    cand = [c for c in C.load(C.S2 / 'full_r1/CANDIDATES.json') if c['id'] == C.FROZEN['candidate_id']]
    if len(cand) != 1 or cand[0]['n'] != [-0.4265240687245509, -0.022919694282833247, 0.9041857698574097] or \
            cand[0]['d'] != 1.3371657243363564:
        raise SystemExit('CANDIDATE DRIFT')
    C.write(C.OUT / 'INPUT_SHA.json', dict(
        item=C.ITEM, frozen=C.FROZEN, source=st, s2=s2, historical=dict(
            path='data/leveled/61cb6976b0f8479394641850d9a7c6ca/tls/transform.json', sha=C.sha(C.HIST)),
        s2_plan=dict(path='docs/human_fall/evidence/2026-10-17_hfus_tcms_02_s03_plan_r1/S3_PLAN_V1.md',
                     sha=C.sha(C.ROOT / 'docs/human_fall/evidence/2026-10-17_hfus_tcms_02_s03_plan_r1/S3_PLAN_V1.md')),
        protocol=dict(sha=C.sha(C.OUT / 'PROTOCOL_V1.json')),
        acceptance=dict(sha=C.sha(C.OUT / 'ACCEPTANCE_V1.md')),
        note='rehashed in this session before any real-data processing'))
    C.write(C.OUT / 'CANDIDATE_FREEZE.json', dict(
        item=C.ITEM, chosen=cand[0], candidate_id=C.FROZEN['candidate_id'],
        controls=[dict(id=c['id'], n=c['n'], d=c['d'], status=c['status'], fit_pass=c['fit_pass'],
                       val_pass=c['val_pass'], role='comparison only; never fitted/averaged/substituted')
                  for c in C.load(C.S2 / 'full_r1/CANDIDATES.json')],
        rule='no re-fit, no averaging, no model change after any S3 validation number',
        source_candidates_sha=s2['candidates'],
        note='candidate parameters are the frozen S2 values; S3 only converts them into R/t'))
    C.write(C.OUT / 'ENVIRONMENT.json', dict(
        item=C.ITEM, writer='single implementation writer in this session',
        executor='DSH agent (this session)', model='deepseek-flash as declared by the harness; exact runtime ID not exposed; no model switch',
        platform=platform.platform(), python=sys.version, executable=sys.executable,
        numpy=__import__('numpy').__version__, scipy=__import__('scipy').__version__,
        node=subprocess.check_output(['node', '-v']).decode().strip(),
        strategy=dict(transform_and_wiring='ENGINEERING', m0_rebuild_and_replay='ENGINEERING',
                      new_validation_domain='RESEARCH', browser='ENGINEERING'),
        ponytail='C:/Users/30680/.codex/skills/ponytail/SKILL.md',
        scientific_toolkit='C:/Users/30680/.codex/skills/scientific-toolkit-skill/SKILL.md',
        image_libs=dict(pillow=__import__('PIL').__version__, matplotlib=__import__('matplotlib').__version__)))
    C.write(C.OUT / 'BASELINE_GIT.json', dict(
        branch=git('branch', '--show-current').decode().strip(),
        head=git('rev-parse', 'HEAD').decode().strip(),
        status=git('status', '--porcelain=v1', '-uall').decode('utf8'),
        scope='all tracked and non-ignored untracked files; data/ is input, hashed separately'))
    files = sorted(set(git('ls-files', '-c', '-o', '--exclude-standard', '-z').decode('utf8').split('\0')) - {''})
    tracked = [p for p in files if not p.startswith('data/')]
    with ThreadPoolExecutor(max_workers=12) as ex:
        records = list(ex.map(file_record, tracked))
    with (C.OUT / 'BASELINE_FILES.jsonl').open('x', encoding='utf8', newline='\n') as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + '\n')
    C.write(C.OUT / 'BASELINE_SUMMARY.json', dict(
        files=len(files), tracked_records=len(records),
        excluded_data_files=len(files) - len(tracked),
        workflow_bytes=(C.ROOT / 'docs/human_fall/WORKFLOW.md').stat().st_size,
        workflow_sha=C.sha(C.ROOT / 'docs/human_fall/WORKFLOW.md'),
        review_log_bytes=(C.ROOT / 'docs/human_fall/REVIEW_LOG.md').stat().st_size,
        review_log_sha=C.sha(C.ROOT / 'docs/human_fall/REVIEW_LOG.md'),
        line_endings='WORKFLOW and REVIEW_LOG are LF-only after S2; S3 appends bytes in binary and only LF'))
    print(json.dumps(dict(files=len(files), tracked=len(records), source=st, s2=s2), ensure_ascii=False))
