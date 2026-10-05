"""Read-only all tracked/untracked baseline, preserving Windows symlink form."""
import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def snapshot(name):
    target = OUT / name
    if target.exists():
        raise SystemExit('No evidence overwrite: ' + str(target))
    paths = set(subprocess.check_output(
        ['git', 'ls-files', '-c', '-o', '--exclude-standard', '-z'], cwd=ROOT
    ).decode('utf-8').split('\0')) - {''}
    paths.update([
        'captures/remote/cap_20261002_163621/meta.json',
        'captures/remote/cap_20261002_163621/points.bin',
        'docs/human_fall/evidence/2026-10-03_gl_i02_r1/08_real/real_candidate.adapted.npz',
    ])
    files = {}
    for rel in sorted(paths):
        p = ROOT / rel
        try:
            if p.is_symlink():
                files[rel] = {'symlink': os.readlink(p)}
            elif p.is_file():
                files[rel] = {'sha256': sha(p), 'size': p.stat().st_size}
            else:
                files[rel] = {'missing_or_nonregular': True}
        except OSError as exc:
            # Windows catkin reparse-point representation is preserved, never repaired.
            stat = p.lstat()
            files[rel] = {'unreadable_winerror': getattr(exc, 'winerror', None),
                          'lstat_mode': stat.st_mode, 'size': stat.st_size,
                          'attributes': getattr(stat, 'st_file_attributes', None)}
    result = {
        'time': datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),
        'branch': subprocess.check_output(['git', 'branch', '--show-current'], cwd=ROOT, text=True).strip(),
        'head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        'status': subprocess.check_output(['git', 'status', '--short', '--untracked-files=all'], cwd=ROOT, text=True, encoding='utf-8'),
        'files': files,
    }
    with target.open('x', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(json.dumps({'path': str(target), 'head': result['head'], 'files': len(files)}))


if __name__ == '__main__':
    snapshot(sys.argv[1])
