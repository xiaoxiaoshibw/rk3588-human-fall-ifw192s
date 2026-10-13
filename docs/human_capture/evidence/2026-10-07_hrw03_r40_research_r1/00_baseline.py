"""Read-only inventory including ignored/untracked files; no traversal of symlinks."""
import hashlib
import json
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).parent

def inventory():
    rows = {}
    for base, dirs, files in os.walk(ROOT, followlinks=False):
        dirs[:] = [d for d in dirs if d != '.git' and not (Path(base) / d).is_symlink()]
        for name in files:
            p = Path(base) / name
            if OUT in p.parents:
                continue
            rel = p.relative_to(ROOT).as_posix()
            if p.is_symlink():
                rows[rel] = {'symlink': os.readlink(p)}
                continue
            h = hashlib.sha256()
            try:
                with p.open('rb') as f:
                    for data in iter(lambda: f.read(1 << 20), b''):
                        h.update(data)
                rows[rel] = {'sha256': h.hexdigest(), 'bytes': p.stat().st_size}
            except OSError as e:
                rows[rel] = {'read_error': str(e)}
    return rows

if __name__ == '__main__':
    rows = inventory()
    if '--check' in __import__('sys').argv:
        before = json.loads((OUT / '00_baseline.json').read_text(encoding='utf-8'))['files']
        changed = {p: {'before': before[p], 'after': rows.get(p)} for p in before if rows.get(p) != before[p]}
        added = {p: rows[p] for p in rows if p not in before}
        result = {'changed': changed, 'added': added}
        target = OUT / '09_scope_check.json'
    else:
        result = {'branch': subprocess.check_output(['git', 'branch', '--show-current'], cwd=ROOT, text=True).strip(),
                  'head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
                  'status': subprocess.check_output(['git', 'status', '--porcelain=v1', '--untracked-files=all'], cwd=ROOT, text=True),
                  'files': rows}
        target = OUT / '00_baseline.json'
        snap = OUT / 'baseline_code' / 'pc_apps' / 'human_replay'
        snap.mkdir(parents=True, exist_ok=False)
        for name in ['human_pipe_lib.js', 'human_replay_lib.js', 'registration.js', 'registration_method.js']:
            (snap / name).write_bytes((ROOT / 'pc_apps' / 'human_replay' / name).read_bytes())
    with target.open('x', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(json.dumps({'file': str(target), 'files': len(rows), 'changed': list(result.get('changed', {})), 'added': list(result.get('added', {}))}))
