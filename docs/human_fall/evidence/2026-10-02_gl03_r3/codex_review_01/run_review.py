import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
OUT = Path(__file__).resolve().parent
def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def manifest():
    names = subprocess.check_output(['git', 'ls-files', '-z', '--cached', '--others', '--exclude-standard'], cwd=ROOT).decode().split('\0')
    result = {}
    for name in names:
        if not name or name.startswith(OUT.relative_to(ROOT).as_posix() + '/'):
            continue
        try:
            path = ROOT / name
            if path.is_file():
                result[name] = digest(path)
        except OSError as exc:
            result[name] = 'UNREADABLE:' + str(exc.winerror)
    return result

start = manifest()
(OUT / '00_baseline.json').write_text(json.dumps(dict(
    branch=subprocess.check_output(['git','branch','--show-current'],cwd=ROOT).decode().strip(),
    head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT).decode().strip(),
    python=sys.version, files=start), indent=2), encoding='utf-8')
submitted = json.loads((OUT.parent / '22_source_manifest.json').read_text())
matches = {item['path']: digest(ROOT / item['path']) == item['sha256'] for item in submitted['changed'] + [submitted['acceptance']]}
(OUT / '01_submitted_sha.json').write_text(json.dumps(matches, indent=2), encoding='utf-8')
print('Submitted SHA:', matches, flush=True)
jobs = [
 ('10_geometry', ['docs/human_fall/evidence/2026-10-02_gl03_r1/codex_geometry_checks.py']),
 ('11_reference', ['docs/human_fall/evidence/2026-10-02_gl03_r2/codex_reference_checks.py']),
 ('12_independent', [str(OUT / 'review_checks.py')]),
 ('13_fall', ['-m','unittest','discover','-s','src/human_fall_detection/tests','-v']),
 ('14_follow', ['-m','unittest','discover','-s','src/human_follow_calibration/tests','-v']),
]
results = {}
for name, args in jobs:
    command = [sys.executable, '-B', '-W', 'error'] + args
    with (OUT / (name + '.txt')).open('w',encoding='utf-8') as log:
        log.write('COMMAND: ' + repr(command) + '\n'); log.flush()
        run = subprocess.run(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
        log.write('\nEXIT=' + str(run.returncode) + '\n')
    results[name] = run.returncode
    print(name, 'EXIT=', run.returncode, flush=True)
(OUT / '15_results.json').write_text(json.dumps(results, indent=2),encoding='utf-8')
end = manifest()
deltas = {p: [start.get(p),end.get(p)] for p in sorted(set(start)|set(end)) if start.get(p)!=end.get(p)}
(OUT / '16_end_deltas.json').write_text(json.dumps(deltas,indent=2),encoding='utf-8')
print('Live deltas:', list(deltas), flush=True)
