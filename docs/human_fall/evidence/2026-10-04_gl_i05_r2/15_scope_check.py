"""Verify frozen tracked+untracked baseline; administrative files are explicit."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[3]
before=json.loads((OUT/'00_before_baseline.json').read_text(encoding='utf8'))
after=json.loads((OUT/sys.argv[1]).read_text(encoding='utf8'))
allowed={'docs/human_fall/'+name for name in ('README.md','DISPATCH.md','WORKFLOW.md',
    'returns/GL-I05.md','REVIEW_LOG.md','CLI_RECOVERY.md','GLI05_TASK.md','GLI05_ACCEPTANCE.md')}
prefix=OUT.relative_to(ROOT).as_posix()+'/'
changes=[p for p,v in before['files'].items() if after['files'].get(p)!=v]
unexpected=[p for p in changes if p not in allowed and not p.startswith(prefix)]
assert before['head']==after['head'] and before['branch']==after['branch']
result=dict(before='00_before_baseline.json',after=sys.argv[1],head=after['head'],
    changed_existing=changes,unexpected_changes=unexpected,
    new_paths=[p for p in after['files'] if p not in before['files']],
    frozen_core_and_old_evidence_unchanged=not unexpected,
    production_regression_reused='../2026-10-04_gl_i05_r1/05_checks_meta.json: 423 fall and 2 follow exit0, frozen src/config/tests unchanged')
with (OUT/sys.argv[2]).open('x',encoding='utf8') as f:json.dump(result,f,indent=2)
print(json.dumps(dict(unexpected_changes=unexpected,changed_existing=len(changes),new_paths=len(result['new_paths']))))
sys.exit(int(bool(unexpected)))
