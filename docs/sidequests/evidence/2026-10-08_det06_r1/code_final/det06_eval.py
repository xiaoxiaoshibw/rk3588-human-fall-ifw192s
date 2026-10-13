"""DET-06 baseline evaluation: frozen gt_eval_v1 -> base/z_rank32 forwards on test/dev/empty frames. No training."""
import argparse
import json
import time
from pathlib import Path

import numpy as np
import torch

from cpu_pointpillars import load_model
from diagnose_low_scores import SamplingProbe, run_probe
from experiment import sha

ROOT = Path(__file__).resolve().parent
WORK = ROOT.parents[1]
DET = ROOT / 'artifacts/det06_r1'
NEW_FG = ROOT / 'artifacts/det06_foreground_r1'
NEW_PRE = ROOT / 'artifacts/det06_prepared_r1'
OLD_FG = ROOT / 'artifacts/det02_foreground_r1'
OLD_PRE = ROOT / 'artifacts/det02_prepared_r1'
OLD_NEW_FG = ROOT / 'artifacts/det06_foreground_old_r1'
UP = ROOT / 'artifacts/upstream'
DET03 = WORK / 'docs/sidequests/evidence/2026-10-08_det03_r1'
GT05 = ROOT / 'artifacts/det05_r1/frozen/gt_v1.json'
DEV = [('cap_20261007_215540', 32), ('cap_20261007_215607', 33),
       ('cap_20261007_215623', 33), ('cap_20261007_215643', 28)]
EMPTY_XY = [3.68, -.48]  # DET-04 anchor-158179 reference point; only used for local/candidate bookkeeping


def load_b(sid, index, fg_root, pre_root):
    fg_root, pre_root = Path(fg_root), Path(pre_root)
    fg = json.loads((fg_root / 'manifest.json').read_text(encoding='utf-8'))
    pre = json.loads((pre_root / 'manifest.json').read_text(encoding='utf-8'))
    fs = next(s for s in fg['sessions'] if s['sid'] == sid)
    rec = next(f for f in fs['frames'] if f['index'] == index)
    if 'variants' in rec:
        rec = rec['variants']['B_workspace']
    p = fg_root / sid / rec['file']
    ip = Path(str(p) + '.ids')
    assert sha(p) == rec['sha256'] and sha(ip) == rec['ids_sha256']
    pts = np.fromfile(p, dtype='<f4').reshape(-1, 4)
    ids = np.fromfile(ip, dtype='<u4')
    assert len(pts) == rec['points'] == len(ids)
    ps = next(s for s in pre['sessions'] if s['sid'] == sid)
    pr = next(f for f in ps['frames'] if f['index'] == index)
    rawp = pre_root / sid / pr['file']
    assert sha(rawp) == pr['sha256']
    raw = np.fromfile(rawp, dtype='<f4').reshape(-1, 4)
    assert len(raw) == pr['points']
    np.testing.assert_array_equal(pts, raw[ids])
    return pts, ids


def main():
    a = argparse.ArgumentParser()
    a.add_argument('--out', type=Path, required=True)
    a.add_argument('--evidence', type=Path, required=True)
    args = a.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    gt_path = DET / 'frozen/gt_eval_v1.json'
    gt = json.loads(gt_path.read_text(encoding='utf-8'))
    old_gt = json.loads(GT05.read_text(encoding='utf-8'))['frames']
    items = []
    for f in gt['test_frames']:
        items.append(dict(sid=f['sid'], index=f['index'], kind='test', xy=f['box']['centroid_xy'],
                          fg=str(NEW_FG), pre=str(NEW_PRE)))
    for sid, index in DEV:
        items.append(dict(sid=sid, index=index, kind='dev', xy=old_gt['%s|%d' % (sid, index)]['centroid_xy'],
                          fg=str(OLD_FG), pre=str(OLD_PRE)))
    for f in gt['empty_frames']:
        if f['sid'].startswith('cap_20261008'):
            fg, pre = NEW_FG, NEW_PRE
        elif f['sid'] == 'cap_20261007_233658':
            fg, pre = OLD_NEW_FG, OLD_PRE
        else:
            fg, pre = OLD_FG, OLD_PRE
        items.append(dict(sid=f['sid'], index=f['index'], kind='empty', xy=EMPTY_XY,
                          fg=str(fg), pre=str(pre)))
    torch.set_num_threads(4)
    model = load_model(UP / 'epoch_160.pth', UP)
    assert (model.score_thr, model.nms_thr, model.nms_pre, model.max_num) == (.1, .01, 100, 50)
    base = model.pillar_layer.voxel_layer
    probe = SamplingProbe(base)
    model.pillar_layer.voxel_layer = probe
    config = dict(script_sha256=sha(Path(__file__)), plan_sha256=sha(WORK / 'docs/sidequests/DET06_PLAN.md'),
                  acceptance_sha256=sha(WORK / 'docs/sidequests/DET06_ACCEPTANCE.md'),
                  gt_sha256=sha(gt_path), checkpoint_sha256=sha(UP / 'epoch_160.pth'),
                  manifest_sha256=dict(new_foreground=sha(NEW_FG / 'manifest.json'),
                                       new_prepared=sha(NEW_PRE / 'manifest.json'),
                                       old_foreground=sha(OLD_FG / 'manifest.json'),
                                       old_prepared=sha(OLD_PRE / 'manifest.json'),
                                       old_foreground_regen=sha(OLD_NEW_FG / 'manifest.json')),
                  items=items, arms=['base=first32', 'zrank=z_rank32'], forwards=2 * len(items),
                  model_z=-1.73, intensity_divisor=1023, score=.1, nms=.01, top100=100, max50=50,
                  empty_reference_xy=EMPTY_XY, physical_verified=False)
    (args.out / 'config.json').write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding='utf-8')
    (args.evidence / '04_eval_config.json').write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding='utf-8')
    archive = {}
    for line in (DET03 / 'det03_all_r1_rows.jsonl').read_text(encoding='utf-8').splitlines():
        row = json.loads(line)
        if row['experiment'] == 'base' and row['variant'] == 'B_workspace':
            archive[(row['sid'], row['index'])] = row
    rows, summary, repro = [], [], []
    with (args.out / 'rows.jsonl').open('x', encoding='utf-8') as log:
        for it in items:
            cloud, ids = load_b(it['sid'], it['index'], it['fg'], it['pre'])
            for arm, mode in (('base', 'first32'), ('zrank', 'z_rank32')):
                tag = '%s_%d_%s' % (it['sid'][-6:], it['index'], arm)
                row = run_probe(model, probe, cloud, ids, it['xy'], args.out, tag, mode=mode, full=False)
                row.update(sid=it['sid'], index=it['index'], kind=it['kind'], arm=arm)
                if it['kind'] == 'dev' and arm == 'base':
                    arch = archive[(it['sid'], it['index'])]
                    ok = all(np.isclose(row[k], arch[k], atol=1e-5) for k in
                             ('local_anchor_max', 'raw_containing_max', 'global_raw_ped_max'))
                    repro.append(dict(sid=it['sid'], index=it['index'],
                                      local=(row['local_anchor_max'], arch['local_anchor_max']),
                                      containing=(row['raw_containing_max'], arch['raw_containing_max']),
                                      global_=(row['global_raw_ped_max'], arch['global_raw_ped_max']),
                                      match=bool(ok)))
                    assert ok, repro[-1]
                rows.append(row)
                log.write(json.dumps(row, ensure_ascii=False) + '\n')
                log.flush()
                summary.append(dict(sid=it['sid'], index=it['index'], kind=it['kind'], arm=arm,
                                    local_anchor_max=row['local_anchor_max'],
                                    raw_containing_max=row['raw_containing_max'],
                                    global_raw_ped_max=row['global_raw_ped_max'],
                                    global_raw_any_max=row['global_raw_any_max'],
                                    final_global_ped_max=row['stages']['clockwise']['final_global_ped_max'],
                                    final_target_max=row['stages']['clockwise']['final_target_max'],
                                    seconds=row['seconds']))
    check = dict(repro=repro, note='dev base arm reproduced from det03 archive B_workspace rows within 1e-5')
    (args.out / 'rows.json').write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding='utf-8')
    (args.out / 'reproduction.json').write_text(json.dumps(check, ensure_ascii=False, indent=2), encoding='utf-8')
    (args.evidence / '04_eval_summary.json').write_text(
        json.dumps(dict(rows=summary, reproduction=check), ensure_ascii=False, indent=2), encoding='utf-8')
    print('DONE items=%d rows=%d repro=%s' % (len(items), len(rows), all(r['match'] for r in repro)))


if __name__ == '__main__':
    main()
