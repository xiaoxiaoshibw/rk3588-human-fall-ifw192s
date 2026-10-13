"""Sequential integrity audit, actual replay contracts, then uncontended pure timing."""
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
OUT = ROOT / 'docs/human_capture/evidence/2026-10-12_hfus_d05_r5'
tasks = [
    ('FULL_COMPARISON_V2', [sys.executable, '-B', '-W', 'error', str(HERE / 'analysis_v2/analyze.py')]),
    ('REPLAY_CONTRACTS', ['node', str(HERE / 'check_contracts.js')]),
    ('PERFORMANCE', ['node', str(HERE / 'perf_bank.js'), str(OUT / 'PERFORMANCE_PURE.json'), str(OUT / 'RETENTION_BANK_PURE.jsonl')]),
]
for name, command in tasks:
    result = subprocess.run([sys.executable, '-B', '-W', 'error', str(HERE / 'execute.py'), name, *command], cwd=ROOT)
    if result.returncode:
        sys.exit(result.returncode)
