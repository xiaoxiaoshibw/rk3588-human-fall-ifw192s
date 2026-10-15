import json, subprocess, hashlib
from pathlib import Path
root = Path('D:/Code/ldiar')
out = Path(__file__).resolve().parent
names = subprocess.check_output(['rg', '--files', '--hidden', '--no-ignore', '-g', '!.git/**'], cwd=root, text=True, encoding='utf8').splitlines()
rows = {}; errors = []
for i, name in enumerate(names):
    p = root/name
    if p.is_relative_to(out): continue
    try:
        h = hashlib.sha256()
        with p.open('rb') as f:
            for b in iter(lambda: f.read(4<<20), b''): h.update(b)
        rows[name] = {'sha256': h.hexdigest(), 'bytes': p.stat().st_size, 'mtime_ns': p.stat().st_mtime_ns}
    except OSError as exc: errors.append({'path': name, 'error': str(exc)})
    if i % 3000 == 0: print('snapshot', i, len(names), flush=True)
git = lambda *a: subprocess.check_output(['git', '-C', str(root), *a], text=True, encoding='utf8', errors='replace').strip()
with (out/'BASELINE_BEFORE.json').open('x', encoding='utf8') as f:
    json.dump({'branch': git('branch', '--show-current'), 'head': git('rev-parse', 'HEAD'), 'status': git('status', '--short'), 'files': rows, 'errors': errors}, f, ensure_ascii=False)
for name in ['app.js', 'index.html', 'server.py']:
    if not (out/(name+'.before')).exists():
        (out/(name+'.before')).write_bytes((root/'sidequests/human_fusion_lab_next/pointset/r01'/name).read_bytes())
print('complete', len(rows), errors, flush=True)
