"""Read assistant model metadata only, opening the existing default SQLite read-only."""
import json
from pathlib import Path
import sqlite3
import sys

OUT = Path(__file__).resolve().parent
target = OUT / sys.argv[1]
if target.exists():
    raise SystemExit('No evidence overwrite')
sessions = sys.argv[2:]
db_uri = 'file:C:/Users/30680/.local/share/opencode/opencode.db?mode=ro'
con = sqlite3.connect(db_uri, uri=True, timeout=3)
result = {'access': 'mode=ro; only message.data for the requested sessions', 'sessions': {}}
ok = True
for session in sessions:
    rows = con.execute('SELECT data FROM message WHERE session_id=? ORDER BY time_created', (session,)).fetchall()
    assistants = [json.loads(row[0]) for row in rows if json.loads(row[0]).get('role') == 'assistant']
    models = sorted({(m.get('providerID'), m.get('modelID')) for m in assistants})
    ok = ok and models == [('opencode-go', 'deepseek-v4.1-flash')]
    result['sessions'][session] = {'assistant_messages': len(assistants), 'actual_models': models,
                                   'final_finish': assistants[-1].get('finish') if assistants else None}
con.close()
with target.open('x', encoding='utf-8') as f:
    json.dump(result, f, indent=2)
print(json.dumps(result))
sys.exit(0 if ok else 1)
