"""Read-only audit runner. All writes stay beside this file."""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
R1 = ROOT / 'docs/human_capture/evidence/2026-10-08_hrsemshadow_r1'
RET = 'docs/human_capture/returns/HR-SEM-SHADOW.md'

def sha(p):
    h = hashlib.sha256()
    with p.open('rb') as f:
        for block in iter(lambda: f.read(8 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()

def save(name, obj):
    (OUT / name).write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n', encoding='utf8')

def paths():
    raw = subprocess.check_output(['git', 'ls-files', '-z', '--cached', '--others', '--exclude-standard'], cwd=ROOT)
    names = set(raw.decode('utf8').split('\0')) - {''}
    for base in ['captures', 'docs/human_capture/evidence', 'pc_apps/console/dist']:
        names.update(p.relative_to(ROOT).as_posix() for p in (ROOT / base).rglob('*') if p.is_file())
    return sorted(n for n in names if not n.startswith(OUT.relative_to(ROOT).as_posix() + '/'))

def baseline():
    files, missing = {}, []
    for n in paths():
        p = ROOT / n
        if p.is_file():
            files[n] = {'sha256': sha(p), 'bytes': p.stat().st_size}
        else:
            missing.append(n)
    ret = (ROOT / RET).read_bytes()
    save('baseline.json', {'branch': subprocess.check_output(['git', 'branch', '--show-current'], cwd=ROOT).decode().strip(),
        'head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT).decode().strip(),
        'files': files, 'missing': missing, 'return_prefix_bytes': len(ret), 'return_prefix_sha256': hashlib.sha256(ret).hexdigest()})
    (OUT / 'dirty.txt').write_bytes(subprocess.check_output(['git', 'status', '--porcelain=v1', '--untracked-files=all'], cwd=ROOT))
    (OUT / 'dirty.patch').write_bytes(subprocess.check_output(['git', 'diff', '--binary'], cwd=ROOT))
    print('baseline', len(files), 'files', sum(x['bytes'] for x in files.values()), 'bytes')

def integrity():
    b = json.loads((OUT / 'baseline.json').read_text('utf8'))
    changes = []
    for n, v in b['files'].items():
        if n == RET:
            data = (ROOT / n).read_bytes()[:b['return_prefix_bytes']]
            if hashlib.sha256(data).hexdigest() != b['return_prefix_sha256']:
                changes.append({'path': n, 'reason': 'prefix changed'})
        elif not (ROOT / n).is_file() or sha(ROOT / n) != v['sha256']:
            changes.append({'path': n, 'reason': 'changed or missing'})
    added = sorted(set(paths()) - set(b['files']) - set(b['missing']))
    save('integrity.json', {'old_files_checked': len(b['files']), 'changes': changes, 'unexpected_added': added, 'return_prefix_unchanged': not any(x['path'] == RET for x in changes), 'pass': not changes and not added})
    print('integrity', len(changes), 'changes', len(added), 'unexpected added')
    assert not changes and not added

def run(name, args):
    hashes = {str(Path(a)): sha(ROOT / a) for a in args if (ROOT / a).is_file()}
    p = subprocess.run(args, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    (OUT / (name + '.stdout.log')).write_bytes(p.stdout)
    (OUT / (name + '.stderr.log')).write_bytes(p.stderr)
    save(name + '.run.json', {'argv': args, 'cwd': str(ROOT), 'exit_code': p.returncode, 'tool_sha256': hashes,
         'stdout_sha256': hashlib.sha256(p.stdout).hexdigest(), 'stderr_sha256': hashlib.sha256(p.stderr).hexdigest()})
    print(name, 'exit', p.returncode, p.stdout.decode('utf8', errors='replace')[-1800:])
    if p.returncode:
        print(p.stderr.decode('utf8', errors='replace')[-1800:])
    return p.returncode

if __name__ == '__main__':
    if sys.argv[1] == 'baseline':
        baseline()
    elif sys.argv[1] == 'integrity':
        integrity()
    else:
        sys.exit(run(sys.argv[1], sys.argv[2:]))
