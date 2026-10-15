"""会话数据库模块现场只读探针：真数据根（captures/remote）+ 真板端登记。

只做 GET（/sessions_db.html、/api/manifest），不删任何东西；用于证明：
  - 页面由回放服务直接供给（无需新路由）
  - 清单接口给出本机逐文件 name/bytes/sha256 与板端登记行
  - 抽一个真实会话的 points.bin，sha256 与本机独立计算一致
"""
import hashlib
import json
import os
import sys
import threading
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPLAY = HERE.parents[3] / 'pc_apps' / 'human_replay'
sys.path.insert(0, str(REPLAY))
import config as C          # noqa: E402
import human_replay_lib as H  # noqa: E402

SID = sys.argv[1] if len(sys.argv) > 1 else 'cap_20261015_142730'


def sha256(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as fh:
        for block in iter(lambda: fh.read(1 << 20), b''):
            digest.update(block)
    return digest.hexdigest()


server = ThreadingHTTPServer(('127.0.0.1', 0), H.Handler)
threading.Thread(target=server.serve_forever, daemon=True).start()
base = 'http://127.0.0.1:%d' % server.server_address[1]
out = {'dest_root': C.DEST_ROOT, 'sid': SID}
try:
    with urllib.request.urlopen(base + '/sessions_db.html', timeout=10) as resp:
        page = resp.read().decode('utf-8')
    out['page_status'] = 200
    out['page_bytes'] = len(page)
    out['page_has_title'] = '会话数据库' in page
    out['page_has_delete'] = '/api/delete' in page
    out['page_has_manifest'] = '/api/manifest' in page
    with urllib.request.urlopen(base + '/api/manifest?sid=' + SID, timeout=120) as resp:
        manifest = json.load(resp)
    out['manifest_local_present'] = manifest['local']['present']
    out['manifest_local_files'] = [{'name': f['name'], 'bytes': f['bytes']} for f in manifest['local']['files']]
    out['manifest_total_bytes'] = manifest['local']['total_bytes']
    points = next((f for f in manifest['local']['files'] if f['name'] == 'points.bin'), None)
    if points:
        own = sha256(os.path.join(C.DEST_ROOT, SID, 'points.bin'))
        out['points_sha256_service'] = points['sha256']
        out['points_sha256_independent'] = own
        out['points_sha256_match'] = own == points['sha256']
    out['board'] = {k: manifest['board'].get(k) for k in ('session_id', 'state', 'frame_count', 'duration_sec')} \
        if isinstance(manifest.get('board'), dict) else manifest.get('board')
    still_there = os.path.isfile(os.path.join(C.DEST_ROOT, SID, 'points.bin'))
    out['read_only_files_still_present'] = still_there
finally:
    server.shutdown()
    server.server_close()

print(json.dumps(out, ensure_ascii=False, indent=2))
(HERE / 'DB_PROBE.json').write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')
