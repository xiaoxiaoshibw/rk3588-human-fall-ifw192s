"""Independent raw-byte + NumPy coordinate verification; never import the repaired validator."""
import hashlib
import json
import re
from collections import Counter
import numpy as np
from audit import ROOT, OUT, R1, sha, save

html = (OUT / 'review.html').read_text('utf8')
payload = re.search(r'<script id="payload" type="application/json">([\s\S]*?)</script>', html)[1]
bundle = json.loads(payload.replace('<\\/', '</'))
sources = {}
with (R1 / 'pass3/votes.jsonl').open(encoding='utf8') as vote_file:
    votes = {f"{v['sid']}/{v['mode']}/{v['ordinal']}": v for v in (json.loads(l) for l in vote_file)}
counts = Counter()
for case in bundle['cases']:
    sid = case['sid']
    if sid not in sources:
        b = next(b for b in bundle['binding']['sessions'] if b['sid'] == sid)
        folder = ROOT / 'captures/remote' / sid
        assert sha(folder / 'meta.json') == b['source']['meta_sha256']
        assert sha(folder / 'points.bin') == b['source']['bin_sha256']
        meta = json.loads((folder / 'meta.json').read_text('utf8'))
        raw = np.memmap(folder / 'points.bin', dtype='u1', mode='r').reshape(-1, 28)
        tf = json.loads((ROOT / 'docs/human_capture/evidence/2026-10-08_new_static_sessions_r1/leveling' / b['job'] / 'tls/transform.json').read_text('utf8'))
        sources[sid] = (b, meta, raw, tf)
    b, meta, raw, tf = sources[sid]
    f = meta['frames'][case['ordinal']]
    assert case['seq'] == f['seq']
    for item, point_kind in [(c, False) for c in case['clusters']] + [(p, True) for p in case['deleted']]:
        r = item['receipt']
        rows = [item['row']] if point_kind else [p['row'] for p in item['points']]
        rid = f"{sid}/{case['mode']}/{case['ordinal']}/" + ('p' + str(rows[0]) if point_kind else str(item['ci']))
        assert r['id'] == r['review_id'] == r['vote_member_id'] == rid
        assert r['source_path'] == 'captures/remote/' + sid and r['rows'] == rows
        assert len(rows) == len(set(rows)) and all(0 <= row < f['count_points'] for row in rows)
        assert r['member_sha256'] == hashlib.sha256(json.dumps(rows, separators=(',', ':')).encode()).hexdigest()
        block = raw[np.array(rows) + f['offset_points']].copy()
        assert r['raw_member_sha256'] == hashlib.sha256(block.tobytes()).hexdigest()
        xyz = block.view('<f4').reshape(-1, 7)[:, :3].astype('float64')
        transforms = [(np.array(tf['R']).ravel(), tf['t'])]
        if b['transform']:
            transforms.append((b['transform']['rotation_row_major'], b['transform']['translation_m']))
        for matrix, t in transforms:
            xyz = np.array([matrix[j*3]*xyz[:, 0] + matrix[j*3+1]*xyz[:, 1] + matrix[j*3+2]*xyz[:, 2] + t[j] for j in range(3)]).T.astype('float32').astype('float64')
        displayed = np.array([item['xyz']] if point_kind else [p['xyz'] for p in item['points']], dtype='float64')
        assert np.array_equal(xyz, displayed)
        vote = votes[f"{sid}/{case['mode']}/{case['ordinal']}"]
        # These vote records contain only integer/bool/string/null values; stdlib canonical JSON agrees with JS.
        assert r['vote_frame_sha256'] == hashlib.sha256(json.dumps(vote, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        if not point_kind:
            assert len([v for v in vote['reference']['assigned'] if v['ci'] == item['ci']]) == 1
        counts['points' if point_kind else 'clusters'] += 1
        counts['member_coordinates'] += len(rows)
    counts['cases'] += 1
challenge = json.loads((ROOT / 'docs/human_capture/evidence/2026-10-08_hrsemshadow_review_r1/review_index_challenge.json').read_text('utf8'))['tampered_display']
(OUT / 'tampered_index.jsonl').write_text(json.dumps({'id': '/'.join(map(str, [challenge['sid'], challenge['mode'], challenge['ordinal'], challenge['ci']])), **challenge}) + '\n', encoding='utf8')
save('independent_receipts_final.json', {'counts': dict(counts), 'validator_imported': False, 'raw_content_sha_and_actual_display_coordinates': 'MATCH', 'label_truth': 'NOT_VERIFIED', 'failures': 0})
print('INDEPENDENT_RECEIPTS_PASS', dict(counts))
