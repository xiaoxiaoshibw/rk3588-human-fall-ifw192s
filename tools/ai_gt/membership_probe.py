"""PC-only RAW views for AI weak annotation; never a human-truth generator.

No detector, foreground ledger, target box, or candidate label is read. All
visible source rows are retained. Display bounds are recorded, not fed back to
the perception pipeline. A supplied ground transform must bind this session.
"""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[2]


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def write(path, obj):
    with Path(path).open('x', encoding='utf8') as stream:
        json.dump(obj, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')


class RawSession:
    def __init__(self, path):
        self.path = Path(path).resolve()
        self.meta = json.loads((self.path / 'meta.json').read_text(encoding='utf8'))
        layout = self.meta['point_layout']
        if self.meta.get('format_version') != 1 or layout['stride_bytes'] != 28 \
                or layout['fields'][:3] != ['x', 'y', 'z'] \
                or layout['dtypes'][:3] != ['<f4'] * 3:
            raise ValueError('expected the existing 28-byte XYZ source layout')
        self.frames = self.meta['frames']
        self.binding = {name: sha(self.path / file) for name, file in
                        [('meta', 'meta.json'), ('points', 'points.bin')]}
        self.sid = self.meta['session_id']
        dtype = np.dtype({'names': ['xyz'], 'formats': [('<f4', 3)],
                          'offsets': [0], 'itemsize': 28})
        if (self.path / 'points.bin').stat().st_size != self.meta['total_points'] * 28:
            raise ValueError('source byte count mismatch')
        self.data = np.memmap(self.path / 'points.bin', mode='r', dtype=dtype)

    def frame(self, index):
        if type(index) is not int or not 0 <= index < len(self.frames):
            raise ValueError('frame index outside source')
        frame = self.frames[index]
        start, count = frame['offset_points'], frame['count_points']
        if type(start) is not int or type(count) is not int or start < 0 \
                or count < 0 or start + count > len(self.data):
            raise ValueError('frame row range outside source')
        xyz = np.asarray(self.data['xyz'][start:start + count], dtype=float)
        return xyz, np.arange(start, start + count, dtype=np.int64)

    def close(self):
        self.data._mmap.close()


def render(session, frames, out, ground=None, bounds=None):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    out = Path(out).resolve()
    evidence = (ROOT / 'docs/evidence').resolve()
    if evidence not in out.parents or any(p.is_symlink() or p.is_junction()
            for p in [out, *out.parents] if p.exists()):
        raise ValueError('a fresh ordinary evidence subdirectory is required')
    out.mkdir(parents=True, exist_ok=False)
    src = RawSession(session)
    try:
        transform = None
        if ground:
            transform = json.loads(Path(ground).read_text(encoding='utf8'))
            import sys
            current = ROOT / 'sidequests/hfus_tcms_02/realdev/current'
            sys.path.insert(0, str(current))
            from coordinates import GroundCoordinates
            coords = GroundCoordinates(ground, src.sid, src.binding)
        fig, axes = plt.subplots(len(frames), 3, figsize=(15, 4 * len(frames)),
                                 squeeze=False, constrained_layout=True)
        views = []
        for row, fi in enumerate(frames):
            points, rows = src.frame(fi)
            mask = np.isfinite(points).all(axis=1) & np.any(points != 0, axis=1)
            radius = np.linalg.norm(points, axis=1)
            mask &= (radius >= 0.8) & (radius <= 8.0)
            points, rows = points[mask], rows[mask]
            if ground:
                points = coords.points(points)
            if bounds is not None:
                mask = np.all(points >= bounds[:, 0], axis=1) \
                    & np.all(points <= bounds[:, 1], axis=1)
                points, rows = points[mask], rows[mask]
            for column, (a, b) in enumerate(((0, 1), (0, 2), (1, 2))):
                ax = axes[row, column]
                ax.scatter(points[:, a], points[:, b], s=0.7, c=points[:, 2],
                           cmap='viridis', vmin=-0.3 if ground else -2,
                           vmax=2.5, linewidths=0, rasterized=True)
                ax.set_xlabel('XYZ'[a] + ' (m)')
                ax.set_ylabel('XYZ'[b] + ' (m)')
                ax.set_title('Frame {} | {} source rows | {}{}'.format(
                    fi, len(rows), 'XYZ'[a], 'XYZ'[b]))
                ax.set_aspect('equal', adjustable='box')
                ax.grid(alpha=0.2)
                if bounds is not None:
                    ax.set_xlim(bounds[a]); ax.set_ylim(bounds[b])
            views.append(dict(fi=fi, source_rows=rows.tolist()))
        fig.suptitle(src.sid + ' | RAW-only views; no model target overlay')
        fig.savefig(out / 'VIEWS.png', dpi=140)
        plt.close(fig)
        write(out / 'VIEWS.json', dict(session=str(src.path), sid=src.sid,
            source_sha256=src.binding, frames=views, range_m=[0.8, 8.0],
            bounds=None if bounds is None else bounds.tolist(),
            coordinate='research_ground' if ground else 'RAW/innolidar',
            ground=None if ground is None else dict(path=str(Path(ground).resolve()),
                sha256=sha(ground), qualification=transform.get('qualification', {})),
            source_script_sha256=sha(__file__), model_overlay=False,
            purpose='AI weak annotation input, not independent semantic truth'))
    finally:
        src.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--session', type=Path, required=True)
    parser.add_argument('--frames', type=int, nargs='+', required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--ground', type=Path)
    parser.add_argument('--bounds', type=float, nargs=6)
    args = parser.parse_args()
    bound = None if args.bounds is None else np.asarray(args.bounds).reshape(3, 2)
    if bound is not None and (not np.isfinite(bound).all() or np.any(bound[:, 0] >= bound[:, 1])):
        parser.error('bounds must be finite increasing pairs')
    render(args.session, args.frames, args.out, args.ground, bound)
