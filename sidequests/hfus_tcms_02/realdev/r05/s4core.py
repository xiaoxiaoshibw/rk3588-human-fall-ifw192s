"""S4 core: item root, inherited S3 frozen inputs, guarded writes, r01/r04 read-only reuse."""
import hashlib
import importlib.util
import json
import sys
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
OUT = ROOT / 'docs/human_fall/evidence/2026-10-17_hfus_tcms_02_s04_r1'
S3 = ROOT / 'docs/human_fall/evidence/2026-10-17_hfus_tcms_02_s03_r1'
SOURCE = ROOT / 'data/sessions/cap_20261017_113516'
R01 = ROOT / 'sidequests/hfus_tcms_02/realdev/r01'
R04 = ROOT / 'sidequests/hfus_tcms_02/realdev/r04'

ITEM = 'HFUS-TCMS-02-REALDEV-02-S04'
RAW = 'RAW/innolidar'
FROZEN = dict(meta='eeb336b895e2a147a09f23f9d69cdecb9490e020c2d91467e2ab5a84bd082ad4',
              points='254c481fb4faad01f6d30d4630b471dcbc74a25985caba0949ea6d40705f84f1',
              rows=38298918, frames=780,
              transform='8699429bcc9b85e8b9cf10a3252b8082a09174f60f7eb550cd4cc9f65bbce3de',
              transform_id='f0533fd84b9c7e1f0ec22bfcf3f7f433fb071fa73327ca9c9c881cc4aef4ab8d',
              qualification='c2c15591ef75fc7372f311c4148bd283b89ef29db45ff57d684070d9f1d167f4',
              domains='8cdceb00c0b33338ed180b711fc7157bba2a74db0c026b7f8fb00bbff22d4c81',
              domains_npz='ffae5211f275a1f4d7da1a69a2ab42cef154ee82f268a628568bc068e17d5899',
              m0='9bb0f1115919445deb259757e1dcaacfdb8fa72337c3008353d5a699df3d1c41',
              m0_map_id='56fa2141c00aebda8a9854d258be3e0c8ee44fc6f9a7d20e7704e110c1aa9553',
              s3_seal='601a7a2429a83d60327487c07629534e1ee566d58ce14f4c628aea37164a927b')


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
        raise ValueError('Output must be under the new S4 evidence root')
    if any(x.is_symlink() or x.is_junction() for x in [p, *p.parents] if x.exists()):
        raise ValueError('Output reparse/link path forbidden')
    return p


def write(path, value):
    p = guarded(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open('x', encoding='utf8', newline='\n') as f:
        if isinstance(value, str):
            f.write(value)
        else:
            json.dump(value, f, ensure_ascii=False, indent=2, allow_nan=False)


def save_array(path, **arrays):
    p = guarded(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open('xb') as f:
        np.savez_compressed(f, **arrays)


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, str(path))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def load_source():
    m = module('s4_r01_contracts', R01 / 'contracts.py')
    entry = dict(kind='REAL_DEVELOPMENT', role='B', independent_test=False, path=str(SOURCE),
                 sid='cap_20261017_113516', coordinate_version=RAW,
                 source_sha256=dict(meta=FROZEN['meta'], points=FROZEN['points']))
    src = m.Source(entry)
    if len(src.frames) != FROZEN['frames'] or sum(f['count_points'] for f in src.frames) != FROZEN['rows']:
        raise ValueError('Source denominator drift')
    return src, list(src.times)


def r01_pipeline():
    if str(R01) not in sys.path:
        sys.path.insert(0, str(R01))
    m = module('s4_r01_pipeline', R01 / 'pipeline.py')
    m.save_array, m.write_new = save_array, write
    return m


def r04_transform():
    """Read-only reuse of the S3 Transform adapter (pure math, already validated)."""
    sys.path.insert(0, str(R04))
    try:
        return module('s4_r04_transform', R04 / 'transform.py')
    finally:
        sys.path.remove(str(R04))


def validity(p):
    finite = np.isfinite(p).all(axis=1)
    return finite, finite & np.any(p != 0, axis=1)


def roles(times):
    fit = [i for i, t in enumerate(times) if t < 20.0]
    val = [i for i, t in enumerate(times) if 20.0 <= t < 28.0]
    pre = [i for i, t in enumerate(times) if 28.0 <= t < 30.0]
    return fit, val, pre


def r04_map_protocol(coordinate):
    """The exact protocol dict S3 used, so the rebuilt fingerprint can be compared byte-for-byte."""
    sys.path.insert(0, str(R04))
    try:
        m = module('s4_r04_build_m0', R04 / 'build_m0.py')
        p = m.r01_map_protocol(0.08, 0.05, 750000)
    finally:
        sys.path.remove(str(R04))
    p['coordinate'] = coordinate
    return p


def map_protocol(coordinate, tau=0.08, voxel=0.05, max_surfaces=750000):
    return dict(version='S4/RD-PROTOCOL/1 (r01 FrozenMap semantics, inherited from S3)', source_kind='REAL_DEVELOPMENT',
                role='B', independent_test=False, mode='DIAGNOSTIC', coordinate=coordinate,
                split=dict(build=[0.0, 20.0], temporal_validation=[20.0, 28.0], audit=[28.0, 30.0]),
                qualification=dict(min_surface_observations=20, min_surface_distinct_frames=5,
                                   min_surface_time_span_s=1.0, layout_consistent=None,
                                   rule='inherited from S3; S4 never re-qualifies M0'),
                map=dict(voxel_m=voxel, tau=tau, max_surfaces=max_surfaces,
                         finite_support='observed voxel AABB + nearest-centroid tau; no infinite plane'),
                ground_audit=None, budget=dict(peak_rss_bytes=2147483648, full_wall_seconds=2400),
                seed=17, physical_ground_conclusion=False)
