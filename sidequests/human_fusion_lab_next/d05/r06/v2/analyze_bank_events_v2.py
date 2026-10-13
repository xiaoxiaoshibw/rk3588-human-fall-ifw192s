"""Audit actual pre-fusion bank provenance after a completed full replay."""
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[5]
OUT = ROOT / 'docs/human_capture/evidence/2026-10-12_hfus_d05_r6'
variant = sys.argv[1]
summary = json.loads((OUT / 'runs' / variant / ('R06_' + variant + '_SUMMARY.json')).read_text(encoding='utf-8'))
reference = {}
with (ROOT / 'docs/human_capture/evidence/2026-10-12_hfus_d05_r4/RETENTION_BANK.jsonl').open(encoding='utf-8') as f:
    for line in f:
        r = json.loads(line)
        reference[(r['sid'], r['frame_index'])] = r['bank_after']
sessions = []
with (OUT / ('BANK_EVENT_CASES_v2_' + variant + '.jsonl')).open('x', encoding='utf-8') as log:
    for session in summary['sessions']:
        stats = Counter()
        largest_shift = 0.0
        with Path(session['ledger']['path']).open(encoding='utf-8') as f:
            for line in f:
                row = json.loads(line)
                event = row['bank_events']
                stats['frames'] += 1
                expired_prior = [i for i, b in event['bank_before'].items()
                                 if row['frame_index'] - b['frame_index'] > session['config']['retention']['max_lost_for_retain']
                                 or row['timestamp'] - b['timestamp'] > session['config']['retention']['timeout_s']]
                reentered = [i for i in expired_prior if i in event['bank_after']
                             and event['bank_after'][i]['frame_index'] == row['frame_index']]
                stats['derived_expired_prior_anchors'] += len(expired_prior)
                stats['derived_same_id_reentry_after_expiry'] += len(reentered)
                if variant == 'control':
                    assert event['bank_after'] == reference[(row['sid'], row['frame_index'])], 'control bank drift'
                assert {r['raw_index'] for r in event['retained_owners']} == set(row['stages']['retained_ids'])
                assert all(r['anchors'] for r in event['retained_owners'])
                groups = defaultdict(list)
                for c in event['pre_fusion_candidates']:
                    assert c['independent_fg_points'] + c['retained_points'] == len(c['raw_indices'])
                    assert (c['foreground_source'] == 'fg') == (c['retained_points'] == 0)
                    groups[c['internal_track_id']].append(c)
                repeated = {str(i): [c['id'] for c in cs] for i, cs in groups.items() if len(cs) > 1}
                stats['multi_assignment_frames'] += bool(repeated)
                cases = []
                for u in event['updates']:
                    cs = groups[u['internal_track_id']]
                    chosen = next(c for c in cs if c['id'] == u['proof_candidate'])
                    assert chosen['retained_points'] == 0 and chosen['prob'] >= session['config']['rf51_threshold']
                    expected = variant == 'guard' and u['displacement_m'] > session['config']['retention']['hot_cell_radius_m']
                    assert u['anchor_changed'] == expected
                    assert u['current_anchor'] == (u['proof_centroid'] if expected else u['original_pipe_anchor'])
                    stats['corrected_updates'] += expected
                    stats['updates'] += 1
                    shift = u['displacement_m']
                    largest_shift = max(largest_shift, shift)
                    stats['shift_over_1cm'] += shift > .01
                    stats['shift_over_5cm'] += shift > .05
                    stats['shift_over_10cm'] += shift > .1
                    mixed = len(cs) > 1 and any(c['retained_points'] for c in cs)
                    stats['updates_with_multiple_assignments'] += len(cs) > 1
                    stats['updates_with_retained_coassignment'] += mixed
                    overlaps = []
                    ids = set(chosen['raw_indices'])
                    for g in row['gt']:
                        hits = len(ids & set(g['indices']))
                        if hits:
                            overlaps.append({'gt_id': g['id'], 'class': g['class_name'], 'source': g['source'],
                                             'coverage': hits / len(g['indices']), 'purity': hits / len(ids)})
                    if shift > .01 or mixed:
                        cases.append({**u, 'coassigned_candidates': [{k: c[k] for k in ['id', 'foreground_source', 'independent_fg_points', 'retained_points', 'prob', 'centroid']} for c in cs],
                                      'qualified_gt_overlap_diagnostic_only': overlaps})
                if cases or repeated or expired_prior:
                    log.write(json.dumps({'sid': row['sid'], 'frame': row['frame_index'], 'timestamp': row['timestamp'],
                                          'qualification': row['qualification'], 'updates': cases, 'multi_assignment': repeated,
                                          'derived_expired_prior_ids': expired_prior, 'derived_same_id_reentered': reentered,
                                          'expiry_derivation': 'frame AND seconds TTL enforced; raw runtime labels retained unchanged'}) + '\n')
        assert stats['frames'] == session['frames']
        sessions.append({'sid': session['sid'], **dict(stats), 'max_displacement_m': largest_shift})
with (OUT / ('BANK_EVENT_SUMMARY_v2_' + variant + '.json')).open('x', encoding='utf-8') as f:
    json.dump({'status': 'PASS', 'variant': variant, 'frames': sum(s['frames'] for s in sessions),
               'sessions': sessions, 'analyzer_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
               'scope': 'bank provenance and displacement; diagnostic overlap is not independent furniture qualification; no GT inference'}, f, indent=2)
print(json.dumps({'variant': variant, 'sessions': sessions}), flush=True)
