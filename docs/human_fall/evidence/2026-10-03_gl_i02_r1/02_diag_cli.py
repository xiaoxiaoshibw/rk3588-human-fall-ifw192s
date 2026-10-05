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
name = '03_opencode_diag'
if any((OUT / (name + s)).exists() for s in ('.jsonl', '.stderr.txt', '_meta.json')):
    raise SystemExit('No evidence overwrite')

prompt_path = ROOT / 'docs' / 'human_fall' / 'AI_PROMPT_GLI02_OPENCODE_R1_DIAG.md'
prompt_text = prompt_path.read_text(encoding='utf-8')

command = [r'C:\Users\30680\AppData\Roaming\npm\node_modules\opencode-ai\bin\opencode.exe',
           'run', '--dir', 'D:/Code/ldiar',
           '-m', 'opencode-go/deepseek-v4.1-flash', '--format', 'json',
           prompt_text]
meta = {'start': datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),
        'model': 'opencode-go/deepseek-v4.1-flash', 'db': 'default',
        'phase': 'gli02_r1_phase1_diag',
        'prompt_sha256': __import__('hashlib').sha256(prompt_text.encode('utf-8')).hexdigest()}
start = time.monotonic()
with (OUT / (name + '.jsonl')).open('wb') as stdout, \
     (OUT / (name + '.stderr.txt')).open('wb') as stderr:
    process = subprocess.Popen(command, cwd=ROOT, stdout=stdout, stderr=stderr,
                               creationflags=subprocess.CREATE_NO_WINDOW)
    meta['exit'] = process.wait()
meta.update(end=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),
            elapsed_s=time.monotonic() - start, pid=process.pid)
(OUT / (name + '_meta.json')).write_text(json.dumps(meta, indent=2), encoding='utf-8')
print(json.dumps(meta, ensure_ascii=False))
sys.exit(meta['exit'])
