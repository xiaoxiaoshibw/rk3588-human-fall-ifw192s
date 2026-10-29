"""S2 bootstrap: item-local evidence root, environment, source re-verification, workspace baseline."""
import hashlib
import json
import os
import platform
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
OUT = ROOT / 'docs/human_fall/evidence/2026-10-17_hfus_tcms_02_s02_r1'
ITEM = 'HFUS-TCMS-02-REALDEV-02-S02'
SOURCE = ROOT / 'data/sessions/cap_20261017_113516'
FROZEN = dict(meta='eeb336b895e2a147a09f23f9d69cdecb9490e020c2d91467e2ab5a84bd082ad4',
              points='254c481fb4faad01f6d30d4630b471dcbc74a25985caba0949ea6d40705f84f1',
              rows=38298918, frames=780)


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda: f.read(16 * 1024 * 1024), b''):
            h.update(b)
    return h.hexdigest()


def guarded(path):
    p = Path(path).absolute()
    if not p.resolve().is_relative_to(OUT.resolve()) or p.resolve() == OUT.resolve():
        raise ValueError('Output must be under this item evidence root')
    if any(x.is_symlink() or x.is_junction() for x in [p, *p.parents] if x.exists()):
        raise ValueError('Output reparse path forbidden')
    return p


def write(path, value):
    p = guarded(path)
    with p.open('x', encoding='utf8') as f:
        if isinstance(value, str):
            f.write(value)
        else:
            json.dump(value, f, ensure_ascii=False, indent=2, allow_nan=False)


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT)


def source_state():
    meta = SOURCE / 'meta.json'
    points = SOURCE / 'points.bin'
    with meta.open('rb') as f:
        m = json.loads(f.read().decode('utf8'))
    return dict(meta_sha=sha(meta), points_sha=sha(points), meta_bytes=meta.stat().st_size,
                points_bytes=points.stat().st_size, frames=len(m['frames']),
                rows=int(m['total_points']), duration_s=float(m['duration_sec']),
                created_iso=m['created_iso'], session_id=m['session_id'],
                stride=int(m['point_stride_bytes']), alias_same=(ROOT / 'captures/remote/cap_20261017_113516').resolve() == SOURCE.resolve())


if __name__ == '__main__':
    t0 = time.time()
    OUT.mkdir(exist_ok=False)
    st = source_state()
    if (st['meta_sha'], st['points_sha'], st['rows'], st['frames']) != (FROZEN['meta'], FROZEN['points'], FROZEN['rows'], FROZEN['frames']):
        raise SystemExit('SOURCE MISMATCH ' + json.dumps(st))
    files = sorted(set(git('ls-files', '-c', '-o', '--exclude-standard', '-z').decode('utf8').split('\0')) - {''})
    write(OUT / 'ENVIRONMENT.json', dict(item=ITEM, writer='single implementation writer in this session',
        executor='DSH agent (this session)', model='deepseek-flash as declared by harness; exact runtime ID not exposed; no model switch',
        platform=platform.platform(), python=sys.version, executable=sys.executable,
        strategy=dict(ground_review='RESEARCH', distance_image='RESEARCH', source_binding='ENGINEERING', browser='ENGINEERING'),
        ponytail='C:/Users/30680/.codex/skills/ponytail/SKILL.md',
        scientific_toolkit='C:/Users/30680/.codex/skills/scientific-toolkit-skill/SKILL.md',
        image_libs=dict(pillow=__import__('PIL').__version__, matplotlib=__import__('matplotlib').__version__)))
    write(OUT / 'BASELINE_GIT.json', dict(branch=git('branch', '--show-current').decode().strip(),
        head=git('rev-parse', 'HEAD').decode().strip(),
        status=git('status', '--porcelain=v1', '-uall').decode('utf8'),
        scope='all tracked and nonignored untracked files; data is input, separately hashed'))
    write(OUT / 'SOURCE_CHECK.json', dict(frozen=FROZEN, actual=st,
        purpose='REAL_DEVELOPMENT/B', taint='development_seen/dev-tainted', independent_test=False,
        decode='XYZ <f4 bytes 0..11; tail 12..27 opaque; invalid rows preserved'))
    write(OUT / 'BASELINE_LIST.json', dict(files=files, count=len(files)))
    print(json.dumps(dict(out=str(OUT), seconds=time.time() - t0, source=st), ensure_ascii=False))
