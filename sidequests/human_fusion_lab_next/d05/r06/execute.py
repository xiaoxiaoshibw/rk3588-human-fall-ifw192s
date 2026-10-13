"""Exclusive-output child runner; records actual PID, command, exit, log and SHA."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time


ROOT = Path(__file__).resolve().parents[4]
OUT = ROOT / 'docs/human_capture/evidence/2026-10-12_hfus_d05_r5'
name, *command = sys.argv[1:]
assert command and '/' not in name and '\\' not in name
log = OUT / (name + '.log')
status = OUT / (name + '_EXIT.json')
assert not status.exists()
started = time.time()
with log.open('x', encoding='utf-8') as f:
    child = subprocess.Popen(command, cwd=ROOT, stdout=f, stderr=subprocess.STDOUT,
                             creationflags=subprocess.CREATE_NO_WINDOW)
    print(json.dumps({'running_pid': child.pid, 'command': command, 'started_unix': started}), flush=True)
    code = child.wait()
record = {'command': command, 'pid': child.pid, 'exit_code': code,
          'started_unix': started, 'finished_unix': time.time(),
          'log_sha256': hashlib.sha256(log.read_bytes()).hexdigest(),
          'runner_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
with status.open('x', encoding='utf-8') as f:
    json.dump(record, f, ensure_ascii=True, indent=2)
print(json.dumps(record), flush=True)
sys.exit(code)
