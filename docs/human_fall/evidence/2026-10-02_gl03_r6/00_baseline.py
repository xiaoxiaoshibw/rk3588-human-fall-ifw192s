"""GL-03 R5 pre-implementation baseline: HEAD, worktree, tracked+untracked SHA."""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def manifest():
    names = subprocess.check_output(
        ['git', 'ls-files', '-z', '--cached', '--others', '--exclude-standard'],
        cwd=ROOT).decode().split('\0')
    files = {}
    for name in names:
        if not name or name.startswith(OUT.relative_to(ROOT).as_posix() + '/'):
            continue
        try:
            if (ROOT / name).is_file():
                files[name] = sha(ROOT / name)
        except OSError as exc:
            files[name] = 'UNREADABLE:' + str(getattr(exc, 'winerror', exc.errno))
    return files


head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT).decode().strip()
status = subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT).decode()
files = manifest()
(OUT / '00_before_manifest.json').write_text(json.dumps({
    'round': 'GL-03 R5 / 2026-10-02',
    'head': head,
    'python': sys.version,
    'worktree_entries': len(status.splitlines()),
    'files': files,
}, indent=2), encoding='utf-8')
(OUT / '00_baseline.txt').write_text(
    'HEAD ' + head + '\n' + status, encoding='utf-8')
print('HEAD', head, 'files', len(files))

