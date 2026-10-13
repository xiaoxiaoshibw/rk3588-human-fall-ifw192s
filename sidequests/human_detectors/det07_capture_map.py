"""DET-07 capture design map: 2D top-down views of the room (left: existing DET-06 person boxes;
right: planned capture positions). Offline, 0 forwards."""
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Rectangle

plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False
ROOT = Path(__file__).resolve().parent
DET06 = ROOT / 'artifacts/det06_r1'
FIX = ROOT / 'artifacts/det06_fix_r1'
PRE = ROOT / 'artifacts/det06_prepared_r1'
OUT = ROOT / 'artifacts/det07_capture_design'
SESSIONS = {'cap_20261008_114205': ('#D55E00', '中央空处静立'),
            'cap_20261008_114254': ('#0072B2', '右桌前静立'),
            'cap_20261008_114340': ('#009E73', '左隔板旁静立'),
            'cap_20261008_114422': ('#CC79A7', '中央静立举左手')}
PLANNED = [('S1 中央基准', 2.00, -0.30), ('S2 近距', 1.50, -0.40),
           ('S3 中距家具旁', 2.60, -0.70), ('S4 遮挡几何', 3.00, -0.34)]


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    gt = json.loads((FIX / 'frozen_v2/gt_eval_v2.json').read_text(encoding='utf-8'))
    man = json.loads((PRE / 'manifest.json').read_text(encoding='utf-8'))
    s = next(x for x in man['sessions'] if x['sid'] == 'cap_20261008_114819')
    rec = next(f for f in s['frames'] if f['index'] == 122)
    pts = np.fromfile(PRE / 'cap_20261008_114819' / rec['file'], dtype='<f4').reshape(-1, 4)
    fig, axes = plt.subplots(1, 2, figsize=(19, 7.2), layout='constrained')
    for ax in axes:
        ax.scatter(pts[:, 0], pts[:, 1], s=1, c='#BBBBBB', alpha=.35, linewidths=0, rasterized=True)
        ax.plot(0, 0, marker='*', ms=16, c='k')
        ax.text(0.05, -0.22, '雷达', fontsize=8)
        for name, (fx, fy) in [('固定物A', (3.65, -0.41)), ('桌子', (2.12, 0.66)), ('固定物B', (1.21, 0.91))]:
            ax.plot(fx, fy, marker='x', ms=9, mew=2, c='#666666')
            ax.text(fx + .06, fy + .06, name, fontsize=8, color='#444444')
        ax.set_xlim(-.2, 5.1)
        ax.set_ylim(-2.7, 2.3)
        ax.set_aspect('equal')
        ax.grid(alpha=.15)
        ax.set_xlabel('x (m)')
        ax.set_ylabel('y (m)')
    ax = axes[0]
    seen = set()
    for f in gt['test_frames']:
        col, name = SESSIONS[f['sid']]
        mn, mx = f['box']['aabb_min'], f['box']['aabb_max']
        ax.add_patch(Rectangle((mn[0], mn[1]), mx[0] - mn[0], mx[1] - mn[1], fill=False, ec=col, lw=1.6,
                               label=name if name not in seen else None))
        seen.add(name)
    ax.set_title('现有 DET-06：24 帧人框（俯视占位，按会话着色）')
    ax.legend(fontsize=8, loc='upper left')
    ax = axes[1]
    for name, x, y in PLANNED:
        ax.add_patch(Rectangle((x - .25, y - .25), .5, .5, fill=False, ec='#009E73', lw=2, ls='--'))
        ax.text(x + .08, y + .30, name, fontsize=9, color='#007A55')
    ax.set_title('DET-07 计划站位（绿框 0.5×0.5 m；S8 双人同场= S3 位 + S1 位）\n'
                 'S3 修正：原 (3.5,1.0) 无地面回波（雷达不可达），改为 (2.6,−0.7)')
    fig.suptitle('房间俯视 2D 图（空场 114819#122 点云为背景；坐标与 GT/计划一致）', fontsize=12)
    p = OUT / 'bev_room_person_boxes_and_planned.png'
    fig.savefig(p, dpi=130)
    plt.close(fig)
    print('wrote', p)


if __name__ == '__main__':
    main()
