"""Hash every tracked/untracked workspace file (excluding data inputs) for the S2 baseline."""
import json
import os
import sys
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from bootstrap import OUT, ROOT, sha

if __name__ == '__main__':
    t0 = time.time()
    names = json.loads((OUT / 'BASELINE_LIST.json').read_text(encoding='utf8'))['files']
    out = OUT / 'BASELINE_FILES.jsonl'
    with out.open('x', encoding='utf8') as f:
        for i, name in enumerate(names):
            p = ROOT / name
            if name.startswith(('data/', 'captures/remote/', 'captures/leveled/', 'captures/registration/')):
                raise ValueError('Data unexpectedly in workspace baseline')
            rec = dict(path=name)
            if p.is_symlink():
                rec.update(kind='symlink', target=os.readlink(p))
            elif not p.is_file():
                rec.update(kind='missing_or_nonfile')
            else:
                rec.update(kind='file', bytes=p.stat().st_size, sha256=sha(p))
            f.write(json.dumps(rec, ensure_ascii=False) + '\n')
            if i % 5000 == 0:
                print(i, flush=True)
    print(json.dumps(dict(files=len(names), seconds=time.time() - t0)))
