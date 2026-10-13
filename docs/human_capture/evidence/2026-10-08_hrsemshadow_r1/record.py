"""PC offline records only. stdlib; never modifies input or historical evidence."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timezone, timedelta

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
RETURN = ROOT / 'docs/human_capture/returns/HR-SEM-SHADOW.md'

def sha(p):
    h = hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda: f.read(4 << 20), b''):
            h.update(b)
    return h.hexdigest()

def write(name, obj):
    with (OUT / name).open('x', encoding='utf8', newline='\n') as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
        f.write('\n')

def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT)

def snapshot():
    names = set(git('ls-files', '-z', '--cached', '--others', '--exclude-standard').decode('utf8').split('\0')) - {''}
    # Bind ignored input, frozen historical records and packaged production assets too.
    for folder in ['captures', 'docs/human_capture', 'pc_apps/console/dist']:
        for p in (ROOT / folder).rglob('*'):
            if p.is_file():
                names.add(p.relative_to(ROOT).as_posix())
    records = {}
    for name in sorted(names):
        p = ROOT / name
        if p.is_relative_to(OUT):
            continue
        if p.is_symlink():
            records[name] = {'symlink': os.readlink(p)}
        elif p.is_file():
            records[name] = {'sha256': sha(p), 'bytes': p.stat().st_size}
        else:
            records[name] = {'missing': True}
    write('00_baseline.json', {
        'time_asia_shanghai': datetime.now(timezone(timedelta(hours=8))).isoformat(),
        'branch': git('branch', '--show-current').decode().strip(),
        'head': git('rev-parse', 'HEAD').decode().strip(),
        'status': git('status', '--porcelain=v1', '-uall').decode('utf8'),
        'diff_stat': git('diff', '--stat').decode('utf8'),
        'files': records,
        'scope': 'all git tracked/untracked plus all existing captures, HC docs/evidence and console dist; current evidence excluded',
    })
    (OUT / '00_dirty.patch').write_bytes(git('diff', '--binary'))
    print('BASELINE', len(records), 'files', sum(r.get('bytes', 0) for r in records.values()), 'bytes')

def run():
    name, *cmd = sys.argv[2:]
    if not name.replace('_', '').replace('-', '').isalnum():
        raise ValueError('unsafe log name')
    start = datetime.now(timezone.utc).isoformat()
    with (OUT / (name + '.stdout.log')).open('xb') as so, (OUT / (name + '.stderr.log')).open('xb') as se:
        proc = subprocess.run(cmd, cwd=ROOT, stdout=so, stderr=se)
    write(name + '.run.json', {'command': cmd, 'cwd': str(ROOT), 'start_utc': start,
        'end_utc': datetime.now(timezone.utc).isoformat(), 'exit_code': proc.returncode,
        'tool_sha256': {str(Path(c).resolve().relative_to(ROOT)): sha(Path(c).resolve())
                        for c in cmd if Path(c).is_file() and Path(c).resolve().is_relative_to(ROOT)}})
    print(name, 'exit', proc.returncode)
    print((OUT / (name + '.stdout.log')).read_text(encoding='utf8', errors='replace')[-5000:])
    print((OUT / (name + '.stderr.log')).read_text(encoding='utf8', errors='replace')[-5000:])
    sys.exit(proc.returncode)

def integrity():
    b = json.loads((OUT / '00_baseline.json').read_text(encoding='utf8'))
    changed, checked = [], 0
    prefix = None
    for name, rec in b['files'].items():
        p = ROOT / name
        if p == RETURN:
            raw = p.read_bytes()
            n = rec['bytes']
            prefix = hashlib.sha256(raw[:n]).hexdigest() == rec['sha256']
            if not prefix:
                changed.append(name)
            continue
        current = {'symlink': os.readlink(p)} if p.is_symlink() else (
            {'sha256': sha(p), 'bytes': p.stat().st_size} if p.is_file() else {'missing': True})
        checked += 1
        if rec != current:
            changed.append(name)
    new = set(git('ls-files', '-z', '--cached', '--others', '--exclude-standard').decode('utf8').split('\0')) - {''} - set(b['files'])
    unexpected_new = sorted(n for n in new if not (ROOT / n).is_relative_to(OUT))
    result = {'checked_files': checked, 'changed': changed, 'return_prefix_unchanged': prefix,
        'unexpected_new_git_files': unexpected_new, 'head_unchanged': git('rev-parse', 'HEAD').decode().strip() == b['head'],
        'outputs': {p.relative_to(OUT).as_posix(): {'sha256': sha(p), 'bytes': p.stat().st_size}
                    for p in sorted(OUT.rglob('*')) if p.is_file() and not p.name.startswith('integrity.')},
        'pass': not changed and prefix and not unexpected_new}
    write('integrity.json', result)
    print(json.dumps({k: v for k, v in result.items() if k != 'outputs'}, ensure_ascii=False))
    sys.exit(0 if result['pass'] else 1)

if __name__ == '__main__':
    {'baseline': snapshot, 'run': run, 'integrity': integrity}[sys.argv[1]]()
