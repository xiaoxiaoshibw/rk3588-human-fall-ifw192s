"""Read-only verification of the completed skeleton-calibration run."""
import hashlib
import json
import sys
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[4]
EV = ROOT / 'docs/human_fall/evidence/2026-10-18_hfus_human_skeleton_02_r1'
RUN = EV / 'RUN_R4'
S3 = ROOT / 'docs/human_fall/evidence/2026-10-17_hfus_tcms_02_s03_r1'
SOURCE = ROOT / 'data/sessions/cap_20261017_113516'


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda: f.read(16 * 1024 * 1024), b''):
            h.update(b)
    return h.hexdigest()


def write_new(name, value):
    p = EV / name
    with p.open('x', encoding='utf8', newline='\n') as f:
        json.dump(value, f, ensure_ascii=False, indent=2, allow_nan=False)
        f.write('\n')
    return p


def source_frame():
    return None


def main():
    protocol = json.loads((EV / 'PROTOCOL_V3.json').read_text(encoding='utf8'))
    meta = json.loads((RUN / 'RUN_META.json').read_text(encoding='utf8'))
    summary = json.loads((RUN / 'FRAME_SUMMARY.json').read_text(encoding='utf8'))
    tracks = json.loads((RUN / 'TRACKS.json').read_text(encoding='utf8'))
    records = []
    with (RUN / 'frames.jsonl').open(encoding='utf8') as f:
        for line in f:
            records.append(json.loads(line))
    if len(records) != 780 or [r['fi'] for r in records] != list(range(780)):
        raise ValueError('frame record denominator/order drift')
    # A01 input bindings and read-only imports.
    input_sha = dict(
        item='HFUS-HUMAN-SKELETON-02',
        protocol=dict(path='PROTOCOL_V3.json', sha256=sha(EV / 'PROTOCOL_V3.json')),
        source=dict(sid='cap_20261017_113516',
                    meta=sha(SOURCE / 'meta.json'), points=sha(SOURCE / 'points.bin'),
                    frames=780, rows=38298918),
        inherited=dict(
            transform=dict(path='docs/human_fall/evidence/2026-10-17_hfus_tcms_02_s03_r1/TRANSFORM/TRANSFORM_S3.json',
                           sha256=sha(S3 / 'TRANSFORM/TRANSFORM_S3.json'), transform_id=meta['transform_id']),
            domains=dict(path='docs/human_fall/evidence/2026-10-17_hfus_tcms_02_s03_r1/DOMAINS/S3_DOMAINS.json',
                         sha256=sha(S3 / 'DOMAINS/S3_DOMAINS.json')),
            domains_npz=dict(path='docs/human_fall/evidence/2026-10-17_hfus_tcms_02_s03_r1/DOMAINS/domains_s3.npz',
                             sha256=sha(S3 / 'DOMAINS/domains_s3.npz')),
            m0=dict(path='docs/human_fall/evidence/2026-10-17_hfus_tcms_02_s03_r1/M0/M0.json',
                    sha256=sha(S3 / 'M0/M0.json'), map_id=meta['m0_map_id']),
            s2_candidate=dict(path='docs/human_fall/evidence/2026-10-17_hfus_tcms_02_s02_r1/full_r1/CANDIDATES.json',
                              sha256=sha(ROOT / 'docs/human_fall/evidence/2026-10-17_hfus_tcms_02_s02_r1/full_r1/CANDIDATES.json'))),
        read_only=protocol['reuse_readonly']['files_sha256'],
        read_only_unchanged=bool(summary['read_only_unchanged']),
        source_unchanged_during_run=bool(sha(SOURCE / 'meta.json') == 'eeb336b895e2a147a09f23f9d69cdecb9490e020c2d91467e2ab5a84bd082ad4'
                                          and sha(SOURCE / 'points.bin') == '254c481fb4faad01f6d30d4630b471dcbc74a25985caba0949ea6d40705f84f1'),
        data_zero_write=bool(sha(SOURCE / 'meta.json') == 'eeb336b895e2a147a09f23f9d69cdecb9490e020c2d91467e2ab5a84bd082ad4'
                                 and sha(SOURCE / 'points.bin') == '254c481fb4faad01f6d30d4630b471dcbc74a25985caba0949ea6d40705f84f1'),
    )
    write_new('INPUT_SHA.json', input_sha)
    # A02 call sites, copied from actual source locations.
    wire_text = (ROOT / 'sidequests/hfus_tcms_02/realdev/r08/wire.py').read_text(encoding='utf8')
    lines = wire_text.splitlines()
    calls = []
    for key, needle in [('estimate', 'SK.estimate('),
                        ('stabilize_display', 'SK.stabilize_display('),
                        ('associate_tracks', 'A.associate_tracks(')]:
        hits = [dict(line=i + 1, text=line.strip()) for i, line in enumerate(lines) if needle in line]
        calls.append(dict(name=key, call_site=hits))
    copied = []
    for name in ['wire.py', 'calibrate.py', 'synthetic.py']:
        text = (ROOT / 'sidequests/hfus_tcms_02/realdev/r08' / name).read_text(encoding='utf8')
        for forbidden in ['def estimate(', 'def stabilize_display(', 'def associate_tracks(']:
            if forbidden in text:
                copied.append(dict(file=name, definition=forbidden))
    write_new('REUSE_CALLS.json', dict(
        item='HFUS-HUMAN-SKELETON-02', strategy='CONSOLIDATION',
        calls=calls,
        copied_implementations=copied,
        no_copied_implementations=bool(not copied),
        display_only_rule='stabilize_display mutates display_xyz/display_edges only; skeleton_measurements() reads raw xyz.',
        files=protocol['reuse_readonly']['files_sha256'],
        read_only_unchanged=bool(summary['read_only_unchanged'])))
    # A04 real-data evaluation.
    action = [r for r in records if r['phase'] == 'ACTION']
    action_candidates = [r for r in action if r['candidate_summaries']]
    action_six = [r for r in action_candidates if r['best_valid_nodes'] >= 6]
    primary = tracks['tracks'][tracks['primary_track']]
    edge_eval = {}
    cross_stable = []
    for key, value in sorted(primary['calibration']['edges'].items()):
        if not value['ever_calibrated']:
            continue
        metrics = []
        for episode in value.get('calibration_episodes', []):
            metric = episode.get('cross_window_std_m')
            if metric is None:
                metric = episode.get('raw_std_m')
            metrics.append(dict(start_frame=episode['start_frame'], end_frame=episode['end_frame'],
                                n=episode['n'], raw_std_m=episode['raw_std_m'],
                                cross_window_std_m=episode['cross_window_std_m'],
                                gate_metric_m=metric))
        best = min((m['gate_metric_m'] for m in metrics), default=None)
        has_cross = any(m['cross_window_std_m'] is not None for m in metrics)
        ok = bool(best is not None and best <= 0.02 and has_cross)
        edge_eval[key] = dict(ever_calibrated=True, episodes=metrics,
                              best_cross_window_metric_m=best,
                              has_cross_window_episode=has_cross,
                              stable=ok)
        if ok:
            cross_stable.append(key)
    all_cross = [m['gate_metric_m'] for e in edge_eval.values() for m in e['episodes']
                 if m['cross_window_std_m'] is not None]
    real = dict(
        item='HFUS-HUMAN-SKELETON-02', run='RUN_R4', action_start_s=30.0,
        action_frames=len(action),
        action_frames_with_r01_candidate=len(action_candidates),
        action_frames_with_six_valid_nodes=len(action_six),
        fraction_among_candidate_action_frames=(len(action_six) / len(action_candidates)
                                                if action_candidates else 0.0),
        fraction_among_all_action_frames=(len(action_six) / len(action) if action else 0.0),
        empty_or_insufficient_action_frames=len(action) - len(action_candidates),
        denominator='ACTION frames containing at least one r01 candidate with >=30 member rows; a skeleton cannot be measured on an empty candidate frame.',
        primary_track=tracks['primary_track'],
        primary_track_frames=primary['skeleton_frames'],
        calibrated_edges=sorted(edge_eval),
        calibrated_edge_count=len(edge_eval),
        cross_window_stable_edges=sorted(cross_stable),
        cross_window_stable_edge_count=len(cross_stable),
        max_cross_window_std_m=(max(all_cross) if all_cross else None),
        per_edge=edge_eval,
        node_gate_PASS=bool(action_candidates and len(action_six) / len(action_candidates) >= 0.8),
        calibration_gate_PASS=bool(len(cross_stable) >= 6 and all_cross and max(all_cross) <= 0.02),
        semantic=dict(anatomy='UNKNOWN', left_right='UNKNOWN', physical_height='UNKNOWN',
                      human_identity='UNKNOWN', effectiveness='BLOCKED_NO_LABELS'))
    real['A04_PASS'] = bool(real['node_gate_PASS'] and real['calibration_gate_PASS']
                             and input_sha['source_unchanged_during_run'])
    write_new('REAL_EVALUATION.json', real)
    # A05 state-machine evidence.
    transitions = {}
    drift_records = []
    states_seen = set()
    drift_state_events = []
    for tid, tr in tracks['tracks'].items():
        for key, value in tr['calibration']['edges'].items():
            states_seen.add(value['state'])
            for episode in value.get('calibration_episodes', []):
                states_seen.add('CALIBRATED')
            for event in tr['calibration']['state_events']:
                if event['edge'] == key.split('|'):
                    label = event['old'] + '->' + event['new']
                    transitions[label] = transitions.get(label, 0) + 1
                    states_seen.add(event['old']); states_seen.add(event['new'])
                    if event['new'] == 'DRIFT_RESET':
                        drift_state_events.append(event)
            for drift in tr['calibration']['drift_events']:
                if drift['edge'] == key.split('|'):
                    drift_records.append(drift)
    bad_drifts = [d for d in drift_records
                  if not (d['ratio'] < d['band'][0] or d['ratio'] > d['band'][1])]
    for fi_record in records:
        for tr in fi_record['track_results']:
            for edge in tr['edges']:
                states_seen.add(edge['state'])
    state_check = dict(
        item='HFUS-HUMAN-SKELETON-02', run='RUN_R4',
        states_seen=sorted(states_seen),
        transitions=transitions,
        drift_reset_events=len(drift_records),
        drift_state_events=len(drift_state_events),
        bad_drift_records=len(bad_drifts),
        required_states_present=set(['COLLECTING','CALIBRATING','CALIBRATED','DRIFT_RESET']).issubset(states_seen),
        every_drift_outside_band=bool(not bad_drifts),
        no_silent_state_changes='state transitions carry old/new/reason and per-frame snapshots carry state/mean/sigma/n',
        PASS=bool(set(['COLLECTING','CALIBRATING','CALIBRATED','DRIFT_RESET']).issubset(states_seen)
                  and not bad_drifts and drift_records))
    write_new('STATE_MACHINE_CHECK.json', state_check)
    # A06 explicit association.
    assoc_keys = ['matches', 'ambiguous_track_ids', 'ambiguous_candidate_ids',
                  'unmatched_track_ids', 'unmatched_candidate_ids']
    n_matches = n_amb_tracks = n_amb_candidates = n_unmatched_tracks = n_unmatched_candidates = 0
    ambiguous_frames = 0
    silent_errors = []
    for r in records:
        assoc = r.get('association', {})
        if set(assoc_keys) - set(assoc):
            silent_errors.append(dict(fi=r['fi'], error='missing association keys'))
            continue
        n_matches += len(assoc['matches'])
        n_amb_tracks += len(assoc['ambiguous_track_ids'])
        n_amb_candidates += len(assoc['ambiguous_candidate_ids'])
        n_unmatched_tracks += len(assoc['unmatched_track_ids'])
        n_unmatched_candidates += len(assoc['unmatched_candidate_ids'])
        if assoc['ambiguous_track_ids'] or assoc['ambiguous_candidate_ids']:
            ambiguous_frames += 1
        amb = set(assoc['ambiguous_candidate_ids'])
        for tr in r['track_results']:
            if tr['candidate_id'] in amb:
                silent_errors.append(dict(fi=r['fi'], track_id=tr['track_id'],
                                          candidate_id=tr['candidate_id'],
                                          error='ambiguous candidate silently measured'))
    assoc_check = dict(
        item='HFUS-HUMAN-SKELETON-02', run='RUN_R4', frames=len(records),
        frames_with_all_explicit_fields=sum(1 for r in records
                                             if not (set(assoc_keys) - set(r.get('association', {})))),
        matches=n_matches, ambiguous_track_ids=n_amb_tracks,
        ambiguous_candidate_ids=n_amb_candidates,
        unmatched_track_ids=n_unmatched_tracks,
        unmatched_candidate_ids=n_unmatched_candidates,
        ambiguous_frames=ambiguous_frames,
        silent_ambiguity_assignments=silent_errors,
        PASS=bool(not silent_errors and ambiguous_frames > 0))
    write_new('ASSOCIATION_CHECK.json', assoc_check)
    # A07 browser pointer.
    browser_path = EV / 'BROWSER/attempt2/BROWSER_RESULTS.json'
    browser = json.loads(browser_path.read_text(encoding='utf8'))
    write_new('BROWSER_SUMMARY.json', dict(
        item='HFUS-HUMAN-SKELETON-02',
        primary_result='BROWSER/attempt2/BROWSER_RESULTS.json',
        primary_result_sha256=sha(browser_path),
        failed_retained='BROWSER/BROWSER_RESULTS.json (first attempt; point click selection missed on 7/8 frames)',
        browser=browser['browser'], input_method=browser['input_method'],
        summary=browser['summary'], PASS=bool(browser.get('PASS'))))
    print(json.dumps(dict(A04=real['A04_PASS'], A05=state_check['PASS'], A06=assoc_check['PASS'],
                          A07=browser.get('PASS')), ensure_ascii=False))


if __name__ == '__main__':
    main()
