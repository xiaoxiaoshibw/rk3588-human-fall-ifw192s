"""Read-only full Git inventory, including untracked files; never follows symlinks."""
import hashlib
import json
import pathlib
import subprocess

root = pathlib.Path(__file__).resolve().parents[2]
dest = root / 'docs/human_capture/evidence/2026-10-11_human_fusion_demo_v2_r1'
dest.mkdir(parents=True, exist_ok=True)
files = subprocess.check_output(['git', 'ls-files', '-z', '--cached', '--others', '--exclude-standard'], cwd=root).decode().split('\0')
rows = {}
for name in sorted(set(files) - {''}):
    p = root / name
    try:
        if p.is_symlink():
            rows[name] = {'symlink': str(p.readlink())}
        elif p.is_file():
            h = hashlib.sha256()
            with p.open('rb') as f:
                for block in iter(lambda: f.read(1024 * 1024), b''):
                    h.update(block)
            rows[name] = {'sha256': h.hexdigest(), 'bytes': p.stat().st_size}
        else:
            rows[name] = {'status': 'MISSING'}
    except OSError as exc:
        rows[name] = {'error': str(exc)}
result = {'branch': subprocess.check_output(['git', 'branch', '--show-current'], cwd=root).decode().strip(),
          'head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root).decode().strip(), 'files': rows}
target = dest / 'BASELINE.json'
if target.exists():
    raise RuntimeError('Baseline already exists; preserve it')
target.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
print('Baseline:', len(rows), 'files', target)
