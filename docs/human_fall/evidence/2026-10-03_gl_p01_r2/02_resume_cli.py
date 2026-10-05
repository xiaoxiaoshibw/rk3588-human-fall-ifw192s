import datetime
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
name = '03_opencode'
if any((OUT/(name+s)).exists() for s in ('.jsonl','.stderr.txt','_meta.json')):
    raise SystemExit('No evidence overwrite')
prompt = ('Continue SAME GL-P01 R2 sole-writer after R1 SUBMITTED/stopped. New probe12.469s PROBE_OK. '
          'Read ONLY docs/human_fall/AI_PROMPT_GLP01_OPENCODE_R2.md, R1 CODEX_REVIEW and failure in97. '
          'Do not reread full history/source/test files; use compacted summary and rg+targeted lines. '
          'Actual local ponytail read, M01-M12+accepted list/tuple container cross-consumer 00_diag first, '
          'then smallest producer guard fix and concentrated actual FallNodeCore/ROS/JSON/JS regression. '
          'Original requirements/flags/IDs/unknown behavior remain. Append perP/perM return SHA SUBMITTED and stop. '
          'Only allowed producer+two new GLP tests+this evidence/return; no runtime/math/config/driver/webui/old evidence '
          'or git/board/capture/deploy/GL05/model/DB changes.')
command = [r'C:\Users\30680\AppData\Roaming\npm\node_modules\opencode-ai\bin\opencode.exe',
           'run','--attach','http://127.0.0.1:18094','--dir','D:/Code/ldiar',
           '--session','ses_eff8d3be0ffepAa0xDl9vMyuI0','-m',
           'opencode-go/deepseek-v4.1-flash','--format','json',prompt]
start = time.monotonic()
meta = {'start':datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),
        'model':'opencode-go/deepseek-v4.1-flash','db':'default','session':'ses_eff8d3be0ffepAa0xDl9vMyuI0'}
with (OUT/(name+'.jsonl')).open('wb') as stdout,(OUT/(name+'.stderr.txt')).open('wb') as stderr:
    process = subprocess.Popen(command,cwd=ROOT,stdout=stdout,stderr=stderr,creationflags=subprocess.CREATE_NO_WINDOW)
    meta['exit'] = process.wait()
meta.update(end=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),
            elapsed_s=time.monotonic()-start,pid=process.pid)
(OUT/(name+'_meta.json')).write_text(json.dumps(meta,indent=2),encoding='utf-8')
print(json.dumps(meta))
sys.exit(meta['exit'])
