"""Single authorized OpenCode process; separate no-tool service probes."""
import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
EXE = r'C:\Users\30680\AppData\Roaming\npm\node_modules\opencode-ai\bin\opencode.exe'
MODEL = 'opencode-go/deepseek-v4.1-flash'
name, phase = sys.argv[1:3]
if 'OPENCODE_DB' in os.environ:
    raise SystemExit('BLOCKED: OPENCODE_DB present; require default DB')
for suffix in ('.jsonl', '.stderr.txt', '_meta.json'):
    if (OUT / (name + suffix)).exists():
        raise SystemExit('No evidence overwrite')
prompt = ('No tool use, no file reads/writes, no commands. Reply only PROBE_OK'
          if phase == 'probe' else (ROOT / sys.argv[3]).read_text(encoding='utf-8'))
command = [EXE, 'run', '--dir', str(ROOT), '-m', MODEL, '--format', 'json']
if len(sys.argv) > 4:
    command.extend(['--session', sys.argv[4]])
command.append(prompt)
tz = datetime.timezone(datetime.timedelta(hours=8))
meta = {'start': datetime.datetime.now(tz).isoformat(), 'model': MODEL,
        'db': 'default', 'phase': phase,
        'prompt_sha256': hashlib.sha256(prompt.encode()).hexdigest()}
start = time.monotonic()
with (OUT / (name + '.jsonl')).open('xb') as stdout, (OUT / (name + '.stderr.txt')).open('xb') as stderr:
    process = subprocess.Popen(command, cwd=ROOT, stdout=stdout, stderr=stderr,
                               creationflags=subprocess.CREATE_NO_WINDOW)
    meta['pid'] = process.pid
    try:
        meta['exit'] = process.wait(timeout=55 if phase == 'probe' else None)
        meta['timed_out'] = False
    except subprocess.TimeoutExpired:
        meta['timed_out'] = True
        meta['timeout_reason'] = '55s probe budget exceeded; stopped this process only'
        process.kill()
        meta['exit'] = process.wait(timeout=4)
meta.update(end=datetime.datetime.now(tz).isoformat(), elapsed_s=time.monotonic()-start)
events = []
for line in (OUT / (name + '.jsonl')).read_text(encoding='utf-8').splitlines():
    try:
        events.append(json.loads(line))
    except ValueError:
        pass
meta['sessions'] = sorted({e['sessionID'] for e in events if e.get('sessionID')})
meta['event_types'] = sorted({e.get('type', '') for e in events})
meta['probe_ok'] = phase == 'probe' and not meta['timed_out'] and meta['exit'] == 0 and any(
    e.get('type') == 'text' and (e.get('part') or {}).get('text', '').strip() == 'PROBE_OK' for e in events
) and not any(e.get('type') in ('error', 'tool_use') for e in events)
with (OUT / (name + '_meta.json')).open('x', encoding='utf-8') as f:
    json.dump(meta, f, indent=2)
print(json.dumps(meta))
sys.exit(0 if meta['probe_ok'] else 1 if phase == 'probe' else meta['exit'])
