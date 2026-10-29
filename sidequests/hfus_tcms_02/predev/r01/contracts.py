"""Isolated strict source adapter. No discovery, writes, opaque-byte decoding or old main."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
EVIDENCE_ROOT = ROOT / 'docs/human_fall/evidence'


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, str(path))
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


# load() is safe at import but uses absolute next_contract/tcms names and mutates
# sys.path. Reuse its strict pure dependency with an isolated module name instead.
strict = module('predev_strict_contract', ROOT / 'sidequests/human_fusion_lab_next/pointset/r01/next_contract.py')
sha = strict.sha


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=False,
                                    separators=(',', ':')).encode()).hexdigest()


def write_new(path, obj):
    with Path(path).open('x', encoding='utf8') as stream:
        json.dump(obj, stream, ensure_ascii=False, indent=2, allow_nan=False)


def new_output(path):
    path = Path(path).resolve()
    item_prefix = '2026-10-17_hfus_tcms_02_predev_r'
    if not path.is_relative_to(EVIDENCE_ROOT.resolve()) or not path.relative_to(EVIDENCE_ROOT).parts[0].startswith(item_prefix):
        raise ValueError('Outputs must be inside this PREDEV evidence item')
    path.mkdir(parents=True, exist_ok=False)
    return path


class Source:
    def __init__(self, entry):
        self.entry = dict(entry)
        allowed_roles = {'SYNTHETIC': {'SYNTHETIC_CONTRACT','MAP_ONLY'},
                         'REUSED_DIAGNOSTIC': {'FAILURE_REGRESSION_ONLY'},
                         'REAL_DEVELOPMENT': {'A','B','C','MAP_ONLY'}}
        role = entry.get('role')
        if (not isinstance(role,str) or role not in allowed_roles.get(entry.get('kind'),set()) or
                type(entry.get('independent_test',False)) is not bool or entry.get('independent_test',False)):
            raise ValueError('D/holdout actions are disabled during predevelopment')
        self.folder = Path(entry['path']).resolve()
        self.sid = entry['sid']
        if entry['kind'] not in ('SYNTHETIC', 'REUSED_DIAGNOSTIC', 'REAL_DEVELOPMENT'):
            raise ValueError('D/holdout input is not enabled in predevelopment')
        if entry['kind'] == 'SYNTHETIC' and not self.folder.is_relative_to(EVIDENCE_ROOT / '2026-10-17_hfus_tcms_02_predev_r1'):
            raise ValueError('Synthetic fixtures must live in this isolated evidence item')
        if entry['kind'] == 'REUSED_DIAGNOSTIC':
            old_manifest = ROOT / 'docs/human_fall/evidence/2026-10-16_hfus_tcms_01_r1/run_r1/MANIFEST.json'
            allowed = json.loads(old_manifest.read_text(encoding='utf8'))['sources'].get(self.sid)
            if allowed is None or self.folder != Path(next(p for p in allowed if p.endswith('meta.json'))).parent.resolve():
                raise ValueError('Reused source is not in explicit TCMS-01 list')
            expected = {k:next(h for p,h in allowed.items() if p.endswith(n))
                        for k,n in [('meta','meta.json'),('points','points.bin')]}
            if entry.get('source_sha256') != expected:
                raise ValueError('Reused source differs from TCMS-01 binding')
        if not isinstance(entry.get('coordinate_version'), str) or not entry['coordinate_version']:
            raise ValueError('Explicit coordinate version required')
        self.binding = {k: sha(self.folder / name) for k, name in [('meta', 'meta.json'), ('points', 'points.bin')]}
        if self.binding != entry.get('source_sha256'):
            raise ValueError('Actual source hash drift')
        self.meta = json.loads((self.folder / 'meta.json').read_text(encoding='utf8'))
        strict.validate_meta(self.meta, (self.folder / 'points.bin').stat().st_size)
        layout = self.meta.get('point_layout', {})
        if (self.meta.get('session_id') != self.sid or self.folder.name != self.sid or
                layout.get('fields', [])[:3] != ['x', 'y', 'z'] or
                layout.get('dtypes', [])[:3] != ['<f4'] * 3 or
                layout.get('stride_bytes') != 28 or layout.get('endian') != 'little'):
            raise ValueError('Unsupported sid or XYZ layout; bytes 12..27 opaque')
        self.frames = self.meta['frames']
        self.buffer = None
        self.xyz = np.empty((0, 3), dtype='<f4')
        if self.meta['total_points']:
            self.buffer = np.memmap(self.folder / 'points.bin', dtype='u1', mode='r')
            self.xyz = np.ndarray((self.meta['total_points'], 3), dtype='<f4',
                                  buffer=self.buffer, strides=(28, 4))

    def close(self):
        if self.buffer is not None:
            self.buffer._mmap.close()
            self.buffer = None

    def frame(self, fi):
        if type(fi) is not int or not 0 <= fi < len(self.frames):
            raise ValueError('Invalid frame index')
        f = self.frames[fi]
        start, count = f['offset_points'], f['count_points']
        return dict(sid=self.sid, fi=fi, offset=start, source_sha256=self.binding,
                    coordinate_version=self.entry['coordinate_version'], kind=self.entry['kind'],
                    time_ns=f['stamp_sec'] * 1000000000 + f['stamp_nanosec'],
                    xyz=np.asarray(self.xyz[start:start + count], dtype=float).copy())

    def mapping(self, fi, source_row=None, global_row=None):
        if type(fi) is not int or not 0 <= fi < len(self.frames):
            raise ValueError('Invalid frame index')
        f = self.frames[fi]
        if (source_row is None) == (global_row is None):
            raise ValueError('Specify exactly one row domain')
        if type(source_row if source_row is not None else global_row) is not int:
            raise ValueError('Noninteger source row')
        row = source_row if source_row is not None else global_row - f['offset_points']
        if type(row) is not int or not 0 <= row < f['count_points']:
            raise ValueError('Cross-frame or invalid source row')
        return {'sid': self.sid, 'fi': fi, 'source_row': row,
                'global_row': f['offset_points'] + row, 'byte_offset': (f['offset_points'] + row) * 28}


def validate_members(frame, members):
    seen = set()
    for m in members:
        row = m.get('source_row')
        if (m.get('sid') != frame['sid'] or m.get('fi') != frame['fi'] or
                type(row) is not int or not 0 <= row < len(frame['xyz']) or row in seen or
                m.get('global_row') != frame['offset'] + row):
            raise ValueError('Duplicate/invalid/cross-frame member')
        seen.add(row)
    return seen


def production_geometry():
    # The existing pure package uses core.* internally. Refuse an unrelated core,
    # rather than silently binding to a same-named consumer in another experiment.
    root = ROOT / 'src/human_fall_detection'
    if 'core' in sys.modules and Path(sys.modules['core'].__file__).resolve().parent != root / 'core':
        raise ValueError('Conflicting core module')
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    from core import ground, calibration
    return ground, calibration
