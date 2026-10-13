"""DET-06 review, NEW forwards (diagnostic only). Budget is separate from the 74 DET-06 forwards.
Stages: kitti (positive control), shift (sub-anchor alignment), zvar (z offset / range clipping /
intensity divisor / ground points). Results never select an operating point or input definition."""
import argparse
import json
from pathlib import Path

import numpy as np
import torch

from cpu_pointpillars import load_model
from det06_annotate import read_prepared
from det06_eval import load_b
from det06_metrics import final_boxes
from diagnose_low_scores import SamplingProbe, run_probe
from experiment import sha

ROOT = Path(__file__).resolve().parent
DET = ROOT / 'artifacts/det06_r1'
EVAL = DET / 'eval'
PRE = ROOT / 'artifacts/det06_prepared_r1'
FG = ROOT / 'artifacts/det06_foreground_r1'
UP = ROOT / 'artifacts/upstream'
MATCH_M = .55
ZS = 1.73
DEFAULT_BOUNDS = np.array([0, -39.68, -3, 69.12, 39.68, 1], dtype=np.float32)
WIDE_BOUNDS = np.array([0, -39.68, -1.0, 69.12, 39.68, 3.0], dtype=np.float32)
SHIFTS = [(0.0, 0.0), (0.16, 0.0), (0.0, 0.16), (0.16, 0.16)]
ARMS = [('base', 'first32'), ('zrank', 'z_rank32')]
PERSON_FRAMES = [('114205_35', 'cap_20261008_114205', 35), ('114254_116', 'cap_20261008_114254', 116),
                 ('114340_120', 'cap_20261008_114340', 120), ('114422_28', 'cap_20261008_114422', 28)]
FIXTURE_FRAME = ('fixture_114819_122', 'cap_20261008_114819', 122)
ZVAR_VARIANTS = ['zm06_clip', 'zm06_wide', 'z0_wide', 'int_kittimed', 'ground_add', 'z_m161', 'z_m185']


def footprint(points_xy, box):
    x, y, w, l, yaw = box[0], box[1], box[3], box[4], box[6]
    dx, dy = points_xy[:, 0] - x, points_xy[:, 1] - y
    c, s = np.cos(yaw), -np.sin(yaw)
    return (np.abs(c * dx + s * dy) <= w / 2) & (np.abs(-s * dx + c * dy) <= l / 2)


def local_peak(tr, centre, radius=MATCH_M):
    a, s = tr['anchors'], tr['raw_cls_scores'][:, 0]
    d = np.hypot(a[:, 0] - centre[0], a[:, 1] - centre[1])
    m = np.flatnonzero(d <= radius)
    j = m[np.argmax(s[m])]
    return dict(peak_score=float(s[j]), peak_offset=[float(a[j, 0] - centre[0]), float(a[j, 1] - centre[1])])


def record(row, tr, centre, **kw):
    out = dict(local_anchor_max=row['local_anchor_max'], final_target_max=row['stages']['clockwise']['final_target_max'],
               final_global_ped_max=row['stages']['clockwise']['final_global_ped_max'],
               global_raw_ped_max=row['global_raw_ped_max'], input_points=row['input_points'],
               model_range_dropped=row['model_range_dropped'], pillars_over32=row['pillars_over32'],
               seconds=row['seconds'], trace=row['trace'])
    out.update(local_peak(tr, centre))
    out.update(kw)
    return out


def stage_kitti(model, probe, out):
    cloud = np.fromfile(UP / '000134.bin', dtype='<f4').reshape(-1, 4)
    row = run_probe(model, probe, cloud, np.arange(len(cloud)), [10.0, 0.0], out, 'kitti_first32',
                    z=0, divisor=1, mode='first32', full=True)
    boxes = final_boxes(dict(np.load(row['trace'])), 0.10)
    top = []
    for b in boxes[:5]:
        m = footprint(cloud[:, :2], b)
        zg = float(np.percentile(cloud[m, 2], 2)) if m.sum() > 5 else None
        top.append(dict(score=float(b[7]), x=float(b[0]), y=float(b[1]), bottom_z=float(b[2]), h=float(b[5]),
                        w=float(b[3]), l=float(b[4]), yaw=float(b[6]), n_footprint=int(m.sum()),
                        ground_p2=zg, bottom_minus_ground=None if zg is None else float(b[2] - zg)))
    return dict(final_global_ped_max=row['stages']['clockwise']['final_global_ped_max'],
                n_ped_ge_0p1=int(len(boxes)), top5=top, seconds=row['seconds'], trace=row['trace'])


def stage_shift(model, probe, out, eval_by, centres):
    runs = []
    for key, sid, index in [('114205_35', PERSON_FRAMES[0][1], 35), FIXTURE_FRAME]:
        cloud, ids = load_b(sid, index, FG, PRE)
        centre0 = np.asarray(centres[key])
        for arm, mode in ARMS:
            for sx, sy in SHIFTS:
                c = cloud.copy()
                c[:, 0] += np.float32(sx)
                c[:, 1] += np.float32(sy)
                tgt = centre0 + np.array([sx, sy])
                tag = '%s_%s_s%03d_%03d' % (key, arm, round(sx * 100), round(sy * 100))
                row = run_probe(model, probe, c, ids, tgt, out, tag, mode=mode, full=False)
                rec = record(row, dict(np.load(row['trace'])), tgt, key=key, sid=sid, index=index, arm=arm,
                             shift=[sx, sy], target_shifted=tgt.tolist())
                if sx == 0 and sy == 0:
                    rec['reproduction_diff_local_anchor_max'] = abs(
                        eval_by[(sid, index, arm)]['local_anchor_max'] - row['local_anchor_max'])
                runs.append(rec)
    return runs


def stage_zvar(model, probe, out, eval_by, centres, pre_man, divisor, variant_names):
    base = probe.base
    frames = PERSON_FRAMES + [FIXTURE_FRAME]
    variants = {
        'zm06_clip': dict(z=-0.6, bounds=DEFAULT_BOUNDS, divisor=1023, ground=False),
        'zm06_wide': dict(z=-0.6, bounds=WIDE_BOUNDS, divisor=1023, ground=False),
        'z0_wide': dict(z=0.0, bounds=WIDE_BOUNDS, divisor=1023, ground=False),
        'int_kittimed': dict(z=-ZS, bounds=DEFAULT_BOUNDS, divisor=divisor, ground=False),
        'ground_add': dict(z=-ZS, bounds=DEFAULT_BOUNDS, divisor=1023, ground=True),
        'z_m161': dict(z=-1.61, bounds=DEFAULT_BOUNDS, divisor=1023, ground=False),
        'z_m185': dict(z=-1.85, bounds=DEFAULT_BOUNDS, divisor=1023, ground=False),
    }
    runs = []
    try:
        for key, sid, index in frames:
            cloud, ids = load_b(sid, index, FG, PRE)
            centre = np.asarray(centres[key])
            rec_pre = next(f for s in pre_man['sessions'] if s['sid'] == sid for f in s['frames'] if f['index'] == index)
            pts_pre, _ = read_prepared(sid, rec_pre)
            rng = np.linalg.norm(pts_pre[:, :3], axis=1)
            ground_idx = np.flatnonzero((pts_pre[:, 2] >= -.25) & (pts_pre[:, 2] < .10) & (rng >= .35) & (rng <= 25))
            for arm, mode in ARMS:
                for name in variant_names:
                    v = variants[name]
                    base.bounds = v['bounds'].copy()
                    c, cid = cloud, ids
                    if v['ground']:
                        cid = np.union1d(ids, ground_idx).astype(ids.dtype)
                        c = pts_pre[cid]
                    row = run_probe(model, probe, c, cid, centre, out, '%s_%s_%s' % (key, arm, name), mode=mode,
                                    z=v['z'], divisor=v['divisor'], full=False)
                    base.bounds = DEFAULT_BOUNDS.copy()
                    b_row = eval_by[(sid, index, arm)]
                    runs.append(record(row, dict(np.load(row['trace'])), centre, key=key, sid=sid, index=index,
                                       arm=arm, variant=name, z=v['z'], divisor=v['divisor'],
                                       n_ground_added=int(len(cid) - len(ids)),
                                       baseline_local_anchor_max=b_row['local_anchor_max'],
                                       baseline_final_target_max=b_row['stages']['clockwise']['final_target_max']))
    finally:
        base.bounds = DEFAULT_BOUNDS.copy()
    return runs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--evidence', type=Path, required=True)
    ap.add_argument('--stages', default='kitti,shift,zvar')
    ap.add_argument('--variants', default=','.join(ZVAR_VARIANTS))
    a = ap.parse_args()
    stages = a.stages.split(',')
    variant_names = a.variants.split(',')
    assert set(variant_names) <= set(ZVAR_VARIANTS)
    a.out.mkdir(parents=True, exist_ok=False)
    a.evidence.mkdir(parents=True, exist_ok=True)
    torch.set_num_threads(4)
    model = load_model(UP / 'epoch_160.pth', UP)
    base = model.pillar_layer.voxel_layer
    probe = SamplingProbe(base)
    model.pillar_layer.voxel_layer = probe
    assert np.array_equal(base.bounds, DEFAULT_BOUNDS)
    rows = [json.loads(l) for l in (EVAL / 'rows.jsonl').read_text(encoding='utf-8').splitlines()]
    eval_by = {(r['sid'], r['index'], r['arm']): r for r in rows}
    gt = json.loads((DET / 'frozen/gt_eval_v1.json').read_text(encoding='utf-8'))
    centres = {key: next(f['box']['centroid_xy'] for f in gt['test_frames'] if f['sid'] == sid and f['index'] == index)
               for key, sid, index in PERSON_FRAMES}
    centres['fixture_114819_122'] = gt['hard_negative_structures'][0]['centroid'][:2]
    kitti = np.fromfile(UP / '000134.bin', dtype='<f4').reshape(-1, 4)
    kitti_med = float(np.median(kitti[:, 3]))
    scene_med = float(np.median(np.concatenate([load_b(f['sid'], f['index'], FG, PRE)[0][:, 3]
                                                 for f in gt['test_frames']])))
    divisor = int(round(scene_med / kitti_med))
    pre_man = json.loads((PRE / 'manifest.json').read_text(encoding='utf-8'))
    expected = ((1 if 'kitti' in stages else 0)
                + (len(SHIFTS) * len(ARMS) * 2 if 'shift' in stages else 0)
                + (len(PERSON_FRAMES + [FIXTURE_FRAME]) * len(ARMS) * len(variant_names) if 'zvar' in stages else 0))
    config = dict(script_sha256=sha(Path(__file__)), checkpoint_sha256=sha(UP / 'epoch_160.pth'),
                  eval_rows_sha256=sha(EVAL / 'rows.jsonl'), stages=stages, variants=variant_names,
                  expected_forwards=expected,
                  relation_to_74_budget='separate diagnostic budget, additional to the 74 DET-06 forwards; '
                                        'not used to choose operating points or input definitions; test frames '
                                        'were already scored in DET-06, so any input change needs a new pre-registration',
                  intensity_divisor_kittimed=divisor, scene_intensity_median_raw=scene_med,
                  kitti_intensity_median=kitti_med, shifts=SHIFTS, widened_z_bounds=WIDE_BOUNDS.tolist(),
                  default_bounds=DEFAULT_BOUNDS.tolist())
    (a.out / 'config.json').write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding='utf-8')
    res = dict(config=config)
    if 'kitti' in stages:
        res['kitti'] = stage_kitti(model, probe, a.out)
    res['shift'] = stage_shift(model, probe, a.out, eval_by, centres) if 'shift' in stages else []
    res['zvar'] = stage_zvar(model, probe, a.out, eval_by, centres, pre_man, divisor, variant_names) if 'zvar' in stages else []
    actual = (1 if 'kitti' in stages else 0) + len(res['shift']) + len(res['zvar'])
    assert actual == expected, (actual, expected)
    res['forwards_actual'] = actual
    with (a.out / 'rows.jsonl').open('x', encoding='utf-8') as f:
        for r in res['shift'] + res['zvar']:
            f.write(json.dumps(r, ensure_ascii=False) + '\n')
    (a.out / 'summary.json').write_text(json.dumps(res, ensure_ascii=False, indent=2, default=float), encoding='utf-8')
    print('DONE forward forwards=%d divisor=%d' % (actual, divisor))


if __name__ == '__main__':
    main()
