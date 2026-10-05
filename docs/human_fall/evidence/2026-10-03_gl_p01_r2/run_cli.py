import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).parent
CLI = r'C:\Users\30680\AppData\Roaming\npm\node_modules\opencode-ai\bin\opencode.exe'
MODEL = 'opencode-go/deepseek-v4.1-flash'
TZ = datetime.timezone(datetime.timedelta(hours=8))

def create_baseline():
    dest = OUT / '00_before_manifest.json'
    if dest.exists():
        raise SystemExit('No evidence overwrite')
    paths = subprocess.check_output(['git', 'ls-files', '-c', '-o', '--exclude-standard', '-z'], cwd=ROOT).decode('utf-8').split('\0')
    files = {}
    for name in sorted(set(paths) - {''}):
        path = ROOT / name
        try:
            files[name] = {'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
        except OSError as error:
            files[name] = {'error': str(error)}
    data = {'time': datetime.datetime.now(TZ).isoformat(),
            'branch': subprocess.check_output(['git', 'branch', '--show-current'], cwd=ROOT, text=True).strip(),
            'head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
            'status': subprocess.check_output(['git', 'status', '--porcelain=v1', '-uall'], cwd=ROOT, text=True),
            'files': files}
    dest.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'head': data['head'], 'files': len(files)}))

def run(phase):
    if 'OPENCODE_DB' in os.environ:
        raise SystemExit('DB override present; do not change it')
    name = '01_service_probe' if phase == 'probe' else '03_opencode'
    if any((OUT / (name + suffix)).exists() for suffix in ('.jsonl', '.stderr.txt', '_meta.json')):
        raise SystemExit('No evidence overwrite')
    prompt = 'No tools or file changes. Reply only PROBE_OK.' if phase == 'probe' else (
        'Implement GL-P01 R1, sole production writer. Read docs/human_fall/AI_PROMPT_GLP01_OPENCODE_R1.md, '
        'GLP01_ACCEPTANCE.md v1 and evidence/2026-10-03_gl_p01_r1/PLAN_REVIEW.md. '
        'Actual ponytail read, full M01-M12 00_diag before source, smallest whitelist coordinate.ground projection. '
        'Use targeted current source, no long historical reread. Self-check actual production-to-preview JS chain, '
        'append per-ID return, SHA, SUBMITTED and stop writing. No formal/preview/runtime/config/driver/old evidence '
        'or board/deploy/capture/git/model/DB changes.')
    command = [CLI, 'run', '-m', MODEL, '--format', 'json', prompt]
    start = time.monotonic()
    meta = {'start': datetime.datetime.now(TZ).isoformat(), 'phase': phase, 'model': MODEL, 'db': 'default'}
    with (OUT / (name + '.jsonl')).open('wb') as stdout, (OUT / (name + '.stderr.txt')).open('wb') as stderr:
        process = subprocess.Popen(command, cwd=ROOT, stdout=stdout, stderr=stderr, creationflags=subprocess.CREATE_NO_WINDOW)
        try:
            meta.update(exit=process.wait(timeout=55 if phase == 'probe' else None), timed_out=False)
        except subprocess.TimeoutExpired:
            subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'], stdout=stderr, stderr=stderr)
            meta.update(exit=process.wait(), timed_out=True)
    meta.update(end=datetime.datetime.now(TZ).isoformat(), elapsed_s=time.monotonic()-start, pid=process.pid)
    (OUT / (name + '_meta.json')).write_text(json.dumps(meta, indent=2), encoding='utf-8')
    print(json.dumps(meta))
    return 1 if meta['timed_out'] else meta['exit']

if sys.argv[1] == 'baseline':
    create_baseline()
else:
    sys.exit(run(sys.argv[1]))
