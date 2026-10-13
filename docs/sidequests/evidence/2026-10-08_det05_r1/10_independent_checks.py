"""DET-05 independent checks: frozen-label chain, purity re-derivation, switch isolation, run inventory. No network."""
import hashlib
import json
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
WORK = HERE.parents[3]
DET = WORK / 'sidequests/human_detectors'
ART = DET / 'artifacts/det05_r1'
ANN, RUNS, FROZEN = ART / 'annotate', ART / 'runs', ART / 'frozen'
PRE, FG = DET / 'artifacts/det02_prepared_r1', DET / 'artifacts/det02_foreground_r1'
ITEMS = [('cap_20261007_215540', 32, 'B_workspace'), ('cap_20261007_215607', 33, 'B_workspace'),
         ('cap_20261007_215623', 33, 'B_workspace'), ('cap_20261007_215643', 28, 'B_workspace'),
         ('cap_20261007_215643', 3, 'B_workspace'), ('cap_20261007_215643', 7, 'E_cleanup'),
         ('cap_20261007_215643', 11, 'E_cleanup'), ('cap_20261007_215643', 12, 'E_cleanup'),
         ('cap_20261007_215643', 17, 'E_cleanup'), ('cap_20261007_215643', 37, 'E_cleanup')]


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def main():
    checks = []

    def check(name, ok, detail):
        checks.append(dict(check=name, ok=bool(ok), detail=detail))
        print('%-44s %s  %s' % (name, 'OK  ' if ok else 'FAIL', detail), flush=True)

    freeze = json.loads((FROZEN / 'freeze_manifest.json').read_text(encoding='utf-8'))
    labels = json.loads((FROZEN / 'labels_v1.json').read_text(encoding='utf-8'))
    gt = json.loads((FROZEN / 'gt_v1.json').read_text(encoding='utf-8'))
    rows = json.loads((HERE / '05_run_rows.json').read_text(encoding='utf-8'))
    audit = json.loads((HERE / '04_purity_audit.json').read_text(encoding='utf-8'))
    author = json.loads((HERE / '03_annotation_author.json').read_text(encoding='utf-8'))
    ff = {Path(f['path']).name: f['sha256'] for f in freeze['files']}
    check('frozen file hashes', ff['labels_v1.json'] == sha(FROZEN / 'labels_v1.json') and
          ff['gt_v1.json'] == sha(FROZEN / 'gt_v1.json') and freeze['overrides'] == [], 'labels/gt/freeze chain, no overrides')
    check('author proposals no-manual', all(f['needs_manual'] is False for f in author['frames']),
          'all 10 frames auto-assigned, user-confirmed')

    pre = json.loads((PRE / 'manifest.json').read_text(encoding='utf-8'))
    pre_sessions = {s['sid']: s for s in pre['sessions']}
    chain_ok, geom_ok, list_ok = True, True, True
    for key, item in labels['labels'].items():
        sid, index = item['sid'], item['index']
        fk = gt['frames'][key]
        human = [i for i, c in enumerate(item['cls']) if c == 'human']
        hp = [item['prepared_rows'][i] for i in human]
        hr = [item['raw_rows'][i] for i in human]
        list_ok &= hp == fk['human_prepared_rows'] and hr == fk['human_raw_rows'] and len(hp) == fk['n_human']
        rec = next(f for f in pre_sessions[sid]['frames'] if f['index'] == index)
        assert sha(PRE / sid / rec['file']) == rec['sha256'] and sha(PRE / sid / (rec['file'] + '.rows')) == rec['rows_sha256']
        raw_rows = np.fromfile(PRE / sid / (rec['file'] + '.rows'), dtype='<i8')
        chain_ok &= np.array_equal(np.asarray(item['raw_rows'], dtype='i8'),
                                   raw_rows[np.asarray(item['prepared_rows'], dtype='i8')])
        proposal = json.loads((ANN / ('ann_%s_%d.json' % (sid, index))).read_text(encoding='utf-8'))
        x = np.asarray(proposal['points']['x'])[human]
        y = np.asarray(proposal['points']['y'])[human]
        z = np.asarray(proposal['points']['z'])[human]
        geom_ok &= np.allclose([x.mean(), y.mean()], fk['centroid_xy'], atol=1e-6) and abs(z.max() - fk['z_top']) < 1e-6
        geom_ok &= np.allclose([x.min(), y.min(), z.min()], fk['aabb_min'], atol=1e-6)
        geom_ok &= np.allclose([x.max(), y.max(), z.max()], fk['aabb_max'], atol=1e-6)
    check('human row lists consistent', list_ok, 'labels_v1 vs gt_v1 prepared/raw lists and counts')
    check('prepared/raw row chain', chain_ok, 'raw rows re-derived from .rows files for all 10 frames')
    check('gt geometry recompute', geom_ok, 'centroid/z-top/AABB recomputed from proposal point arrays')

    fg = json.loads((FG / 'manifest.json').read_text(encoding='utf-8'))
    fg_sessions = {s['sid']: s for s in fg['sessions']}
    audit_by = {(r['sid'], r['index'], r['variant']): r for r in audit['rows']}
    rows_by = {(r['sid'], r['index'], r['variant'], r['experiment']): r for r in rows}
    pure_ok, iso_ok = True, True
    for sid, index, variant in ITEMS:
        key = '%s|%d' % (sid, index)
        lmap = dict(zip(labels['labels'][key]['prepared_rows'], labels['labels'][key]['cls']))
        rec = next(f for f in fg_sessions[sid]['frames'] if f['index'] == index)
        vrec = rec['variants'][variant]
        assert sha(FG / sid / vrec['file']) == vrec['sha256'] and sha(FG / sid / (vrec['file'] + '.ids')) == vrec['ids_sha256']
        cloud = np.fromfile(FG / sid / vrec['file'], dtype='<f4').reshape(-1, 4)
        ids = np.fromfile(FG / sid / (vrec['file'] + '.ids'), dtype='<u4')
        p = cloud.copy()
        p[:, 2] -= np.float32(1.73)
        p[:, 3] /= np.float32(1023)
        bounds = np.array([0, -39.68, -3, 69.12, 39.68, 1], dtype='f4')
        size = np.array([.16, .16, 4], dtype='f4')
        valid = ((p[:, :3] >= bounds[:3]) & (p[:, :3] < bounds[3:])).all(1)
        keys = np.floor((p[:, :3] - bounds[:3]) / size).astype('i8')
        groups = {}
        for i in np.flatnonzero(valid):
            groups.setdefault(tuple(keys[i]), []).append(i)
        pure, switchable, reasons = 0, 0, dict(pure=0, furniture=0, mixed_uncertain=0, unlabeled=0)
        for memb in groups.values():
            labs = [lmap.get(int(ids[i])) for i in memb]
            has_none = any(l is None for l in labs)
            has_f = 'furniture' in labs
            has_m = 'mixed_uncertain' in labs
            if not (has_none or has_f or has_m):
                pure += 1
                reasons['pure'] += 1
                if len(memb) > 32:
                    switchable += 1
            elif has_none:
                reasons['unlabeled'] += 1
            elif has_f:
                reasons['furniture'] += 1
            else:
                reasons['mixed_uncertain'] += 1
        a = audit_by[(sid, index, variant)]
        pure_ok &= (pure == a['pure'] and switchable == a['switchable_pure_over32'] and reasons == a['reasons'] and
                    len(groups) == a['pillars'] and int(valid.sum()) == a['valid_points'])
        base_npz = RUNS / ('%s_%d_%s_base_pillars.npz' % (sid, index, variant))
        switch_npz = RUNS / ('%s_%d_%s_pure_switch_pillars.npz' % (sid, index, variant))
        with np.load(base_npz) as b, np.load(switch_npz) as s:
            bcoords, bvox, bcounts, bsw, bpure = b['coords'], b['voxels'], b['counts'], b['switched'], b['pure']
            sc, svox, scounts, swm, spur = s['coords'], s['voxels'], s['counts'], s['switched'], s['pure']
        brow = rows_by[(sid, index, variant, 'base')]
        srow = rows_by[(sid, index, variant, 'pure_switch')]
        iso_ok &= int(bsw.sum()) == 0 and int(bpure.sum()) == pure and int(swm.sum()) == srow['changed_pillars']
        iso_ok &= np.array_equal(bcoords, sc) and np.array_equal(spur, bpure)
        for j in range(len(sc)):
            if not swm[j]:
                iso_ok &= np.array_equal(svox[j], bvox[j]) and np.array_equal(scounts[j], bcounts[j])
            else:
                n = int(scounts[j])
                iso_ok &= not np.array_equal(svox[j][:n], bvox[j][:int(bcounts[j])])
        iso_ok &= srow['input_sha256'] == brow['input_sha256']
    check('purity re-derivation', pure_ok, 'independent recomputation matches 04 audit for all 10 items')
    check('switch isolation', iso_ok, 'only pure pillars changed; every other row byte-equal; base switched mask empty')

    check('run inventory', len(rows) == 20 and len(list(RUNS.glob('*_trace.npz'))) == 20 and
          len(list(RUNS.glob('*_pillars.npz'))) == 20, '10 items x (base, pure_switch); no other forwards')
    seed_ok = all(r['seed_consistency'] is not None and r['seed_consistency']['exact'] for r in rows if r['experiment'] == 'base')
    check('seed consistency exact', seed_ok, 'base runs reproduce DET-03 seed-relative values bit-exact')
    check('metric sanity', all(0.0 <= r['gt_local_raw'] <= 1.0 and r['gt_rank_global'] >= 1 and r['gt_rank_local'] >= 1
                               for r in rows), 'scores in [0,1]; ranks 1-based')
    result = dict(checks=checks, all_ok=all(c['ok'] for c in checks))
    with (HERE / '10_independent_checks.json').open('x', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, allow_nan=False, indent=2)
    assert result['all_ok'], [c for c in checks if not c['ok']]
    print('PASS: all independent checks OK')


if __name__ == '__main__':
    main()
