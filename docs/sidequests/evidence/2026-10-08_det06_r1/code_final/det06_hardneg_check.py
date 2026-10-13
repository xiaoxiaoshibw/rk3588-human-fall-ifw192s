"""DET-06: presence check of the three hard-negative clusters across old/new empty and C1 sessions. No model."""
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent
NEW = ROOT / 'artifacts/det06_prepared_r1'
OLD = ROOT / 'artifacts/det02_prepared_r1'
POS = {'hn0_3.65_-0.41': (3.65, -.41), 'hn1_2.12_0.66': (2.12, .66), 'hn2_1.21_0.91': (1.21, .91)}
CYL = .45


def manifest(root):
    return json.loads((root / 'manifest.json').read_text(encoding='utf-8'))


def stat(root, sid, index):
    m = manifest(root)
    s = next(x for x in m['sessions'] if x['sid'] == sid)
    rec = next(f for f in s['frames'] if f['index'] == index)
    pts = np.fromfile(root / sid / rec['file'], dtype='<f4').reshape(-1, 4)
    out = {}
    for name, xy in POS.items():
        d = np.hypot(pts[:, 0] - xy[0], pts[:, 1] - xy[1])
        mm = (d <= CYL) & (pts[:, 2] >= .15) & (pts[:, 2] <= 2.5)
        p = pts[mm]
        out[name] = dict(n=int(mm.sum()), z_max=None if not len(p) else float(round(p[:, 2].max(), 2)))
    return out


def main():
    checks = [('OLD_empty', OLD, 'cap_20261007_233658', [0, 13, 27, 40, 53]),
              ('NEW_empty', NEW, 'cap_20261008_114819', [0, 60, 122, 180, 240]),
              ('C1_114205', NEW, 'cap_20261008_114205', [122]),
              ('C1_114254', NEW, 'cap_20261008_114254', [135]),
              ('C1_114340', NEW, 'cap_20261008_114340', [140]),
              ('C1_114422', NEW, 'cap_20261008_114422', [97])]
    for title, root, sid, frames in checks:
        for i in frames:
            print(title, sid[-6:], i, json.dumps(stat(root, sid, i), ensure_ascii=False))
    m = manifest(NEW)
    s = next(x for x in m['sessions'] if x['sid'] == 'cap_20261008_114819')
    series = {k: [] for k in POS}
    for rec in s['frames']:
        pts = np.fromfile(NEW / 'cap_20261008_114819' / rec['file'], dtype='<f4').reshape(-1, 4)
        for name, xy in POS.items():
            d = np.hypot(pts[:, 0] - xy[0], pts[:, 1] - xy[1])
            series[name].append(int(((d <= CYL) & (pts[:, 2] >= .15) & (pts[:, 2] <= 2.5)).sum()))
    for name, v in series.items():
        v = np.asarray(v)
        print('SERIES', name, 'frames=%d' % len(v), 'min=%d' % v.min(), 'max=%d' % v.max(),
              'std=%.1f' % v.std(), 'median=%d' % int(np.median(v)))


if __name__ == '__main__':
    main()
