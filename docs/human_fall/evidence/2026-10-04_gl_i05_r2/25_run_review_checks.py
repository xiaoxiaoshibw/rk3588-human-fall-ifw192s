"""Once-only immutable execution of independently authored review checks."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[3]
REVIEW=OUT/'opencode_second_review_02'
script_names=[r['script'] for r in json.loads((OUT/'24_revalidation_precheck.json').read_text(encoding='utf8'))]
if any(REVIEW.glob('*.json')) or (REVIEW/'execution_manifest.json').exists():
    raise SystemExit('refuse overwriting revalidation evidence; new numbered directory required')
start={name:hashlib.sha256((REVIEW/name).read_bytes()).hexdigest() for name in script_names}
results=[]
for name in script_names:
    command=([sys.executable,'-B','-W','error',str(REVIEW/name)] if name.endswith('.py')
             else ['node',str(REVIEW/name)])
    with (REVIEW/(name+'_raw.txt')).open('xb') as log:
        r=subprocess.run(command,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
    results.append(dict(script=name,command=command,exit=r.returncode))
end={name:hashlib.sha256((REVIEW/name).read_bytes()).hexdigest() for name in script_names}
assert start==end,'review checker changed while executing'
result=dict(kind='immutable_go_review_revalidation',start_sha=start,end_sha=end,
    checker_bytes_unchanged=True,commands=results,all_exit_zero=all(r['exit']==0 for r in results),
    prior_stream='20_second_review.jsonl',prior_versions='24_review_history_final/manifest.json')
with (REVIEW/'execution_manifest.json').open('x',encoding='utf8') as f:json.dump(result,f,indent=2)
print(json.dumps(dict(all_exit_zero=result['all_exit_zero'],checker_bytes_unchanged=True,
                     outputs=[p.name for p in REVIEW.glob('*.json')],commands=len(results))))
sys.exit(int(not result['all_exit_zero']))
