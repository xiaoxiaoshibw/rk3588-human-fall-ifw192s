"""重打后的冻结总控制台探针（Python 版，避开 PowerShell/编码坑）。

1) 壳页 console.html：从 Console.exe 的每个监听端口取一次，确认分栏（GROUPS/数据管理）
   与会话数据库卡片已内嵌；
2) 冻结回放服务（默认 8901）：sessions_db.html 可开 + /api/manifest 返回本机 sha256 清单。
只读 GET；不删任何数据。
"""
import json
import re
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
SID = 'cap_20261015_142730'
REPLAY = int(sys.argv[1]) if len(sys.argv) > 1 else 8901
EXE = HERE.parents[3] / 'pc_apps' / 'console' / 'dist' / 'Console.exe'
out = {}


def get(url, timeout=90):
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        return resp.status, resp.read()


def pids():
    raw = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq Console.exe', '/FO', 'CSV'],
                         capture_output=True).stdout.decode('gbk', 'replace')
    return [int(m.group(1)) for m in re.finditer(r'"Console\.exe","(\d+)"', raw)]


def ports(owner):
    raw = subprocess.run(['netstat', '-ano', '-p', 'TCP'], capture_output=True).stdout.decode('gbk', 'replace')
    found = set()
    for line in raw.splitlines():
        m = re.match(r'\s+TCP\s+\S+:(\d+)\s+\S+\s+LISTENING\s+(\d+)', line)
        if m and int(m.group(2)) in owner:
            found.add(int(m.group(1)))
    return sorted(found)


if EXE.is_file():
    import hashlib
    out['exe'] = {'path': str(EXE), 'bytes': EXE.stat().st_size,
                  'sha256': hashlib.sha256(EXE.read_bytes()).hexdigest().upper()}
live = pids()
out['console_pids'] = live
out['shell'] = []
for port in ports(live):
    try:
        status, body = get('http://127.0.0.1:%d/console.html?replay_port=%d' % (port, REPLAY), timeout=10)
    except Exception:
        continue
    text = body.decode('utf-8', 'replace')
    if 'LiDAR Workspace' not in text:
        continue
    out['shell'].append({
        'port': port, 'status': status, 'bytes': len(body),
        'has_GROUPS': 'const GROUPS' in text,
        'has_group_sections': '.group .gtitle' in text,
        'has_db_card': 'sessions_db.html' in text,
        'has_db_group_name': '数据管理' in text,
        'has_learn_card_guard': 'APPS.push' in text,
    })
out['replay_service'] = REPLAY
status, page = get('http://127.0.0.1:%d/sessions_db.html' % REPLAY, timeout=10)
text = page.decode('utf-8', 'replace')
out['db_page'] = {'status': status, 'bytes': len(page),
                  'has_title': '会话数据库' in text,
                  'has_manifest_call': '/api/manifest' in text,
                  'has_delete_call': '/api/delete' in text}
status, body = get('http://127.0.0.1:%d/api/manifest?sid=%s' % (REPLAY, SID), timeout=180)
manifest = json.loads(body)
out['manifest'] = {
    'status': status, 'sid': manifest['sid'],
    'local_present': manifest['local']['present'],
    'files': [{'name': f['name'], 'bytes': f['bytes'], 'sha256': f['sha256'][:16]} for f in manifest['local']['files']],
    'total_bytes': manifest['local']['total_bytes'],
    'board': {k: manifest['board'].get(k) for k in ('session_id', 'state', 'frame_count')},
}

print(json.dumps(out, ensure_ascii=False, indent=2))
(HERE / 'FROZEN_PROBE.json').write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')
