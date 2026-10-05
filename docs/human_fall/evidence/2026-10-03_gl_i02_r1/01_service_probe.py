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
    raise SystemExit('DB override present; default DB required')
name = '01_service_probe'
if any((OUT / (name + s)).exists() for s in ('.jsonl', '.stderr.txt', '_meta.json')):
    raise SystemExit('No evidence overwrite')
prompt = ('READ ONLY check. No code execution, no file writes, no tool use. '
          'Reply only: PROBE_OK')
command = [r'C:\Users\30680\AppData\Roaming\npm\node_modules\opencode-ai\bin\opencode.exe',
           'run', '--dir', 'D:/Code/ldiar',
           '-m', 'opencode-go/deepseek-v4.1-flash', '--format', 'json',
           prompt]
meta = {'start': datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),
        'model': 'opencode-go/deepseek-v4.1-flash', 'db': 'default',
        'phase': 'gli02_r1_pre_dispatch_probe', 'prompt': 'READ ONLY check / PROBE_OK'}
start = time.monotonic()
with (OUT / (name + '.jsonl')).open('wb') as stdout, \
     (OUT / (name + '.stderr.txt')).open('wb') as stderr:
    process = subprocess.Popen(command, cwd=ROOT, stdout=stdout, stderr=stderr,
                               creationflags=subprocess.CREATE_NO_WINDOW)
    try:
        meta['exit'] = process.wait(timeout=55)
        meta['timed_out'] = False
    except subprocess.TimeoutExpired:
        process.kill()
        meta['exit'] = None
        meta['timed_out'] = True
        meta['timeout_reason'] = '55s budget exceeded'
meta.update(end=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),
            elapsed_s=time.monotonic() - start, pid=process.pid)
(OUT / (name + '_meta.json')).write_text(json.dumps(meta, indent=2), encoding='utf-8')
print(json.dumps(meta, ensure_ascii=False))
sys.exit(meta['exit'] if meta['exit'] is not None else 1)
