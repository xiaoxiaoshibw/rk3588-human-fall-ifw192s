"""Exclusive logs: real stdout/stderr/exit and command; never overwrite earlier attempts."""
from pathlib import Path
import json
import subprocess
import sys
import time

out = Path(__file__).parent
name, *cmd = sys.argv[1:]
assert name.replace('_', '').replace('-', '').isalnum()
start = time.time()
with (out / (name + '.stdout.log')).open('xb') as stdout, (out / (name + '.stderr.log')).open('xb') as stderr:
    p = subprocess.run(cmd, cwd=out.parents[3], stdout=stdout, stderr=stderr)
with (out / (name + '.run.json')).open('x', encoding='utf-8') as f:
    json.dump({'command': cmd, 'cwd': str(out.parents[3]), 'exit_code': p.returncode,
               'elapsed_seconds': time.time()-start, 'started_utc_epoch': start}, f, indent=2)
print(json.dumps({'name': name, 'exit_code': p.returncode, 'elapsed_seconds': time.time()-start}))
sys.exit(p.returncode)
