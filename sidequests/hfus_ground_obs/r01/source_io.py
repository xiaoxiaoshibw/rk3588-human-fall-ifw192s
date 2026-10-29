"""只读访问 human_capture 会话（meta.json + points.bin，28B/行）。

每行仅解释前 12B（float32 x,y,z，小端）；12..27B 按现行契约保持 opaque，
不参与任何 ring/扫描线/逐点时间/强度计算。零写 data/。
"""
import hashlib
import json
from pathlib import Path

import numpy as np

STRIDE = 28


class Session:
    def __init__(self, folder):
        self.folder = Path(folder)
        self.meta = json.loads((self.folder / 'meta.json').read_text(encoding='utf8'))
        if self.meta.get('point_stride_bytes') != STRIDE:
            raise ValueError('unexpected point_stride_bytes')
        self.frames = self.meta['frames']
        self.t0 = self.frames[0]['stamp_sec'] + self.frames[0]['stamp_nanosec'] * 1e-9

    def sha256(self):
        out = {}
        for name in ('meta.json', 'points.bin'):
            h = hashlib.sha256()
            with (self.folder / name).open('rb') as f:
                for chunk in iter(lambda: f.read(1 << 22), b''):
                    h.update(chunk)
            out[name] = h.hexdigest()
        return out

    def rel_s(self, fi):
        f = self.frames[fi]
        return f['stamp_sec'] + f['stamp_nanosec'] * 1e-9 - self.t0

    def xyz(self, fi):
        f = self.frames[fi]
        n, off = int(f['count_points']), int(f['offset_points'])
        with (self.folder / 'points.bin').open('rb') as fh:
            fh.seek(off * STRIDE)
            raw = fh.read(n * STRIDE)
        if len(raw) != n * STRIDE:
            raise ValueError('truncated points.bin')
        # strides=(STRIDE,4): 每行只取 0..11B，尾 16B 不解释
        return np.ndarray((n, 3), dtype='<f4', buffer=raw, strides=(STRIDE, 4)).astype(np.float64)


def validity(p):
    # 与 r01 pipeline.py validity() 同义：valid = finite 且任一分量非零
    finite = np.isfinite(p).all(axis=1)
    return finite, finite & np.any(p != 0, axis=1)


def write_new(path, obj):
    """排他写 JSON：已存在即失败；data/ 与旧证据目录禁止。"""
    p = Path(path).absolute()
    low = str(p).lower()
    if '\\data\\' in low or '/data/' in low:
        raise ValueError('write into data/ forbidden')
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open('x', encoding='utf8') as f:
        json.dump(obj, f, ensure_ascii=False, allow_nan=False, indent=2)


def save_new_npz(path, **arrays):
    """排他写 npz。"""
    p = Path(path).absolute()
    low = str(p).lower()
    if '\\data\\' in low or '/data/' in low:
        raise ValueError('write into data/ forbidden')
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open('xb') as f:
        np.savez_compressed(f, **arrays)
