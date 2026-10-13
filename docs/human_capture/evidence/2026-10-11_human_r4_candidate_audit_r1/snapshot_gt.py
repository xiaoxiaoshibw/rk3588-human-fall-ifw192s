"""Snapshot only eligible currently-bound GT; never approve/freeze/write GT."""
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / 'pc_apps/human_ml'))
from frozen_gt import audit_session, write_json

sessions = []
for suffix in ('175227', '175429', '180235'):
    sid = 'cap_20261010_' + suffix
    record, doc, _ = audit_session(sid, ROOT / 'pc_apps/human_replay/gt_store', ROOT / 'captures/remote')
    if not record['eligible']:
        raise ValueError(str(record))
    sessions.append({'record': record, 'doc': doc, 'zero_person_protocol': suffix == '175227'})
write_json(pathlib.Path(__file__).parent / 'GT_SNAPSHOT_02.json', {'sessions': sessions})
print([(s['record']['sid'], s['record']['version'], s['record']['eligible']) for s in sessions])
