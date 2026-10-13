"""Offline contact sheets. Views are evidence, never anatomical/person labels."""
import json
import sys
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from prepare import ROOT, OUT, frame_xyz


def main(sid):
    report = json.loads((OUT/(sid+'_leveling.json')).read_text(encoding='utf8'))
    if report['recommended'] is None:
        raise ValueError('no accepted offline recommendation')
    transform = report['estimators'][report['recommended']]
    R, t = np.array(transform['R']), np.array(transform['t'])
    directory = ROOT/'captures/remote'/sid
    meta = json.loads((directory/'meta.json').read_text(encoding='utf8'))
    indices = np.linspace(0, len(meta['frames'])-1, 16, dtype=int)
    for name, axes in [('side_xz', (0, 2)), ('front_yz', (1, 2)), ('top_xy', (0, 1))]:
        fig, grid = plt.subplots(4, 4, figsize=(16, 12))
        for ax, i in zip(grid.flat, indices):
            p = frame_xyz(directory, meta, int(i)) @ R.T + t
            p = p[(p[:,0] > -.5) & (p[:,0] < 6) & (abs(p[:,1]) < 3) & (p[:,2] > .08) & (p[:,2] < 2.5)]
            ax.scatter(p[:,axes[0]], p[:,axes[1]], s=.5, c=p[:,2], cmap='turbo', vmin=0, vmax=2)
            ax.set_xlim((-3,3) if axes[0] == 1 else (-.5,6))
            ax.set_ylim((-3,3) if axes[1] == 1 else (0,2.5))
            seconds = meta['frames'][i]['bag_time_sec'] - meta['frames'][0]['bag_time_sec']
            ax.set_title('frame %d / %.2fs / %d points' % (i, seconds, len(p)), fontsize=10)
            ax.grid(alpha=.2)
        fig.suptitle(sid+' leveled / '+name+' / NO BACKGROUND REMOVAL YET')
        fig.tight_layout()
        target = OUT/(sid+'_'+name+'_leveled.png')
        if target.exists():
            raise FileExistsError(target)
        fig.savefig(target, dpi=130); plt.close(fig)
    print(sid, 'contact sheets written')


if __name__ == '__main__':
    for sid in sys.argv[1:]:
        main(sid)
