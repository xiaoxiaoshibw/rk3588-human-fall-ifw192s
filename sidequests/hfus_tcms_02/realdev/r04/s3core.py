"""S3 shared core: item root, strict source binding, guarded writes, r01 pure-function reuse.

S3 only builds a new levelling transform from the frozen S2 candidate, rebuilds M0 from
FIT rows in that coordinate version, and replays the unchanged r01 application chain.
"""
import hashlib
import importlib.util
import json
import sys
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
OUT = ROOT / 'docs/human_fall/evidence/2026-10-17_hfus_tcms_02_s03_r1'
SOURCE = ROOT / 'data/sessions/cap_20261017_113516'
R01 = ROOT / 'sidequests/hfus_tcms_02/realdev/r01'
R01_RUN = ROOT / 'docs/human_fall/evidence/2026-10-17_hfus_tcms_02_realdev_r1/ai_continuation_r2'
S2 = ROOT / 'docs/human_fall/evidence/2026-10-17_hfus_tcms_02_s02_r1'
HIST = ROOT / 'data/leveled/61cb6976b0f8479394641850d9a7c6ca/tls/transform.json'

ITEM = 'HFUS-TCMS-02-REALDEV-02-S03'
RAW = 'RAW/innolidar'
FIT_END_S, VAL_END_S, AUDIT_END_S = 20.0, 28.0, 30.0
FROZEN = dict(meta='eeb336b895e2a147a09f23f9d69cdecb9490e020c2d91467e2ab5a84bd082ad4',
              points='254c481fb4faad01f6d30d4630b471dcbc74a25985caba0949ea6d40705f84f1',
              rows=38298918, frames=780, hist_sha='01662ac7df061b42353c465ad74ab5a0d1d8452ede014c09d4a3b310f26b447a',
              s2_seal='740342ecddd2586605cb7a5f7b69fe9bf074d3f9514e50f4600db9dd21baee1d',
              s2_report='f2f2d0b44b5ffd5089c2043efc83a19d77978d42049eafa96fc2c34d92bfd5e3',
              s2_candidates='04219a3c54d4842be96d9ffeabea5459e64c7f838981f6832493f0b7fbac5673',
              s2_validation='527515de5da4fc17ee2b52324f53be791c04803c9bdfe4a34ab522376a5f2433',
              s2_domains_json='44fdc88498a7bf3d1cfce29030947bf5c9c1c32706281526d77fc7f4843ae11b',
              s2_domains='89604dceddcc934f1c2c3a8b2837d9edfe6e8486f1dc30a62eb93660b81d02bb',
              s2_protocol='3a9a78c6c734e8a214cb4b0caa5c1378ced57136f2d90f724e13073776ba10fc',
              candidate_id='C3D_03')


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
    if not p.resolve().is_relative_to(OUT.resolve()) or p.resolve() == OUT.resolve():
        raise ValueError('Output must be under the new S3 evidence root')
    if any(x.is_symlink() or x.is_junction() for x in [p, *p.parents] if x.exists()):
        raise ValueError('Output reparse/link path forbidden')
    return p


def write(path, value):
    """Exclusive JSON/str writer inside the item root (never overwrites)."""
    p = guarded(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open('x', encoding='utf8', newline='\n') as f:
        if isinstance(value, str):
            f.write(value)
        else:
            json.dump(value, f, ensure_ascii=False, indent=2, allow_nan=False)


def write_bytes(path, data):
    p = guarded(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open('xb') as f:
        f.write(data)


def save_array(path, **arrays):
    p = guarded(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open('xb') as f:
        np.savez_compressed(f, **arrays)


def write_png(path, fig):
    p = guarded(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open('xb') as f:
        fig.savefig(f, format='png', dpi=110, bbox_inches='tight')


def load_source():
    """Read-only reuse of the REALDEV strict parser; writes stay in this item."""
    spec = importlib.util.spec_from_file_location('s3_r01_contracts', R01 / 'contracts.py')
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    entry = dict(kind='REAL_DEVELOPMENT', role='B', independent_test=False, path=str(SOURCE),
                 sid='cap_20261017_113516', coordinate_version=RAW,
                 source_sha256=dict(meta=FROZEN['meta'], points=FROZEN['points']))
    src = m.Source(entry)
    if len(src.frames) != FROZEN['frames'] or sum(f['count_points'] for f in src.frames) != FROZEN['rows']:
        raise ValueError('Source denominator drift')
    return src, list(src.times)


def r01_pipeline():
    """r01 pure classes with THIS item's exclusive writers substituted for its own."""
    if str(R01) not in sys.path:
        sys.path.insert(0, str(R01))
    spec = importlib.util.spec_from_file_location('s3_r01_pipeline', R01 / 'pipeline.py')
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    m.save_array, m.write_new = save_array, write
    return m


def validity(p):
    finite = np.isfinite(p).all(axis=1)
    return finite, finite & np.any(p != 0, axis=1)


def roles(times):
    fit = [i for i, t in enumerate(times) if t < FIT_END_S]
    val = [i for i, t in enumerate(times) if FIT_END_S <= t < VAL_END_S]
    pre = [i for i, t in enumerate(times) if VAL_END_S <= t < AUDIT_END_S]
    return fit, val, pre
