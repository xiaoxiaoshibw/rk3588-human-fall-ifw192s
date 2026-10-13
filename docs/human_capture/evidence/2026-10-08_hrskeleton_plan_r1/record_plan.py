"""Document-only skeleton planning baseline and append-only integrity checks."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
APPEND = {'docs/human_capture/README.md', 'docs/human_capture/tickets/INDEX.md',
          'docs/human_capture/HUMAN_RECOGNITION_NEXT_STAGE_PLAN.md'}
NEW = {'docs/human_capture/HUMAN_SKELETON_OFFLINE_PLAN.md',
       'docs/human_capture/HR_SKELETON_OFFLINE_ACCEPTANCE.md',
       'docs/human_capture/tickets/HR-SKELETON-OFFLINE.md',
       'docs/human_capture/returns/HR-SKELETON-OFFLINE.md'}

def sha(p):
    h = hashlib.sha256()
    with p.open('rb') as f:
        for block in iter(lambda: f.read(4 << 20), b''):
            h.update(block)
    return h.hexdigest()

def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT)

def paths():
    names = set(git('ls-files', '-z', '--cached', '--others', '--exclude-standard').decode('utf8').split('\0')) - {''}
    for folder in ['captures', 'docs/human_capture', 'pc_apps/console/dist']:
        names.update(p.relative_to(ROOT).as_posix() for p in (ROOT / folder).rglob('*') if p.is_file())
    return sorted(n for n in names if not (ROOT / n).is_relative_to(OUT))

def record(p):
    if p.is_symlink():
        return {'symlink': os.readlink(p)}
    return {'sha256': sha(p), 'bytes': p.stat().st_size} if p.is_file() else {'missing': True}

def save(name, obj):
    with (OUT / name).open('x', encoding='utf8') as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
        f.write('\n')

if __name__ == '__main__' and sys.argv[1] == 'baseline':
    for n in NEW:
        assert not (ROOT / n).exists(), n
    files = {n: record(ROOT / n) for n in paths()}
    save('00_baseline.json', {'branch': git('branch', '--show-current').decode().strip(),
        'head': git('rev-parse', 'HEAD').decode().strip(), 'files': files,
        'append_only_paths': sorted(APPEND), 'allowed_new_documents': sorted(NEW)})
    (OUT / '00_dirty.txt').write_bytes(git('status', '--porcelain=v1', '-uall'))
    (OUT / '00_dirty.patch').write_bytes(git('diff', '--binary'))
    print('PLAN_BASELINE', len(files), 'paths', sum(v.get('bytes', 0) for v in files.values()), 'bytes')
elif __name__ == '__main__':
    b = json.loads((OUT / '00_baseline.json').read_text('utf8'))
    changes = []
    prefixes = {}
    for n, v in b['files'].items():
        p = ROOT / n
        if n in APPEND:
            prefixes[n] = p.is_file() and hashlib.sha256(p.read_bytes()[:v['bytes']]).hexdigest() == v['sha256']
            if not prefixes[n]:
                changes.append(n)
        elif record(p) != v:
            changes.append(n)
    added = sorted(set(paths()) - set(b['files']))
    unexpected = sorted(set(added) - NEW)
    head_same = git('rev-parse', 'HEAD').decode().strip() == b['head']
    save('integrity.json', {'old_paths_checked': len(b['files']), 'unexpected_changes': changes,
        'append_prefixes_preserved': prefixes, 'added': added, 'unexpected_added': unexpected,
        'head_unchanged': head_same, 'pass': not changes and not unexpected and head_same})
    assert not changes and not unexpected and head_same
    print('PLAN_INTEGRITY_PASS', len(b['files']), 'old paths; append prefixes intact; only named new documents')
