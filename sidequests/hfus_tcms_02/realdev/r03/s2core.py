"""S2 shared constants: item root, strict source loading, guarded writes, frame roles."""
import hashlib
import importlib.util
import json
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
OUT = ROOT / 'docs/human_fall/evidence/2026-10-17_hfus_tcms_02_s02_r1'
SOURCE = ROOT / 'data/sessions/cap_20261017_113516'
ITEM = 'HFUS-TCMS-02-REALDEV-02-S02'
RAW = 'RAW/innolidar'
FIT_END_S = 20.0
VAL_END_S = 28.0
AUDIT_END_S = 30.0


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda: f.read(16 * 1024 * 1024), b''):
            h.update(b)
    return h.hexdigest()


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def load(path):
    return json.loads(Path(path).read_text(encoding='utf8'))


def guarded(path):
    p = Path(path).absolute()
    if not p.resolve().is_relative_to(OUT.resolve()):
        raise ValueError('Output outside S2 item')
    if any(x.is_symlink() or x.is_junction() for x in [p, *p.parents] if x.exists()):
        raise ValueError('Output reparse path')
    return p


def write(path, value):
    p = guarded(path)
    with p.open('x', encoding='utf8') as f:
        if isinstance(value, str):
            f.write(value)
        else:
            json.dump(value, f, ensure_ascii=False, indent=2, allow_nan=False)


def write_png(path, fig):
    p = guarded(path)
    with p.open('xb') as f:
        fig.savefig(f, format='png', dpi=110, bbox_inches='tight')


def load_source():
    """Read-only reuse of the REALDEV strict parser; never touches its output root."""
    spec = importlib.util.spec_from_file_location('s2_r01_contracts', ROOT / 'sidequests/hfus_tcms_02/realdev/r01/contracts.py')
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    entry = dict(kind='REAL_DEVELOPMENT', role='B', independent_test=False, path=str(SOURCE),
                 sid='cap_20261017_113516', coordinate_version=RAW,
                 source_sha256=dict(meta='eeb336b895e2a147a09f23f9d69cdecb9490e020c2d91467e2ab5a84bd082ad4',
                                    points='254c481fb4faad01f6d30d4630b471dcbc74a25985caba0949ea6d40705f84f1'))
    src = m.Source(entry)
    if len(src.frames) != 780 or sum(f['count_points'] for f in src.frames) != 38298918:
        raise ValueError('Source denominator drift')
    return src, list(src.times)


def validity(p):
    finite = np.isfinite(p).all(axis=1)
    return finite, finite & np.any(p != 0, axis=1)


def roles(times):
    fit = [i for i, t in enumerate(times) if t < FIT_END_S]
    val = [i for i, t in enumerate(times) if FIT_END_S <= t < VAL_END_S]
    audit = [i for i, t in enumerate(times) if VAL_END_S <= t < AUDIT_END_S]
    return fit, val, audit
