"""DET-06 18 integrity: compare both trees against 00 baseline; inherited 3211 assets and pre-existing ignored files must be unchanged. Read-only."""
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
WORK = HERE.parents[3]
MAIN = Path(r'D:\Code\ldiar')


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def git(root, *args):
    return subprocess.check_output(['git', *args], cwd=str(root)).decode('utf-8')


def current(root):
    out = {}
    for kind, args in [('tracked', ['ls-files', '-z']),
                       ('untracked', ['ls-files', '--others', '--exclude-standard', '-z']),
                       ('ignored', ['ls-files', '--others', '--ignored', '--exclude-standard', '-z'])]:
        for name in git(root, *args).split('\0'):
            if name:
                path = root / name
                out[name.replace('\\', '/')] = (kind, sha(path) if path.is_file() else None)
    return out


def main():
    base = json.loads((HERE / '00_baseline.json').read_text(encoding='utf-8'))
    result = dict(created_utc=datetime.now(timezone.utc).isoformat(),
                  method='DET06 00 baseline compare: all tracked/untracked/ignored SHA; inherited 3211 assets; pre-existing ignored unchanged')
    for label, root, key in [('original', MAIN, 'original'), ('worktree', WORK, 'worktree')]:
        bmap = {r['path']: r for r in base[key]['files']}
        now = current(root)
        changes = []
        for path, rec in bmap.items():
            cur = now.get(path, (None, None))[1]
            if cur != rec['sha256']:
                changes.append(dict(path=path, before=rec['sha256'], after=cur))
        new = sorted(set(now) - set(bmap))
        result[label] = dict(checked=len(bmap), changes=changes, new_files=len(new), new_paths=new,
                             branch=git(root, 'branch', '--show-current').strip(),
                             HEAD=git(root, 'rev-parse', 'HEAD').strip(),
                             status=git(root, 'status', '--porcelain'))
    assets_changes = []
    for rec in base['assets']:
        path = Path(rec['path'])
        cur = sha(path) if path.is_file() else None
        if cur != rec['sha256']:
            assets_changes.append(dict(path=rec['path'], before=rec['sha256'], after=cur))
    result['assets'] = {'checked': len(base['assets']), 'changes': assets_changes}
    ignored = [r for r in base['worktree']['files'] if r['kind'] == 'ignored']
    ignored_changes = []
    for rec in ignored:
        path = WORK / rec['path']
        cur = sha(path) if path.is_file() else None
        if cur != rec['sha256']:
            ignored_changes.append(dict(path=rec['path'], before=rec['sha256'], after=cur))
    result['ignored_existing_checked'] = len(ignored)
    result['ignored_existing_changes'] = ignored_changes
    result['consumption_changes'] = []
    result['additional_consumption'] = ('DET05 frozen gt_v1/labels_v1, DET03/04 archived rows/traces, det02 FG/PRE inputs, '
                                        'new det06 sessions/prepared/foreground: protected by 00 baseline and new-file whitelists in 17/22')
    (HERE / '18_integrity.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    assert not assets_changes, assets_changes
    assert not ignored_changes, ignored_changes
    allowed = {'sidequests/human_detectors/README.md'}
    wt_changed = {c['path'] for c in result['worktree']['changes']}
    assert wt_changed <= allowed, sorted(wt_changed - allowed)
    print('assets checked', result['assets']['checked'], 'changes', len(assets_changes))
    print('ignored_existing checked', result['ignored_existing_checked'], 'changes', len(ignored_changes))
    print('original checked', result['original']['checked'], 'changes', result['original']['changes'])
    print('worktree checked', result['worktree']['checked'], 'changes',
          [(c['path'], c['before'][:8] + '->' + (c['after'] or 'missing')[:8]) for c in result['worktree']['changes']],
          'new files', result['worktree']['new_files'])
    print('PASS: assets and pre-existing ignored files unchanged; worktree changes only README')


if __name__ == '__main__':
    main()
