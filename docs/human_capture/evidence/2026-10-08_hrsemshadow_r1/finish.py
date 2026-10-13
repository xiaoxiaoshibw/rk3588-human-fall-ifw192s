"""Stream full evidence; generate review materials and validate actual human sidecars."""
import copy
import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
import re
import sys

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]

def read(p):
    return json.loads(p.read_text(encoding='utf8'))

def sha(p):
    h = hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda: f.read(4 << 20), b''):
            h.update(b)
    return h.hexdigest()

def write(name, obj):
    with (OUT / name).open('x', encoding='utf8', newline='\n') as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
        f.write('\n')

def lines(p):
    with p.open('rb') as f:
        while True:
            offset = f.tell()
            line = f.readline()
            if not line:
                break
            yield offset, json.loads(line)

def framekey(r):
    return (r['sid'], r['mode'], r['ordinal'])

def check_gt(gt, binding, clusters, points):
    if gt.get('kind') != 'hr_sem_shadow_gt' or gt.get('schema') != 1 or gt.get('source') != 'human':
        raise ValueError('requires explicit human sidecar; diagnostic template is not GT')
    if not str(gt.get('reviewer', '')).strip() or not gt.get('created_iso'):
        raise ValueError('missing actual reviewer or review time')
    if gt.get('binding') != binding:
        raise ValueError('source/transform/code binding mismatch')
    seen = set()
    for kind, mapping in [('clusters', clusters), ('points', points)]:
        for r in gt.get(kind, []):
            if r.get('id') in seen or r.get('id') not in mapping:
                raise ValueError('duplicate or unbound review id')
            seen.add(r['id'])
            ref = mapping[r['id']]
            for k in ['sid', 'mode', 'ordinal', 'seq']:
                if r.get(k) != ref[k]:
                    raise ValueError('frame binding mismatch')
            key = 'member_sha256' if kind == 'clusters' else 'row'
            if r.get(key) != ref[key]:
                raise ValueError('member/row mismatch')
            if r.get('label') not in ['PERSON', 'STATIC_OBJECT', 'MIXED', 'UNKNOWN']:
                raise ValueError('invalid label')
            if r['label'] == 'PERSON' and not str(r.get('person_id', '') or '').strip():
                raise ValueError('PERSON needs actual human person_id')
    return {'records': len(seen), 'scope': 'binding/schema only; label truth and complete identity coverage require human review'}

def gt_selfcheck():
    b = {'input_sha': 'frozen'}
    c = {'sid': 's', 'mode': 'm', 'ordinal': 0, 'seq': 9, 'member_sha256': 'members'}
    base = {'schema': 1, 'kind': 'hr_sem_shadow_gt', 'source': 'human', 'reviewer': 'synthetic validator fixture',
            'created_iso': 'fixture', 'binding': b, 'clusters': [{'id': 'c', **c, 'label': 'UNKNOWN'}]}
    assert check_gt(base, b, {'c': c}, {})['records'] == 1
    bad = []
    for field, value in [('source', 'diagnostic'), ('reviewer', ''), ('binding', {'input_sha': 'wrong'})]:
        g = copy.deepcopy(base)
        g[field] = value
        bad.append(g)
    for field, value in [('seq', 10), ('member_sha256', 'wrong'), ('label', 'auto_person')]:
        g = copy.deepcopy(base)
        g['clusters'][0][field] = value
        bad.append(g)
    g = copy.deepcopy(base)
    g['clusters'].append(g['clusters'][0])
    bad.append(g)
    g = copy.deepcopy(base)
    g['clusters'][0]['label'] = 'PERSON'
    bad.append(g)
    for g in bad:
        try:
            check_gt(g, b, {'c': c}, {})
        except ValueError:
            continue
        raise AssertionError('invalid GT accepted')
    return {'accepted_synthetic_schema': 1, 'rejected_bad_cases': len(bad), 'real_human_labels_created': 0}

def prepare():
    pair = {}
    for left, right in [('pass2', 'pass3'), ('negative3', 'negative4')]:
        a, b = read(OUT / left / 'digests.json'), read(OUT / right / 'digests.json')
        assert a == b, (left, right, 'non-deterministic output')
        pair[left + '/' + right] = a
    write('determinism.json', {'pass': True, 'compared': pair, 'excluded': 'run paths and wall-clock logs only'})
    binding = read(OUT / 'pass3/binding.json')
    summaries = read(OUT / 'pass3/summary.json')
    frame_metrics = defaultdict(Counter)
    clusters = {}
    comparison = defaultdict(Counter)
    valid_bins = defaultdict(Counter)
    selected = set()
    for s in summaries:
        for fi in [0, s['frames'] // 2, s['frames'] - 1]:
            selected.add((s['sid'], s['mode'], fi))
    vote_examples = {'collision': [], 'stale': [], 'missing': [], 'association_unknown': []}
    for _, r in lines(OUT / 'pass3/votes.jsonl'):
        k = framekey(r)
        if any(t['collision_this_frame'] for t in r['original']):
            if len(vote_examples['collision']) < 5:
                vote_examples['collision'].append(r)
                selected.add(k)
        if any(t['original_human_confirmed'] and not t['normalized_old_confirmed'] for t in r['original']):
            if len(vote_examples['stale']) < 5:
                vote_examples['stale'].append(r)
                selected.add(k)
        if any(t['lost'] for t in r['original']) and len(vote_examples['missing']) < 3:
            vote_examples['missing'].append(r)
        if any(a['status'] == 'UNKNOWN_ASSOCIATION' for a in r['reference']['assigned']) and len(vote_examples['association_unknown']) < 5:
            vote_examples['association_unknown'].append(r)
    write('vote_examples.json', vote_examples)
    with (OUT / 'cluster_index.csv').open('x', encoding='utf-8-sig', newline='') as f:
        fields = ['sid', 'mode', 'ordinal', 'seq', 'ci', 'n', 'valid_n', 'invalid_n', 'old_joint', 'old_same_valid_members_joint',
                  'semantic', 'reason', 'HEAD', 'TORSO', 'LEGS', 'ARM', 'roi_overlap', 'member_sha256', 'jsonl_byte_offset']
        writer = csv.DictWriter(f, fields)
        writer.writeheader()
        for offset, r in lines(OUT / 'pass3/clusters.jsonl'):
            assert len(r['rows']) == r['n'] and len(set(r['rows'])) == r['n']
            assert r['valid_n'] == len(r['valid_rows']) == r['n'] - len(r['invalid_rows'])
            assert set(r['valid_rows']).isdisjoint(r['invalid_rows']) and r['same_member_input']
            assert r['semantic']['features']['n'] == r['valid_n']
            clusters[r['id']] = {k: r[k] for k in ['sid', 'mode', 'ordinal', 'seq', 'member_sha256']}
            k = framekey(r)
            frame_metrics[k][r['semantic']['semantic']] += 1
            comparison[(r['sid'], r['mode'])][r['old_same_valid_members']['joint'] + ' -> ' + r['semantic']['semantic']] += 1
            n = r['valid_n']
            valid_bins[(r['sid'], r['mode'])]['<60' if n < 60 else '60-199' if n < 200 else '200-399' if n < 400 else '>=400'] += 1
            if r['sid'].endswith('114422') and r['semantic']['semantic'] == 'HUMAN_EVIDENCE':
                selected.add(k)
            writer.writerow({**{k: r[k] for k in ['sid', 'mode', 'ordinal', 'seq', 'ci', 'n', 'valid_n', 'roi_overlap', 'member_sha256']},
                'invalid_n': len(r['invalid_rows']), 'old_joint': r['old']['joint'],
                'old_same_valid_members_joint': r['old_same_valid_members']['joint'],
                'semantic': r['semantic']['semantic'], 'reason': r['semantic']['reason'],
                **{k: r['semantic']['flags'][k] for k in ['HEAD', 'TORSO', 'LEGS', 'ARM']}, 'jsonl_byte_offset': offset})
    frames = {}
    point_mapping = {}
    cleanup_roi = []
    with (OUT / 'frame_index.csv').open('x', encoding='utf-8-sig', newline='') as f:
        fields = ['sid', 'mode', 'ordinal', 'seq', 'source', 'foreground', 'cleanup', 'candidates', 'small', 'unassigned',
                  'HUMAN_EVIDENCE', 'OBJECT_EVIDENCE', 'UNKNOWN', 'raw_invalid', 'missing_seq_before', 'jsonl_byte_offset']
        writer = csv.DictWriter(f, fields)
        writer.writeheader()
        for offset, r in lines(OUT / 'pass3/frames.jsonl'):
            k = framekey(r)
            frames[k] = r
            for stage in ['workspace', 'foreground', 'cleanup']:
                assert len(set(r['stage_rows'][stage])) == len(r['stage_rows'][stage])
            assert set(r['stage_rows']['cleanup']).issubset(r['stage_rows']['foreground'])
            writer.writerow({**{n: r[n] for n in ['sid', 'mode', 'ordinal', 'seq', 'missing_seq_before']},
                **{n: r['counts'][n] for n in ['source', 'foreground', 'cleanup', 'candidates', 'small', 'unassigned']},
                **{n: frame_metrics[k][n] for n in ['HUMAN_EVIDENCE', 'OBJECT_EVIDENCE', 'UNKNOWN']},
                'raw_invalid': r['invalid']['raw'], 'jsonl_byte_offset': offset})
    assert len(frames) == 1561  # 1276 raw frames; empty inspected in two branches.
    cases = []
    edge = []
    by_cluster_frame = defaultdict(dict)
    for _, r in lines(OUT / 'pass3/clusters.jsonl'):
        if framekey(r) in selected or r['sid'].endswith('114340'):
            by_cluster_frame[framekey(r)][r['ci']] = {'member_sha256': r['member_sha256'], 'flags': r['semantic']['flags']}
    for _, r in lines(OUT / 'pass3/points.jsonl'):
        k = framekey(r)
        if k in selected:
            for c in r['clusters']:
                c.update(by_cluster_frame[k][c['ci']])
            cases.append(r)
        fr = frames[k]
        for p in r['deleted']:
            pid = '/'.join([r['sid'], r['mode'], str(r['ordinal']), 'p' + str(p['row'])])
            point_mapping[pid] = {**{n: r[n] for n in ['sid', 'mode', 'ordinal', 'seq']}, 'row': p['row']}
            if r['sid'].endswith('114340') and ((p['xyz'][0] - 2.10) ** 2 + (p['xyz'][1] + .08) ** 2 <= .45 ** 2) and .1 <= p['xyz'][2] <= 2.3:
                stages = [stage for stage in ['reference_removed', 'online_supported_removed', 'cleanup_removed'] if p['row'] in fr['stage_rows'][stage]]
                item = {'id': pid, **point_mapping[pid], 'xyz': p['xyz'], 'stages': stages,
                        'source': 'diagnostic', 'label': 'UNKNOWN', 'reviewer': None, 'status': 'BLOCKED_GT'}
                edge.append(item)
                if 'cleanup_removed' in stages:
                    cleanup_roi.append(item)
                    selected.add(k)
    # Include exactly the five previous cleanup point frames, even if not previously selected.
    missing_cases = selected - set(framekey(r) for r in cases)
    if missing_cases:
        for _, r in lines(OUT / 'pass3/points.jsonl'):
            if framekey(r) in missing_cases:
                for c in r['clusters']:
                    c.update(by_cluster_frame[framekey(r)][c['ci']])
                cases.append(r)
    mid_edges = [e for e in edge if e['ordinal'] == 140 and 'reference_removed' in e['stages']]
    assert len(mid_edges) == 185 and len(cleanup_roi) == 5
    previous = read(ROOT / 'docs/human_capture/evidence/2026-10-08_new_static_sessions_r1/region_audit.json')
    old = next(s for s in previous['sessions'] if s['sid'].endswith('114340'))
    old_points = next(r['lostROI'] for r in old['rows'] if r['ordinal'] == 140)
    assert sorted(e['xyz'] for e in mid_edges) == sorted(old_points)
    write('edge_review.json', {'source': 'diagnostic', 'label_status': 'BLOCKED_GT', 'historical_185_reconciled': True,
        'cleanup_roi_points': cleanup_roi, 'points': edge})
    transforms = {}
    for s in binding['sessions']:
        transforms[s['sid']] = read(ROOT / 'docs/human_capture/evidence/2026-10-08_new_static_sessions_r1/leveling' / s['job'] / 'tls/transform.json')
    bundle = {'binding': binding, 'transforms': transforms, 'cases': cases}
    write('review_bundle.json', bundle)
    html = (OUT / 'review_template.html').read_text(encoding='utf8').replace('__PAYLOAD__', json.dumps(bundle, ensure_ascii=False).replace('</', '<\\/'))
    (OUT / 'review.html').write_text(html, encoding='utf8', newline='\n')
    write('gt_review_template.json', {'schema': 1, 'kind': 'hr_sem_shadow_gt_review_template', 'source': 'diagnostic',
        'status': 'PENDING', 'binding': binding,
        'clusters': [{'id': k, **v, 'label': 'UNKNOWN', 'person_id': None, 'reviewer': None} for k, v in clusters.items()],
        'points': [{'id': k, **v, 'label': 'UNKNOWN', 'person_id': None, 'reviewer': None} for k, v in point_mapping.items()]})
    write('audit_checks.json', {'frame_branch_rows': len(frames), 'raw_frames': 1276, 'candidate_rows': len(clusters),
        'mapping_and_validity_assertions': 'PASS', 'manual_gt_selfcheck': gt_selfcheck(),
        'comparison': {('/'.join(k)): dict(v) for k, v in comparison.items()},
        'valid_member_size_bins': {('/'.join(k)): dict(v) for k, v in valid_bins.items()},
        'review_cases': len(cases), 'edge_points': len(edge), 'mid_reference_removed': len(mid_edges), 'cleanup_roi': len(cleanup_roi)})
    print('PREPARED', len(clusters), 'clusters;', len(cases), 'review cases;', len(edge), 'edge points; two pairs of digests identical')

def validate(filename):
    template = read(OUT / 'gt_review_template.json')
    c = {r['id']: r for r in template['clusters']}
    p = {r['id']: r for r in template['points']}
    print(json.dumps(check_gt(read(Path(filename)), template['binding'], c, p), ensure_ascii=False))

if __name__ == '__main__':
    if sys.argv[1] == 'prepare':
        prepare()
    elif sys.argv[1] == 'validate':
        validate(sys.argv[2])
    elif sys.argv[1] == 'selfcheck':
        print(json.dumps(gt_selfcheck()))
