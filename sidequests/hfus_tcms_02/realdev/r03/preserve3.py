"""Threaded preservation check (same baseline, same rules)."""
import hashlib, json, os, subprocess, sys, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from bootstrap import OUT, ROOT, sha

def check(rec):
    p = ROOT / rec['path']; kind = rec['kind']
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
    return dict(path=rec['path'], PASS=ok, method=method, actual=actual)

if __name__ == '__main__':
    start = time.time()
    recs = [json.loads(x) for x in (OUT / 'BASELINE_FILES.jsonl').read_text(encoding='utf8').splitlines()]
    with ThreadPoolExecutor(max_workers=12) as ex:
        results = list(ex.map(check, recs))
    changed = [dict(path=r['path'], method=r['method']) for r in results if not r['PASS']]
    with (OUT / 'PRESERVATION_FINAL.jsonl').open('x', encoding='utf8') as f:
        for r in results:
            f.write(json.dumps(r, ensure_ascii=False) + '\n')
    base = json.loads((OUT / 'BASELINE_GIT.json').read_text(encoding='utf8'))
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT).decode().strip()
    branch = subprocess.check_output(['git', 'branch', '--show-current'], cwd=ROOT).decode().strip()
    result = dict(checked=len(results), changed=changed, seconds=time.time() - start, workers=12,
                  head=head, branch=branch,
                  git_identity_unchanged=head == base['head'] and branch == base['branch'],
                  PASS=not changed and head == base['head'] and branch == base['branch'])
    (OUT / 'PRESERVATION_FINAL_SUMMARY.json').write_text(json.dumps(result, indent=2), encoding='utf8')
    print(json.dumps(result)[:500])
    raise SystemExit(0 if result['PASS'] else 1)
