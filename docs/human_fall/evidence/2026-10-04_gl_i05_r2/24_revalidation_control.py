"""Immutable revalidation copies; retain ALL original review revisions."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[3]
# Reconstruct every version from the now CLOSED full CLI stream in a NEW directory.
recovery=(OUT/'22_recover_review_history.py').read_text(encoding='utf8')
exec(compile(recovery.replace("TARGET=OUT/'22_review_history'",
                             "TARGET=OUT/'24_review_history_final'"),str(OUT/'22_recover_review_history.py'),'exec'),
     {'__file__':str(OUT/'22_recover_review_history.py'),'__name__':'__main__'})
old=OUT/'opencode_second_review_01'
pre=OUT/'24_check_validation'
new=OUT/'opencode_second_review_02'
pre.mkdir();new.mkdir()
scripts=sorted(old.glob('*.py'))+sorted(old.glob('*.js'))
results=[]
for path in scripts:
    if path.name.startswith('12_'):
        # End-state verifier remains useful but likewise writes only its own new directory.
        pass
    for dest in (pre,new):
        with (dest/path.name).open('xb') as f:f.write(path.read_bytes())
    command=([sys.executable,'-B','-W','error',str(pre/path.name)] if path.suffix=='.py'
             else ['node',str(pre/path.name)])
    with (pre/(path.stem+'_raw.txt')).open('xb') as log:
        completed=subprocess.run(command,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
    results.append(dict(script=path.name,sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                        command=command,exit=completed.returncode))
    print(json.dumps(results[-1]),flush=True)
with (OUT/'24_revalidation_precheck.json').open('x',encoding='utf8') as f:json.dump(results,f,indent=2)
assert all(r['exit']==0 for r in results),'independent checker precheck failed; preserve output'
