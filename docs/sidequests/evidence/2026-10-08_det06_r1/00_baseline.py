"""DET-06 00 baseline: both trees' branch/HEAD/status + tracked/untracked/ignored SHA, inherited 3211 assets re-checked. Read-only."""
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
MAIN = Path(r'D:\Code\ldiar')
DET05 = ROOT / 'docs/sidequests/evidence/2026-10-08_det05_r1/00_baseline.json'


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def git(root, *args):
    return subprocess.check_output(['git', *args], cwd=str(root)).decode('utf-8')


def tree(root):
    files = []
    for kind, args in [('tracked', ['ls-files', '-z']),
                       ('untracked', ['ls-files', '--others', '--exclude-standard', '-z']),
                       ('ignored', ['ls-files', '--others', '--ignored', '--exclude-standard', '-z'])]:
        for name in git(root, *args).split('\0'):
            if not name:
                continue
            path = root / name
            files.append(dict(path=name.replace('\\', '/'), kind=kind,
                              sha256=sha(path) if path.is_file() else None))
    return dict(root=str(root), branch=git(root, 'branch', '--show-current').strip(),
                HEAD=git(root, 'rev-parse', 'HEAD').strip(),
                status=git(root, 'status', '--porcelain'), files=files)


def main():
    assert DET05.is_file()
    previous = json.loads(DET05.read_text(encoding='utf-8'))
    changes = []
    for row in previous['assets']:
        path = Path(row['path'])
        now = sha(path) if path.is_file() else None
        if now != row['sha256']:
            changes.append(dict(path=row['path'], expected=row['sha256'], actual=now))
    value = dict(client_date='2026-10-08', created_utc=datetime.now(timezone.utc).isoformat(),
                 original=tree(MAIN), worktree=tree(ROOT), assets=previous['assets'],
                 assets_source='inherited from DET-05 00_baseline.json (' + sha(DET05) + ')',
                 assets_changes_at_baseline=changes,
                 writer='OpenCode only (opencode-go/deepseek-v4.1-flash)',
                 skill_loader='opencode skill tool (id=ponytail, intensity=full)',
                 skill_base_dir='C:/Users/30680/.config/opencode/skills/ponytail',
                 main_tree_readonly=True)
    with (HERE / '00_baseline.json').open('x', encoding='utf-8') as f:
        json.dump(value, f, ensure_ascii=False, indent=2)
    log = ('BASELINE(DET06) at round start before implementation/artifacts; plan/acceptance v1 present and included in tree '
           'hashes; original %d, worktree %d, assets %d, asset changes %d; branch %s HEAD %s\n'
           % (len(value['original']['files']), len(value['worktree']['files']), len(value['assets']),
              len(changes), value['worktree']['branch'], value['worktree']['HEAD']))
    (HERE / '00_baseline.log').write_text(log, encoding='utf-8')
    assert not changes, changes
    print(log.strip())


if __name__ == '__main__':
    main()
