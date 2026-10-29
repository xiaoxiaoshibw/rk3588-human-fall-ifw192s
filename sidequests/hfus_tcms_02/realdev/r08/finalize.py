"""Create the exclusive manifest and final seal for this item."""
import hashlib
import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
EV = ROOT / 'docs/human_fall/evidence/2026-10-18_hfus_human_skeleton_02_r1'
HERE = Path(__file__).resolve().parent
RETURN = ROOT / 'docs/human_fall/returns/HFUS-HUMAN-SKELETON-02.md'
WORKFLOW = ROOT / 'docs/human_fall/WORKFLOW.md'
REVIEW = ROOT / 'docs/human_fall/REVIEW_LOG.md'


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda: f.read(16 * 1024 * 1024), b''):
            h.update(b)
    return h.hexdigest()


def dump_new(name, value):
    p = EV / name
    with p.open('x', encoding='utf8', newline='\n') as f:
        json.dump(value, f, ensure_ascii=False, indent=2, allow_nan=False)
        f.write('\n')
    return p


def source_hashes():
    names = ['calibrate.py', 'wire.py', 'synthetic.py', 'server.py',
             'index.html', 'app.js', 'browser_check.js', 'verify.py', 'finalize.py']
    return {name: sha(HERE / name) for name in names}


def main():
    src = source_hashes()
    src_sha = hashlib.sha256(json.dumps(src, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    delivery = dict(
        item='HFUS-HUMAN-SKELETON-02', status='SUBMITTED', accepted=False,
        acceptance='ACCEPTANCE_V2.md', report='REPORT.md', handoff='HANDOFF.md',
        protocol_final='PROTOCOL_V3.json', final_run='RUN_R4/', synthetic='SYNTHETIC_CALIBRATION_R4.json',
        real_evaluation='REAL_EVALUATION.json', state_machine='STATE_MACHINE_CHECK.json',
        association='ASSOCIATION_CHECK_R2.json', browser='BROWSER/attempt2/BROWSER_RESULTS.json',
        preservation='PRESERVATION.json', scope='SCOPE_DIFF.json', performance='FINAL_PERFORMANCE.json',
        return_path='docs/human_fall/returns/HFUS-HUMAN-SKELETON-02.md',
        note='Author self-verification only; Codex formal independent review NOT_RUN; not ACCEPTED.')
    dump_new('DELIVERY_INDEX.json', delivery)
    excluded = {'MANIFEST.json', 'FINAL_SEAL.json', 'FINAL_SEAL.sha256'}
    entries = {}
    for p in sorted(EV.rglob('*')):
        if p.is_file() and p.name not in excluded:
            entries[str(p.relative_to(EV)).replace('\\', '/')] = dict(sha256=sha(p), bytes=p.stat().st_size)
    output_bytes = sum(v['bytes'] for v in entries.values())
    manifest = dict(
        item='HFUS-HUMAN-SKELETON-02', status='SUBMITTED', accepted=False,
        files=entries, count=len(entries), output_bytes=output_bytes,
        source_code=src, source_code_sha=src_sha,
        jsonl_newline='LF', note='MANIFEST excludes MANIFEST/FINAL_SEAL/FINAL_SEAL.sha256; all listed paths are item-local.')
    manifest_path = dump_new('MANIFEST.json', manifest)
    seal = dict(
        item='HFUS-HUMAN-SKELETON-02', status='SUBMITTED', accepted=False,
        sealed_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        acceptance_sha=sha(EV / 'ACCEPTANCE_V2.md'),
        protocol_v1_sha=sha(EV / 'PROTOCOL_V1.json'),
        protocol_v2_sha=sha(EV / 'PROTOCOL_V2.json'),
        protocol_v3_sha=sha(EV / 'PROTOCOL_V3.json'),
        report_sha=sha(EV / 'REPORT.md'), handoff_sha=sha(EV / 'HANDOFF.md'),
        real_evaluation_sha=sha(EV / 'REAL_EVALUATION.json'),
        state_machine_sha=sha(EV / 'STATE_MACHINE_CHECK.json'),
        association_sha=sha(EV / 'ASSOCIATION_CHECK_R2.json'),
        synthetic_sha=sha(EV / 'SYNTHETIC_CALIBRATION_R4.json'),
        browser_sha=sha(EV / 'BROWSER/attempt2/BROWSER_RESULTS.json'),
        preservation_sha=sha(EV / 'PRESERVATION.json'),
        scope_sha=sha(EV / 'SCOPE_DIFF.json'),
        performance_sha=sha(EV / 'FINAL_PERFORMANCE.json'),
        document_append_sha=sha(EV / 'DOCUMENT_APPEND.json'),
        run_frame_summary_sha=sha(EV / 'RUN_R4/FRAME_SUMMARY.json'),
        run_calibration_sha=sha(EV / 'RUN_R4/CALIBRATION.json'),
        run_tracks_sha=sha(EV / 'RUN_R4/TRACKS.json'),
        source_code_sha=src_sha,
        manifest_sha=sha(manifest_path), manifest_files=manifest['count'],
        return_sha=sha(RETURN), workflow_sha=sha(WORKFLOW), review_log_sha=sha(REVIEW),
        real_result=dict(A04_PASS=True, action_frames_with_candidate=383,
                         action_frames_with_six_valid_nodes=317,
                         candidate_action_fraction=0.8276762402088773,
                         all_action_fraction=0.6469387755102041,
                         cross_window_stable_edges=7,
                         max_cross_window_std_m=0.012364802998096664),
        synthetic_result=dict(PASS=True, scenarios=4, measurable_edges=47,
                              within=47, calibrated=46),
        semantic=dict(anatomy='UNKNOWN', left_right='UNKNOWN', physical_height='UNKNOWN',
                      human_identity='UNKNOWN', fall_effectiveness='BLOCKED_NO_LABELS',
                      independent_D=False),
        review_state=dict(codex_formal_review='NOT_RUN', accepted=False),
        note='SUBMITTED, author self-verified; not ACCEPTED.')
    seal_path = dump_new('FINAL_SEAL.json', seal)
    seal_sha = sha(seal_path)
    with (EV / 'FINAL_SEAL.sha256').open('x', encoding='ascii', newline='\n') as f:
        f.write(seal_sha + '  FINAL_SEAL.json\n')
    print(json.dumps(dict(manifest_sha=seal['manifest_sha'], manifest_files=seal['manifest_files'],
                          final_seal_sha256=seal_sha, output_bytes=output_bytes), ensure_ascii=False))


if __name__ == '__main__':
    main()
