"""DET-06 fix round: input-only sampling arms (diagnostic; no weight/upstream change).

Arms (same voxel set and per-pillar capacity semantics as the frozen pipeline):
- subvox32: in saturated pillars cap 32 points, at most one start point per 0.04x0.04x0.08 m
  sub-cell; cells ordered by representative z, even ranks if more cells than cap.
- zrank11: frozen z_rank32 selection with cap 11 (~KITTI P99 pillar count) - low-density arm.

Budget: 37 frozen items per arm + 1 z_rank32 harness control = 38 forwards per run,
76 for both arms. Separate from and additional to the 74 DET-06 evaluation forwards;
nothing here selects an operating point or a default input definition.
"""
import argparse
import json
import time
from pathlib import Path

import numpy as np
import torch

from cpu_pointpillars import load_model
from det06_eval import DEV, EMPTY_XY, load_b
from diagnose_low_scores import SamplingProbe, run_probe
from experiment import sha

ROOT = Path(__file__).resolve().parent
DET06 = ROOT / 'artifacts/det06_r1'
FIX = ROOT / 'artifacts/det06_fix_r1'
NEW_FG = ROOT / 'artifacts/det06_foreground_r1'
NEW_PRE = ROOT / 'artifacts/det06_prepared_r1'
OLD_FG = ROOT / 'artifacts/det02_foreground_r1'
OLD_PRE = ROOT / 'artifacts/det02_prepared_r1'
OLD_NEW_FG = ROOT / 'artifacts/det06_foreground_old_r1'
GT05 = ROOT / 'artifacts/det05_r1/frozen/gt_v1.json'
UP = ROOT / 'artifacts/upstream'


def subvox_select(points, ids, bounds, sub, cap):
    ids = np.asarray(ids, dtype='i8')
    q = np.floor((points[ids, :3] - bounds[:3]) / sub).astype(np.int64)
    key = q[:, 0] * 1000000 + q[:, 1] * 1000 + q[:, 2]
    seen, first = set(), []
    for i, k in zip(ids.tolist(), key.tolist()):
        if k not in seen:
            seen.add(k)
            first.append(i)
    first = np.asarray(first, dtype='i8')
    first = first[np.argsort(points[first, 2], kind='stable')]
    if len(first) > cap:
        sel = np.rint(np.linspace(0, len(first) - 1, cap)).astype(int)
        return first[sel]
    chosen, used = first.tolist(), set(first.tolist())
    if len(chosen) < cap:
        rest = ids[np.argsort(points[ids, 2], kind='stable')]
        for i in rest.tolist():
            if i not in used:
                chosen.append(i)
                used.add(i)
                if len(chosen) == cap:
                    break
    return np.asarray(chosen, dtype='i8')


def zrank_cap_select(points, ids, cap):
    ids = np.asarray(ids, dtype='i8')
    if len(ids) <= cap:
        return ids.copy()
    ordered = ids[np.argsort(points[ids, 2], kind='stable')]
    return ordered[np.rint(np.linspace(0, len(ordered) - 1, cap)).astype(int)]


class FixProbe(SamplingProbe):
    SUB = np.array([.04, .04, .08], dtype=np.float32)
    CAPS = {'subvox32': 32, 'zrank11': 11}

    def forward(self, points):
        if self.mode not in self.CAPS:
            return super().forward(points)
        assert not getattr(self, 'freeze', None), 'freeze is not supported for fix arms'
        vox, coords, counts = self.base(points)
        p = points.numpy()
        valid = np.isfinite(p).all(1) & ((p[:, :3] >= self.base.bounds[:3]) & (p[:, :3] < self.base.bounds[3:])).all(1)
        indices = np.flatnonzero(valid)
        c = np.floor((p[valid, :3] - self.base.bounds[:3]) / self.base.size).astype('i4')
        groups = {}
        for i, key in zip(indices, map(tuple, c)):
            groups.setdefault(key, []).append(i)
        cap = self.CAPS[self.mode]
        chosen, full_counts = [], []
        for j, key in enumerate(map(tuple, coords.numpy())):
            ids = np.asarray(groups[key])
            full_counts.append(len(ids))
            sel = subvox_select(p, ids, self.base.bounds, self.SUB, cap) if self.mode == 'subvox32' \
                else zrank_cap_select(p, ids, cap)
            chosen.extend(sel.tolist())
            vox[j] = 0
            vox[j, :len(sel)] = torch.from_numpy(p[sel])
            counts[j] = len(sel)
        self.selected = np.asarray(chosen, dtype='i8')
        self.last = (vox.clone(), coords.clone(), counts.clone(), np.asarray(full_counts))
        return vox, coords, counts


def items_from_gt(gt, old_gt):
    items = []
    for f in gt['test_frames']:
        items.append(dict(sid=f['sid'], index=f['index'], kind='test', xy=f['box']['centroid_xy'],
                          fg=NEW_FG, pre=NEW_PRE))
    for sid, index in DEV:
        items.append(dict(sid=sid, index=index, kind='dev', xy=old_gt['%s|%d' % (sid, index)]['centroid_xy'],
                          fg=OLD_FG, pre=OLD_PRE))
    for f in gt['empty_frames']:
        if f['sid'].startswith('cap_20261008'):
            fg, pre = NEW_FG, NEW_PRE
        elif f['sid'] == 'cap_20261007_233658':
            fg, pre = OLD_NEW_FG, OLD_PRE
        else:
            fg, pre = OLD_FG, OLD_PRE
        items.append(dict(sid=f['sid'], index=f['index'], kind='empty', xy=EMPTY_XY, fg=fg, pre=pre))
    return items


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--arm', choices=['subvox32', 'zrank11'], required=True)
    ap.add_argument('--out', type=Path, required=True)
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    gt = json.loads((DET06 / 'frozen/gt_eval_v1.json').read_text(encoding='utf-8'))
    old_gt = json.loads(GT05.read_text(encoding='utf-8'))['frames']
    items = items_from_gt(gt, old_gt)
    torch.set_num_threads(4)
    model = load_model(UP / 'epoch_160.pth', UP)
    base = model.pillar_layer.voxel_layer
    probe = FixProbe(base)
    model.pillar_layer.voxel_layer = probe
    config = dict(script_sha256=sha(Path(__file__)), checkpoint_sha256=sha(UP / 'epoch_160.pth'),
                  gt_sha256=sha(DET06 / 'frozen/gt_eval_v1.json'), arm=args.arm,
                  items=len(items), control=1, forwards_actual=len(items) + 1,
                  relation='separate from and additional to the 74 DET-06 evaluation forwards; '
                           'no operating point or default input definition is selected here',
                  subvox_cell_m=[.04, .04, .08], caps=dict(probe.CAPS))
    (args.out / 'config.json').write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding='utf-8')
    rows = []
    with (args.out / 'rows.jsonl').open('x', encoding='utf-8') as log:
        for it in items:
            cloud, ids = load_b(it['sid'], it['index'], it['fg'], it['pre'])
            tag = '%s_%d_%s' % (it['sid'][-6:], it['index'], args.arm)
            row = run_probe(model, probe, cloud, ids, it['xy'], args.out, tag, mode=args.arm, full=False)
            row.update(sid=it['sid'], index=it['index'], kind=it['kind'], arm=args.arm)
            rows.append(row)
            log.write(json.dumps(row, ensure_ascii=False) + '\n')
            log.flush()
        control = None
        cloud, ids = load_b('cap_20261008_114205', 35, NEW_FG, NEW_PRE)
        row = run_probe(model, probe, cloud, ids, [1.995786428451538, -0.298444002866745], args.out,
                        '114205_35_zrank_control', mode='z_rank32', full=False)
        ref = next(r for r in (json.loads(l) for l in
                               (DET06 / 'eval/rows.jsonl').read_text(encoding='utf-8').splitlines())
                   if r['sid'] == 'cap_20261008_114205' and r['index'] == 35 and r['arm'] == 'zrank')
        control = dict(local_anchor_max=(row['local_anchor_max'], ref['local_anchor_max']),
                       match=bool(abs(row['local_anchor_max'] - ref['local_anchor_max']) < 1e-6),
                       note='harness control: FixProbe z_rank32 path vs stored DET-06 eval row')
        assert control['match'], control
    (args.out / 'rows.json').write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding='utf-8')
    (args.out / 'control.json').write_text(json.dumps(control, ensure_ascii=False, indent=2), encoding='utf-8')
    print('DONE fix arm=%s rows=%d forwards=%d control=%s' % (args.arm, len(rows), len(items) + 1,
                                                              None if control is None else control['match']))


if __name__ == '__main__':
    main()
