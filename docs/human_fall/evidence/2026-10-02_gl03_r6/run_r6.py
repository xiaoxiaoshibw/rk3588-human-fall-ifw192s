"""GL-03 R6 real command logs (before/after); no production writes."""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent


def run(name, args):
    command = [sys.executable, '-B', '-W', 'error'] + args
    with (OUT / (name + '.txt')).open('w', encoding='utf-8') as log:
        log.write('COMMAND: ' + repr(command) + '\n')
        log.flush()
        result = subprocess.run(command, cwd=ROOT, stdout=log,
                                stderr=subprocess.STDOUT)
        log.write('\nEXIT=' + str(result.returncode) + '\n')
    print(name, 'EXIT=', result.returncode, flush=True)
    return result.returncode


BEFORE = [
    ('01_closure_before', [
        'docs/human_fall/evidence/2026-10-02_gl03_r5/codex_review_01/closure_checks.py']),
]

AFTER = [
    ('10_prior_geometry', [
        'docs/human_fall/evidence/2026-10-02_gl03_r1/codex_geometry_checks.py']),
    ('11_prior_reference', [
        'docs/human_fall/evidence/2026-10-02_gl03_r2/codex_reference_checks.py']),
    ('12_prior_failures', [
        'docs/human_fall/evidence/2026-10-02_gl03_r3/codex_review_01/review_checks.py']),
    ('13_r4_worker', [
        'docs/human_fall/evidence/2026-10-02_gl03_r4/06_r4_checks.py']),
    ('14_r5_context', [
        'docs/human_fall/evidence/2026-10-02_gl03_r4/codex_review_01/context_checks.py']),
    ('14b_closure_after', [
        'docs/human_fall/evidence/2026-10-02_gl03_r5/codex_review_01/closure_checks.py']),
    ('15_gl03_suite', ['-m', 'unittest', 'discover',
                       '-s', 'src/human_fall_detection/tests',
                       '-p', 'test_gl03_candidates_geometry.py', '-v']),
    ('16_fall', ['-m', 'unittest', 'discover',
                 '-s', 'src/human_fall_detection/tests', '-v']),
    ('17_follow', ['-m', 'unittest', 'discover',
                   '-s', 'src/human_follow_calibration/tests', '-v']),
    ('18_gl02_lifecycle', [
        'docs/human_fall/evidence/2026-10-01_gl02_r5_codex/codex_r5_lifecycle_checks.py']),
    ('19_gl02_pending', [
        'docs/human_fall/evidence/2026-10-01_gl02_r6/codex_pending_version_checks.py']),
]

if __name__ == '__main__':
    phase = sys.argv[1] if len(sys.argv) > 1 else 'after'
    jobs = BEFORE if phase == 'before' else AFTER
    results = {}
    for name, args in jobs:
        results[name] = run(name, args)
    print(results)
