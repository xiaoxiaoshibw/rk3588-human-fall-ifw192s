"""Capture actual command, source SHA, environment, output, exit and duration (r12)."""
import subprocess
import sys
import time
from register2 import EV, HERE, ROOT, sha, put

if __name__ == '__main__':
    label = sys.argv[1]
    cmd = [sys.executable, '-B', '-W', 'error'] + sys.argv[2:]
    assert (EV / 'REGISTRATION.json').exists(), 'freeze registration first'
    inputs = {str(p.relative_to(ROOT)): sha(p) for p in HERE.glob('*.py')}
    t = time.perf_counter()
    with (EV / (label + '.log')).open('x', encoding='utf8') as out:
        cp = subprocess.run(cmd, cwd=ROOT, stdout=out, stderr=subprocess.STDOUT)
    put(EV / (label + '_RUN.json'), dict(command=cmd, exit_code=cp.returncode, seconds=time.perf_counter() - t, source_sha=inputs, protocol_sha=sha(EV / 'PROTOCOL_V1.json')))
    print(label, cp.returncode, time.perf_counter() - t, flush=True)
    raise SystemExit(cp.returncode)
