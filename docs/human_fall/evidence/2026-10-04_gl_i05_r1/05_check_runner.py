"""Closed raw logs for safe read-only checks; no evidence overwrite."""
import json
from pathlib import Path
import subprocess
import sys
import time

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
checks = [
    ('author_research', [sys.executable, '-B', '-W', 'error',
                        'docs/human_fall/evidence/2026-10-03_gl_i05_r1/research_01/test_gli05_research.py']),
    ('fall_regression', [sys.executable, '-B', '-W', 'error', '-m', 'unittest',
                         'discover', '-s', 'src/human_fall_detection/tests', '-v']),
    ('follow_regression', [sys.executable, '-B', '-W', 'error', '-m', 'unittest',
                           'discover', '-s', 'src/human_follow_calibration/tests', '-v']),
]
results = []
for name, command in checks:
    started = time.perf_counter()
    with (OUT / ('05_' + name + '.txt')).open('xb') as log:
        completed = subprocess.run(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
    results.append(dict(check=name, command=command, exit=completed.returncode,
                        elapsed_s=time.perf_counter() - started))
    print(json.dumps(results[-1]), flush=True)
with (OUT / '05_checks_meta.json').open('x', encoding='utf8') as log:
    json.dump(results, log, indent=2)
sys.exit(int(any(item['exit'] for item in results)))
