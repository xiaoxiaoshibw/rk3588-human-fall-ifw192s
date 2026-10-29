"""S2 preservation: compare every baseline file; only WORKFLOW suffix and REVIEW_LOG prefix may change."""
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from bootstrap import OUT, ROOT, sha

if __name__ == '__main__':
    start = time.time(); changed = []; checked = 0
    with (OUT / 'PRESERVATION.jsonl').open('x', encoding='utf8') as log:
        for line in (OUT / 'BASELINE_FILES.jsonl').read_text(encoding='utf8').splitlines():
            rec = json.loads(line); p = ROOT / rec['path']; kind = rec['kind']
            if rec['path'] == 'docs/human_fall/WORKFLOW.md':
                actual = hashlib.sha256(p.read_bytes()[-rec['bytes']:]).hexdigest(); ok = actual == rec['sha256']; method = 'original suffix bytes'
            elif rec['path'] == 'docs/human_fall/REVIEW_LOG.md':
                actual = hashlib.sha256(p.read_bytes()[:rec['bytes']]).hexdigest(); ok = actual == rec['sha256']; method = 'original prefix bytes'
            elif kind == 'file':
                actual = sha(p) if p.is_file() else None; ok = actual == rec['sha256']; method = 'full SHA256'
            elif kind == 'symlink':
                actual = os.readlink(p) if p.is_symlink() else None; ok = actual == rec['target']; method = 'link target'
            else:
                actual = 'missing_or_nonfile' if not p.is_file() else 'file'; ok = actual == kind; method = 'type'
            log.write(json.dumps(dict(path=rec['path'], PASS=ok, method=method, actual=actual), ensure_ascii=False) + '\n')
            checked += 1
            if not ok: changed.append(dict(path=rec['path'], method=method))
            if checked % 2000 == 0:
                log.flush(); print('checked', checked, 'changed', len(changed), flush=True)
    base = json.loads((OUT / 'BASELINE_GIT.json').read_text(encoding='utf8'))
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT).decode().strip()
    branch = subprocess.check_output(['git', 'branch', '--show-current'], cwd=ROOT).decode().strip()
    result = dict(checked=checked, changed=changed, seconds=time.time() - start,
                  head=head, branch=branch,
                  git_identity_unchanged=head == base['head'] and branch == base['branch'],
                  PASS=not changed and head == base['head'] and branch == base['branch'])
    with (OUT / 'PRESERVATION_SUMMARY.json').open('x', encoding='utf8') as f:
        json.dump(result, f, indent=2)
    print(json.dumps(result))
    raise SystemExit(0 if result['PASS'] else 1)
