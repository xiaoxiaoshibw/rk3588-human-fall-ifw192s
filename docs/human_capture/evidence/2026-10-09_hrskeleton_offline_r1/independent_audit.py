"""No algorithm/R2 validator imports. Independent struct raw + scalar transform checks."""
import hashlib
import json
from pathlib import Path
import struct
import numpy as np
from record import ROOT, OUT, sha, save

def read(p):
    return json.loads(Path(p).read_text('utf8'))

def lines(p):
    with Path(p).open(encoding='utf8') as f:
        return [json.loads(l) for l in f if l.strip()]

def check():
    manifest = read(OUT/'input_manifest.json')
    split = read(OUT/'split_manifest.json')
    assert len(split['frames']) == len(manifest['entries']) == 120
    assert len({(f['sid'], f['ordinal']) for f in split['frames']}) == 100
    r1 = ROOT/'docs/human_capture/evidence/2026-10-08_hrsemshadow_r1/pass3'
    selected = {c['id']: c for c in lines(r1/'clusters.jsonl') if any(c['sid'] == w['sid'] and c['mode'] == w['branch'] and w['lo'] <= c['ordinal'] <= w['hi'] for w in split['windows'])}
    votes = {'/'.join([v['sid'], v['mode'], str(v['ordinal'])]): v for v in lines(r1/'votes.jsonl')}
    counts = {'frames': 0, 'clusters': 0, 'coordinates': 0, 'invalid_source_rows': 0}
    sources = {}
    for sid, src in manifest['sources'].items():
        folder = ROOT/'captures/remote'/sid
        assert sha(folder/'meta.json') == src['binding']['source']['meta_sha256']
        assert sha(folder/'points.bin') == src['binding']['source']['bin_sha256']
        meta = read(folder/'meta.json')
        assert meta['point_layout']['stride_bytes'] == 28
        assert not meta.get('human_annotations')
        sources[sid] = (meta, folder/'points.bin', src)
    for entry in manifest['entries']:
        assert sha(OUT/entry['file']) == entry['sha256']
        f = read(OUT/entry['file'])
        meta, binpath, src = sources[f['sid']]
        sf = meta['frames'][f['ordinal']]
        assert f['source_frame'] == sf
        with binpath.open('rb') as raw:
            for c in f['clusters']:
                rec = c['receipt'];old = selected[rec['id']]
                assert rec['rows'] == old['rows'] and c['global_rows'] == old['global_rows']
                assert len(set(rec['rows'])) == len(rec['rows'])
                h = hashlib.sha256(); xyz = []; invalid = []
                for row, global_row in zip(rec['rows'], c['global_rows']):
                    assert global_row == sf['offset_points']+row and 0 <= row < sf['count_points']
                    raw.seek(global_row*28);block = raw.read(28);assert len(block) == 28;h.update(block)
                    q = struct.unpack('<fff', block[:12])
                    if not all(np.isfinite(q)) or all(v == 0 for v in q):
                        invalid.append(row)
                    tf = src['tf'];transforms = [(sum(tf['R'], []), tf['t'])]
                    if src['binding']['transform']:
                        t = src['binding']['transform'];transforms.append((t['rotation_row_major'], t['translation_m']))
                    for rotation, translation in transforms:
                        q = tuple(float(np.float32(rotation[j*3]*q[0]+rotation[j*3+1]*q[1]+rotation[j*3+2]*q[2]+translation[j])) for j in range(3))
                    xyz.append(list(q))
                assert h.hexdigest() == rec['raw_member_sha256']
                assert np.array_equal(np.array(xyz), np.array(c['xyz']))
                assert invalid == c['invalid_source_rows']
                assert rec['xyz_sha256'] == old['xyz_sha256']
                vote = votes[f['id']]
                assert rec['vote_frame_sha256'] == hashlib.sha256(json.dumps(vote, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
                counts['clusters'] += 1;counts['coordinates'] += len(xyz);counts['invalid_source_rows'] += len(invalid)
        counts['frames'] += 1
    assert counts['clusters'] == len(selected) == 336
    a = read(OUT/'pass5/digests.json');b = read(OUT/'pass6/digests.json');assert a == b
    for n, expected in a.items():
        assert sha(OUT/'pass5'/n) == sha(OUT/'pass6'/n) == expected
    for name in ['normalized_frames.jsonl', 'nodes_raw.jsonl', 'nodes_filtered.jsonl']:
        output = lines(OUT/'pass5'/name)
        assert len(output) == 120 and [r['id'] for r in output] == [e['id'] for e in manifest['entries']]
        for r, e in zip(output, manifest['entries']):
            assert len(r['records']) == len(e['clusters'])
            for c in r['records']:
                assert c['receipt']['id'] in selected
                if name == 'normalized_frames.jsonl':
                    assert c['normalized'] is None and c['status'] == 'BLOCKED_GT'
                elif name == 'nodes_raw.jsonl':
                    assert all(not n['valid'] and n['xyz'] is None for n in c['nodes'].values())
                else:
                    assert all(not n['measurement_valid'] and n['filtered_xyz'] is None for n in c['nodes'].values())
    fixture = read(OUT/'synthetic_fixture.json');synthetic = read(OUT/'synthetic_output.json')
    assert fixture['source'] == synthetic['source'] == 'synthetic'
    norm = synthetic['normalized'];original = np.array(fixture['member']['xyz']);local = np.array(norm['xyz'])
    independent_mean = original.mean(axis=0)
    expected_local = original-np.array([independent_mean[0], independent_mean[1], 0])
    assert np.max(np.abs(local-expected_local)) < 1e-12
    inverse_error = float(np.max(np.abs(local+norm['inverse_translation_m']-original)))
    assert inverse_error <= 1e-5 and np.array_equal(local[:, 2], original[:, 2])
    assert norm['global_rows'] == [100+i for i in range(80)]
    for name, node in synthetic['nodes_raw'].items():
        assert node['valid'] and node['support_n'] == len(node['support_rows'])
        assert len(set(node['support_rows'])) == node['support_n']
        # Independent support reconstruction uses original points, not normalized algo helper.
        center = np.median(original[node['support_rows']], axis=0)
        np.testing.assert_allclose(node['xyz'], center, atol=1e-12, rtol=0)
    np.testing.assert_allclose(synthetic['nodes_raw']['CHEST']['xyz'], [10, 20, 1.05], atol=1e-12)
    assert synthetic['nodes_raw']['CHEST']['support_rows'] == list(range(32, 48))
    for n in synthetic['lifecycle'][1]['nodes'].values():
        assert not n['measurement_valid'] and n['filtered_xyz'] is None
    save(OUT/'independent_audit_final.json', {'pass': True, 'counts': counts, 'algorithm_validator_imported': False,
         'two_pass_digests_match': True, 'synthetic_explicit_chest_expected': [10, 20, 1.05],
         'synthetic_inverse_max_error_m': inverse_error, 'real_normalization_nodes': 'BLOCKED_GT',
         'human_gt_records': 0, 'third_party_review': 'NOT_RUN'})
    print('INDEPENDENT_AUDIT_PASS', counts, 'inverse', inverse_error)

if __name__ == '__main__':
    check()
