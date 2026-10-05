import datetime
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).parent
SESSION = 'ses_eff8d3be0ffepAa0xDl9vMyuI0'
if 'OPENCODE_DB' in os.environ:
    raise SystemExit('DB override present')
name = '10_opencode_compacted'
if any((OUT / (name + suffix)).exists() for suffix in ('.jsonl', '.stderr.txt', '_meta.json')):
    raise SystemExit('No evidence overwrite')
prompt = ('Continue SAME GL-P01 R1 after verified same-model summarize (09_compact_verified). No source changes. Use compacted summary, do not reread full root docs, source or tests. Read only new acceptance clarification paragraph: producer R/t isolated from artifact, projection execution preserves cache but keeps existing nested shallow-copy semantics; support fields only on existing ground summary, artifact-only ground=None stays null. Map monitor and lost/prediction existing lifecycle preservation checks. '
          'Read repository-local docs/human_fall/evidence/2026-10-03_gl_p01_r1/ponytail_SKILL.md instead. '
          'Codex copied the full original skill, SHA256 verified equal. Declare this ACTUAL read path/full in return. '
          'Do not reattempt outside-repository read or change permissions/global config. '
          'Reuse already-read contract/source; complete M01-M12 00_diag before allowed producer changes. '
          'Implement docs/human_fall/AI_PROMPT_GLP01_OPENCODE_R1.md and GLP01_ACCEPTANCE v1, '
          'self-check concentrated actual Python-to-preview JS pipeline, append returns/GL-P01.md SUBMITTED '
          'with SHA/model/session/commands/per-ID evidence, then stop. '
          'Only allowed producer and new concentrated tests/contract/this evidence/return. '
          'No formal/preview/runtime/driver/config/old evidence/board/deploy/capture/git/model/DB changes.')
command = [r'C:\Users\30680\AppData\Roaming\npm\node_modules\opencode-ai\bin\opencode.exe',
           'run', '--attach', 'http://127.0.0.1:18094', '--dir', 'D:/Code/ldiar', '--session', SESSION, '-m', 'opencode-go/deepseek-v4.1-flash', '--format', 'json', prompt]
start = time.monotonic()
meta = {'start': datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),
        'model': 'opencode-go/deepseek-v4.1-flash', 'db': 'default', 'session': SESSION}
with (OUT / (name + '.jsonl')).open('wb') as stdout, (OUT / (name + '.stderr.txt')).open('wb') as stderr:
    process = subprocess.Popen(command, cwd=ROOT, stdout=stdout, stderr=stderr,
                               creationflags=subprocess.CREATE_NO_WINDOW)
    meta['exit'] = process.wait()
meta.update(end=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),
            elapsed_s=time.monotonic()-start, pid=process.pid)
(OUT / (name + '_meta.json')).write_text(json.dumps(meta, indent=2), encoding='utf-8')
print(json.dumps(meta))
sys.exit(meta['exit'])

