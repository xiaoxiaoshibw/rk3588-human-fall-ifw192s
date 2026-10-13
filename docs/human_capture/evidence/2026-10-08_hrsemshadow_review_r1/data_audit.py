"""Independent source and evidence accounting, no r1 write calls."""
import csv
import hashlib
import importlib.util
import json
from collections import Counter, defaultdict
from pathlib import Path
import numpy as np
from audit import ROOT, OUT, R1, RET, sha, save

def read(p):
    return json.loads(p.read_text('utf8'))

def rows(p):
    with p.open('rb') as f:
        for line in f:
            yield json.loads(line)

def digest_list(v):
    return hashlib.sha256(json.dumps(v, separators=(',', ':')).encode()).hexdigest()

def main():
    b = read(OUT / 'baseline.json')['files']
    old = read(R1 / '00_baseline.json')['files']
    mismatches = []
    for n, v in old.items():
        if n == RET:
            with (ROOT / n).open('rb') as f:
                prefix = f.read(v['bytes'])
            if hashlib.sha256(prefix).hexdigest() != v['sha256']:
                mismatches.append(n)
        elif 'sha256' not in v:
            assert v.get('missing') and not (ROOT / n).is_file(), (n, v)
        elif n.replace('\\', '/') not in b or b[n.replace('\\', '/')]['sha256'] != v['sha256']:
            mismatches.append(n)
    integ = read(R1 / 'integrity.json')
    output_bad = [n for n, v in integ['outputs'].items() if b[(R1 / n).relative_to(ROOT).as_posix()]['sha256'] != v['sha256']]
    source_bad = [n for n, h in read(R1 / 'source_hashes.json').items() if sha(R1 / n) != h]
    pairs = {}
    for a, c in [('pass2', 'pass3'), ('negative3', 'negative4')]:
        d = read(R1 / a / 'digests.json')
        assert d == read(R1 / c / 'digests.json')
        for n, h in d.items():
            fn = n if '.' in n else n + ('.json' if n in ['summary', 'binding', 'reconciliation'] else '.jsonl')
            assert sha(R1 / a / fn) == sha(R1 / c / fn) == h
        pairs[a + '/' + c] = d
    logs = []
    for p in sorted(R1.glob('*.run.json')):
        r = read(p)
        logs.append({'file': p.name, **r})
    save('hash_and_log_audit.json', {'old_baseline_files': len(old), 'old_mismatches': mismatches,
        'r1_output_hash_mismatches': output_bad, 'source_hash_mismatches': source_bad, 'verified_digest_pairs': pairs, 'run_records': logs})
    assert not mismatches and not output_bad and not source_bad
    binding = read(R1 / 'pass3/binding.json')
    raw = {}
    metas = {}
    for s in binding['sessions']:
        sid = s['sid']; d = ROOT / 'captures/remote' / sid
        assert sha(d / 'meta.json') == s['source']['meta_sha256']
        assert sha(d / 'points.bin') == s['source']['bin_sha256']
        metas[sid] = read(d / 'meta.json')
        assert metas[sid]['point_layout']['stride_bytes'] == 28
        raw[sid] = np.memmap(d / 'points.bin', dtype='<f4', mode='r').reshape(-1, 7)
    cluster_by_frame = defaultdict(list)
    stats = defaultdict(Counter)
    human_frames = defaultdict(set)
    for c in rows(R1 / 'pass3/clusters.jsonl'):
        k = (c['sid'], c['mode'], c['ordinal'])
        cluster_by_frame[k].append(c)
        m = metas[c['sid']]['frames'][c['ordinal']]
        assert len(c['rows']) == len(set(c['rows'])) == c['n']
        assert c['global_rows'] == [m['offset_points'] + r for r in c['rows']]
        assert c['member_sha256'] == digest_list(c['rows'])
        invalid_members = set(c['invalid_rows'])
        assert c['valid_rows'] == [r for r in c['rows'] if r not in invalid_members]
        assert c['valid_n'] == len(c['valid_rows']) == c['semantic']['features']['n']
        if c['valid_n'] < 400:
            assert c['semantic']['semantic'] == 'UNKNOWN' and c['semantic']['reason'] == 'POINTS_LOW'
        assert c['gt']['source'] == 'diagnostic' and c['gt']['label'] == 'UNKNOWN'
        sk = '/'.join(k[:2]); stats[sk][c['semantic']['semantic']] += 1
        stats[sk]['60-199' if c['n'] < 200 else '200-399' if c['n'] < 400 else '>=400'] += 1
        if c['semantic']['semantic'] == 'HUMAN_EVIDENCE':
            human_frames[sk].add(k[2])
    stages = {}
    frame_counts = Counter()
    invalid_unique = {}
    for f in rows(R1 / 'pass3/frames.jsonl'):
        k = (f['sid'], f['mode'], f['ordinal']); sk = '/'.join(k[:2]); frame_counts[sk] += 1
        m = metas[f['sid']]['frames'][f['ordinal']]
        assert f['seq'] == m['seq'] and f['source_offset_points'] == m['offset_points']
        points = raw[f['sid']][m['offset_points']:m['offset_points'] + f['counts']['source'], :3]
        invalid = np.nonzero(~np.isfinite(points).all(axis=1) | (points == 0).all(axis=1))[0].tolist()
        assert f['invalid_source_rows'] == invalid
        invalid_unique[(f['sid'], f['ordinal'])] = len(invalid)
        s = f['stage_rows']; sets = {name: set(v) for name, v in s.items()}
        for name, v in s.items():
            assert v == sorted(v) and len(v) == len(sets[name])
            assert all(0 <= r < f['counts']['source'] for r in v)
        assert sets['cleanup'] <= sets['foreground'] <= sets['workspace']
        assert sets['cleanup_removed'] == sets['foreground'] - sets['cleanup']
        # reference_removed describes the parallel REF filter even in WORKSPACE/V2.
        assert not (sets['reference_removed'] & sets['online_supported_removed'])
        used = []
        invalid_set = set(invalid)
        for c in cluster_by_frame[k]:
            used += c['rows']
            assert c['invalid_rows'] == [r for r in c['rows'] if r in invalid_set]
        for c in f['small_components']:
            assert c['n'] < 60 and len(c['rows']) == c['n']; used += c['rows']
        assert len(used) == len(set(used)) and set(used) <= sets['cleanup']
        assert len(sets['cleanup'] - set(used)) == f['counts']['unassigned']
        assert len(cluster_by_frame[k]) == f['counts']['candidates']
        stages['/'.join(map(str, k))] = {name: digest_list(v) for name, v in s.items()}
    assert len(stages) == 1561 and len(invalid_unique) == 1276
    save('stage_hashes.json', stages)
    vote_stats = defaultdict(Counter)
    for v in rows(R1 / 'pass3/votes.jsonl'):
        fi = v['ordinal']; sk = v['sid'] + '/' + v['mode']
        ids = [a['identity'] for a in v['reference']['assigned'] if a['identity'] is not None]
        assert len(ids) == len(set(ids))
        for t in v['reference']['windows']:
            w = t['window']; frames = [x['f'] for x in w]
            assert frames == list(range(max(t['born'], fi - 4), fi + 1))
            assert t['age'] == fi - t['born'] + 1
            unknown = any(x['semantic'] is None for x in w)
            for field in ['semantic', 'old']:
                n = sum(x[field] or 0 for x in w)
                assert t[field + '_votes'] == n
                assert t[field + '_confirmed'] == (None if unknown else t['age'] >= 3 and n >= 3)
            for x in w:
                if x.get('missing'):
                    assert x['old'] == x['semantic'] == 0
            assert t['human_identity_status'] == 'BLOCKED_GT'
        vote_stats[sk]['collision_frames'] += any(t['collision_this_frame'] for t in v['original'])
        vote_stats[sk]['stale_frames'] += any(t['original_human_confirmed'] and not t['normalized_old_confirmed'] for t in v['original'])
    edge = read(R1 / 'edge_review.json')
    assert len(edge['points']) == 52228 and len(edge['cleanup_roi_points']) == 5
    old_region = read(ROOT / 'docs/human_capture/evidence/2026-10-08_new_static_sessions_r1/region_audit.json')
    previous = next(r['lostROI'] for s in old_region['sessions'] if s['sid'].endswith('114340') for r in s['rows'] if r['ordinal'] == 140)
    actual = [e['xyz'] for e in edge['points'] if e['ordinal'] == 140 and 'reference_removed' in e['stages']]
    assert sorted(actual) == sorted(previous) and len(actual) == 185
    for e in edge['points']:
        assert e['source'] == 'diagnostic' and e['label'] == 'UNKNOWN'
        assert e['id'] == '/'.join([e['sid'], e['mode'], str(e['ordinal']), 'p' + str(e['row'])])
    neg = defaultdict(Counter)
    for c in rows(R1 / 'negative4/negative_clusters.jsonl'):
        neg[c['sid'] + '/' + c['mode']][c['semantic']['semantic']] += 1
    regions = defaultdict(Counter)
    wd_hits = []
    for c in rows(R1 / 'negative4/negative_regions.jsonl'):
        sk = c['sid'] + '/' + c['mode'] + '/' + c['id']
        regions[sk][c['semantic']['semantic']] += 1
        regions[sk]['zero'] += not c['rows']
        if c['id'] == 'WD01' and c['semantic']['semantic'] == 'HUMAN_EVIDENCE':
            wd_hits.append({'sid': c['sid'], 'mode': c['mode'], 'ordinal': c['ordinal'], 'rows': c['rows']})
    spec = importlib.util.spec_from_file_location('r1finish', R1 / 'finish.py')
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    gt_check = module.gt_selfcheck()
    save('data_audit.json', {'raw_frames': len(invalid_unique), 'branch_frames': len(stages), 'candidate_clusters': sum(len(x) for x in cluster_by_frame.values()),
        'frame_counts': dict(frame_counts), 'cluster_counts': {k: dict(v) for k, v in stats.items()},
        'human_frames': {k: len(v) for k, v in human_frames.items()}, 'invalid_unique': sum(invalid_unique.values()),
        'vote_stats': {k: dict(v) for k, v in vote_stats.items()}, 'edge_points': len(edge['points']), 'edge185': len(actual),
        'cleanup5': edge['cleanup_roi_points'], 'negative_clusters': {k: dict(v) for k, v in neg.items()},
        'negative_regions': {k: dict(v) for k, v in regions.items()}, 'WD01_region_human': wd_hits, 'gt_schema_selfcheck': gt_check})
    print('INDEPENDENT_DATA_PASS', len(stages), 'frame branches;', sum(len(x) for x in cluster_by_frame.values()), 'clusters;', sum(invalid_unique.values()), 'invalid raw rows')

if __name__ == '__main__':
    main()
