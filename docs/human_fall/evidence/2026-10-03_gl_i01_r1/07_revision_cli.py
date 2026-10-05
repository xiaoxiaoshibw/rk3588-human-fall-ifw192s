import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

OUT = Path(__file__).parent
ROOT = OUT.parents[3]
if 'OPENCODE_DB' in os.environ:
    raise SystemExit('DB override present')
if any((OUT/('07_diag_revision'+s)).exists() for s in ('.jsonl','.stderr.txt','_meta.json')):
    raise SystemExit('No evidence overwrite')
prompt = ('GL-I01 R1 phase ONE revision ONLY per06_DESIGN_REVIEW: read docs/human_fall/AI_PROMPT_GLI01_OPENCODE_R1_DIAG.md, '
          'GLI01_ACCEPTANCE v1 and this round PLAN_REVIEW. Actual local ponytail_SKILL.md read. '
          'Read evidence/2026-10-03_gl_i01_r1/06_DESIGN_REVIEW.md, which overrides conflicting initial design. Only write NEW evidence/2026-10-03_gl_i01_r1/07_diag_revision.md with full M01-M13 updated actual-function/order/check matrix. Do not reread full files/history. No arbitrary groups, explicit frame/units, actual source XYZ equality, all-loader detection, group-first selectors, single adapted output/no diagnostics, atomic exclusive link only. '
          'DO NOT edit or create ANY source/tests/config/state/contracts/returns. '
          'Reply READY_FOR_DESIGN_REVIEW and STOP; do not implement on your own. Codex will verify source SHA '
          'and complete design, then separately authorize phase2. Use targeted current source, not full history. '
          'Existing capture only read/hash/count; no fit/ROI/physical conclusion/board/deploy/capture/git/DB/model changes.')
command = [r'C:\Users\30680\AppData\Roaming\npm\node_modules\opencode-ai\bin\opencode.exe',
           'run','--attach','http://127.0.0.1:18094','--dir','D:/Code/ldiar','--session','ses_eff575a5affevftT6g3Dzvg05e','-m','opencode-go/deepseek-v4.1-flash','--format','json',prompt]
start = time.monotonic()
meta = {'start':datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),
        'model':'opencode-go/deepseek-v4.1-flash','db':'default','phase':'diagnosis_only'}
with (OUT/'07_diag_revision.jsonl').open('wb') as stdout,(OUT/'07_diag_revision.stderr.txt').open('wb') as stderr:
    process = subprocess.Popen(command,cwd=ROOT,stdout=stdout,stderr=stderr,creationflags=subprocess.CREATE_NO_WINDOW)
    meta['exit'] = process.wait()
meta.update(end=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),
            elapsed_s=time.monotonic()-start,pid=process.pid)
(OUT/'07_diag_revision_meta.json').write_text(json.dumps(meta,indent=2),encoding='utf-8')
print(json.dumps(meta))
sys.exit(meta['exit'])

