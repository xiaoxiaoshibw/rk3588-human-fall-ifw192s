"""DET-06 fix round metrics: compare base / z_rank32 / subvox32 / zrank11 under the same protocol.
Offline (reads traces only). Budget: 0 forwards."""
import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

from det06_metrics import TAUS, trace_path
from det06_review_offline import BUDGETS, fp_locations, hits, loso, operating, pooled_ops, sweep

plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False
ROOT = Path(__file__).resolve().parent
D06 = ROOT / 'artifacts/det06_r1'
FIX = ROOT / 'artifacts/det06_fix_r1'
ARMS = ['base', 'zrank', 'subvox32', 'zrank11']


def load_arm(arm):
    if arm in ('base', 'zrank'):
        rows = [r for r in (json.loads(l) for l in
                            (D06 / 'eval/rows.jsonl').read_text(encoding='utf-8').splitlines()) if r['arm'] == arm]
    else:
        rows = [json.loads(l) for l in (FIX / ('eval_%s/rows.jsonl' % arm)).read_text(encoding='utf-8').splitlines()]
    return {(r['sid'], r['index'], arm): dict(np.load(trace_path(r))) for r in rows}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', type=Path, required=True)
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=False)
    gt = json.loads((D06 / 'frozen/gt_eval_v1.json').read_text(encoding='utf-8'))
    test, empty = gt['test_frames'], gt['empty_frames']
    structs = [tuple(s['centroid'][:2]) for s in gt['hard_negative_structures']]
    res = {'note': 'fix round, offline; pooled budget = per-frame FP over test+empty; test-only budget also shown; '
                   'no operating point is selected by this script'}
    curves = {}
    for arm in ARMS:
        traces = load_arm(arm)
        t = sweep(test, traces, arm)
        ptab, pops = pooled_ops(test, empty, traces, arm)
        empty_cnt = {str(tau): fp_locations(empty, traces, arm, structs, tau, False)[0]
                     for tau in (0.20, 0.25, 0.35, 0.45, 0.55)}
        res[arm] = dict(test_only_ops=operating(t), pooled_ops=pops, loso=loso(test, traces, arm),
                        empty_fp_per_frame=empty_cnt,
                        table={k: v for k, v in t.items()},
                        pooled_table={k: v for k, v in ptab.items()})
        curves[arm] = [(v['fp_per_frame_pooled'], v['recall_center']) for v in ptab.values()]
    fig, ax = plt.subplots(figsize=(7.5, 4.8), layout='constrained')
    for arm in ARMS:
        pts = sorted(curves[arm])
        ax.plot([p[0] for p in pts], [p[1] for p in pts], marker='o', ms=3.5, lw=1.6, label=arm)
    for b in BUDGETS:
        ax.axvline(b, color='k', ls=':', lw=.8)
    ax.set(xlabel='FP / frame（test+empty 合并池）', ylabel='recall（中心 ≤0.55 m）',
           title='DET-06 修复轮：四臂 PR（合并口径，24 人框帧 + 9 空场帧）')
    ax.grid(alpha=.2)
    ax.legend()
    fig.savefig(a.out / 'fig_fix_pr.png', dpi=130)
    plt.close(fig)
    (a.out / 'summary.json').write_text(json.dumps(res, ensure_ascii=False, indent=2, default=float), encoding='utf-8')
    for arm in ARMS:
        p = res[arm]['pooled_ops']
        op = {k: (None if v is None else (v['tau'], round(v['recall_center'], 3), round(v['fp_per_frame_pooled'], 3)))
              for k, v in p.items()}
        print(arm, 'pooled ops', op)
    print('DONE fix metrics', a.out)


if __name__ == '__main__':
    main()
