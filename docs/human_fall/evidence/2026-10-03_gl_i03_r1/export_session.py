import json
from pathlib import Path
import subprocess
import sys

OUT = Path(__file__).resolve().parent
EXE = r'C:\Users\30680\AppData\Roaming\npm\node_modules\opencode-ai\bin\opencode.exe'
name, session = sys.argv[1:3]
target = OUT / name
if target.exists():
    raise SystemExit('No evidence overwrite')
r = subprocess.run([EXE, 'export', session], cwd=OUT.parents[3], capture_output=True,
                   creationflags=subprocess.CREATE_NO_WINDOW)
if r.returncode:
    print(r.stderr.decode('utf-8', errors='replace')[:2000])
    raise SystemExit(r.returncode)
payload = json.loads(r.stdout)
with target.open('x', encoding='utf-8') as f:
    json.dump(payload, f, ensure_ascii=False, indent=2)
models = set()
finishes = []
for m in payload.get('messages', []):
    info = m.get('info', {})
    if info.get('role') == 'assistant':
        models.add((info.get('providerID'), info.get('modelID')))
        if info.get('finish'):
            finishes.append(info['finish'])
print(json.dumps({'session': session, 'models': sorted(models), 'finishes': finishes[-5:], 'exit': r.returncode}))
