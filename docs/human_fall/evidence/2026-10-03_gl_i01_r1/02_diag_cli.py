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
if any((OUT/('03_opencode_diag'+s)).exists() for s in ('.jsonl','.stderr.txt','_meta.json')):
    raise SystemExit('No evidence overwrite')
prompt = ('GL-I01 R1 phase ONE ONLY: read docs/human_fall/AI_PROMPT_GLI01_OPENCODE_R1_DIAG.md, '
          'GLI01_ACCEPTANCE v1 and this round PLAN_REVIEW. Actual local ponytail_SKILL.md read. '
          'Only write evidence/2026-10-03_gl_i01_r1/00_diag.md with complete M01-M13 design/function/check matrix. '
          'DO NOT edit or create ANY source/tests/config/state/contracts/returns. '
          'Reply READY_FOR_DESIGN_REVIEW and STOP; do not implement on your own. Codex will verify source SHA '
          'and complete design, then separately authorize phase2. Use targeted current source, not full history. '
          'Existing capture only read/hash/count; no fit/ROI/physical conclusion/board/deploy/capture/git/DB/model changes.')
command = [r'C:\Users\30680\AppData\Roaming\npm\node_modules\opencode-ai\bin\opencode.exe',
           'run','-m','opencode-go/deepseek-v4.1-flash','--format','json',prompt]
start = time.monotonic()
meta = {'start':datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),
        'model':'opencode-go/deepseek-v4.1-flash','db':'default','phase':'diagnosis_only'}
with (OUT/'03_opencode_diag.jsonl').open('wb') as stdout,(OUT/'03_opencode_diag.stderr.txt').open('wb') as stderr:
    process = subprocess.Popen(command,cwd=ROOT,stdout=stdout,stderr=stderr,creationflags=subprocess.CREATE_NO_WINDOW)
    meta['exit'] = process.wait()
meta.update(end=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),
            elapsed_s=time.monotonic()-start,pid=process.pid)
(OUT/'03_opencode_diag_meta.json').write_text(json.dumps(meta,indent=2),encoding='utf-8')
print(json.dumps(meta))
sys.exit(meta['exit'])
