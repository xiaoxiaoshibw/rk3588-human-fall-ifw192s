"""Append-only PC evidence recorder. Python 3.8; no input mutations."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from datetime import datetime, timezone, timedelta

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
RETURN = ROOT / 'docs/human_capture/returns/HR-SKELETON-OFFLINE.md'

def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(4 << 20), b''):
            h.update(block)
    return h.hexdigest()

def save(path, obj):
    with Path(path).open('x', encoding='utf8', newline='\n') as f:
        json.dump(obj, f, ensure_ascii=False, indent=2, allow_nan=False)
        f.write('\n')

def git(*args):
    return subprocess.check_output(['git', *args], cwd=str(ROOT))

def names():
    result = set(git('ls-files', '-z', '--cached', '--others', '--exclude-standard').decode('utf8').split('\0')) - {''}
    for folder in ['captures', 'docs/human_capture', 'docs/human_fall/evidence', 'pc_apps/console/dist']:
        for p in (ROOT / folder).rglob('*'):
            if p.is_file() or p.is_symlink():
                result.add(p.relative_to(ROOT).as_posix())
    return sorted(n for n in result if not n.startswith(OUT.relative_to(ROOT).as_posix() + '/'))

def info(p):
    if p.is_symlink():
        return {'symlink': os.readlink(str(p))}
    if p.is_file():
        return {'sha256': sha(p), 'bytes': p.stat().st_size}
    return {'missing': True}

def baseline():
    files = {n: info(ROOT / n) for n in names()}
    save(OUT / '00_baseline.json', {
        'time_asia_shanghai': datetime.now(timezone(timedelta(hours=8))).isoformat(),
        'branch': git('branch', '--show-current').decode().strip(),
        'head': git('rev-parse', 'HEAD').decode().strip(),
        'status': git('status', '--porcelain=v1', '-uall').decode('utf8'),
        'tracked': git('ls-files', '-z', '--cached').decode('utf8').split('\0'),
        'untracked': git('ls-files', '-z', '--others', '--exclude-standard').decode('utf8').split('\0'),
        'files': files, 'scope': 'git tracked/untracked plus ignored captures, HC docs/evidence, HF evidence and console dist; .git/current round excluded',
        'authorization': '2026-10-09 user: HR-SKELETON-OFFLINE A-F PC offline only; single writer; no agents; no production/old evidence changes',
        'ponytail': 'C:/Users/30680/.codex/skills/ponytail/SKILL.md; read; full'})
    (OUT / '00_dirty.patch').write_bytes(git('diff', '--binary'))
    print('BASELINE', len(files), sum(r.get('bytes', 0) for r in files.values()))

def run():
    name, *cmd = sys.argv[2:]
    if not name.replace('_', '').replace('-', '').isalnum():
        raise ValueError('invalid log name')
    start = datetime.now(timezone.utc).isoformat()
    clock = time.perf_counter()
    with (OUT / (name + '.stdout.log')).open('xb') as so, (OUT / (name + '.stderr.log')).open('xb') as se:
        proc = subprocess.run(cmd, cwd=str(ROOT), stdout=so, stderr=se)
    save(OUT / (name + '.run.json'), {'command': cmd, 'cwd': str(ROOT), 'start_utc': start,
        'end_utc': datetime.now(timezone.utc).isoformat(), 'runtime_s': time.perf_counter()-clock,
        'exit_code': proc.returncode, 'executable_sha256': sha(Path(cmd[0])) if Path(cmd[0]).is_file() else None,
        'source_sha256': {c: sha(ROOT / c) for c in cmd if (ROOT / c).is_file()},
        'stdout_sha256': sha(OUT / (name+'.stdout.log')), 'stderr_sha256': sha(OUT / (name+'.stderr.log'))})
    print(name, 'exit', proc.returncode)
    for suffix in ['stdout', 'stderr']:
        print((OUT / (name + '.' + suffix + '.log')).read_text('utf8', errors='replace')[-5000:])
    sys.exit(proc.returncode)

def integrity():
    b = json.loads((OUT / '00_baseline.json').read_text('utf8'))
    changed = []
    prefix = False
    for n, expected in b['files'].items():
        if ROOT / n == RETURN:
            prefix = hashlib.sha256(RETURN.read_bytes()[:expected['bytes']]).hexdigest() == expected['sha256']
            if not prefix:
                changed.append(n)
        elif info(ROOT / n) != expected:
            changed.append(n)
    new = sorted(set(names()) - set(b['files']))
    head = git('rev-parse', 'HEAD').decode().strip() == b['head']
    branch = git('branch', '--show-current').decode().strip() == b['branch']
    obj = {'checked_paths': len(b['files']), 'changed': changed, 'unexpected_new': new,
           'return_prefix_unchanged': prefix, 'head_unchanged': head, 'branch_unchanged': branch,
           'pass': not changed and not new and prefix and head and branch}
    save(OUT / sys.argv[2], obj)
    print(json.dumps(obj))
    sys.exit(0 if obj['pass'] else 1)

if __name__ == '__main__':
    {'baseline': baseline, 'run': run, 'integrity': integrity}[sys.argv[1]]()
