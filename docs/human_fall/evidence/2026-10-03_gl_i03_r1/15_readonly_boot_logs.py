"""Extract only the two known CLI runs, avoiding auth/credential log contents."""
import datetime
import json
from pathlib import Path
import re

OUT = Path(__file__).resolve().parent
source = Path(r'C:\Users\30680\.local\share\opencode\log\opencode.log')
runs = {'cb195cf5': '14_resume_service_probe', 'b79ea463': '08_service_probe_historical_supplement'}
target = OUT / '15_readonly_boot_logs.json'
if target.exists():
    raise SystemExit('No evidence overwrite')
records = {name: [] for name in runs.values()}
for line in source.read_text(encoding='utf-8', errors='replace').splitlines():
    match = re.search(r'\brun=([0-9a-f]+)\b', line)
    if not match or match.group(1) not in runs:
        continue
    if re.search(r'(?i)authorization|bearer|api.?key|credential|password|secret|token', line):
        continue
    # The relevant boot/model diagnostic lines do not contain tool content.
    if any(x in line for x in ('message="creating instance"', 'message=fromDirectory',
                              'message=bootstrapping', 'message=loading',
                              'message="Failed to fetch models.dev"', 'message=init',
                              'message="event connected"', 'message=loop',
                              'message=stream', 'message="llm runtime selected"',
                              'message="stream error"')):
        records[runs[match.group(1)]].append(line)
payload = {'read_only_source': str(source), 'time_zone': 'timestamps are UTC; add 8h for Asia/Shanghai',
           'extracted': datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),
           'runs': records, 'redaction': 'lines potentially containing credentials omitted'}
with target.open('x', encoding='utf-8') as f:
    json.dump(payload, f, indent=2, ensure_ascii=False)
print(json.dumps({key: {'lines': len(lines),
    'has_session_marker': any('session.id=' in line for line in lines),
    'has_model_stream': any('message=stream' in line for line in lines),
    'has_upstream_reject': any('An active OpenCode Go subscription is required' in line for line in lines)}
    for key, lines in records.items()}))
