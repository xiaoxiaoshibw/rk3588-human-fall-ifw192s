# -*- coding: utf-8 -*-
"""P02 r2 基线生成（一次性）。拒绝覆盖既有 00_BASELINE.json。"""
import json, hashlib, os

SRC = r'D:/Code/ldiar/docs/human_fall/evidence/2026-10-04_p02_ground_r1'
DST = os.path.dirname(os.path.abspath(__file__))
TARGET = os.path.join(DST, '00_BASELINE.json')
assert not os.path.exists(TARGET), '00_BASELINE.json exists, refuse overwrite'

def load(p):
    with open(p, encoding='utf-8') as f:
        return json.load(f)

def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for c in iter(lambda: f.read(1 << 20), b''):
            h.update(c)
    return h.hexdigest()

INV = r'D:/Code/ldiar/docs/human_fall/evidence/2026-10-04_p02_context_r1/03_SESSION_INVENTORY.json'
inv = {s['session']: s for s in load(INV)}
SESS = {'A': 'cap_20261004_202456', 'B': 'cap_20261004_203135', 'C': 'cap_20261004_203349'}

paths = [
    INV,
    r'D:/Code/ldiar/pc_apps/human_replay/annotator.html',
    r'D:/Code/ldiar/docs/human_fall/P02_ACCEPTANCE.md',
    os.path.join(SRC, '00_BASELINE.json'),
    os.path.join(SRC, '01_DIAG_AND_PROPOSAL.md'),
    r'D:/Code/ldiar/src/human_fall_detection/core/ground.py',
    r'D:/Code/ldiar/src/human_fall_detection/core/ground_diagnostics.py',
]
for label in ('A', 'B', 'C'):
    sdir = inv[SESS[label]]['path']
    paths.append(os.path.join(sdir, 'meta.json'))
    paths.append(os.path.join(sdir, 'points.bin'))

files = {}
for p in paths:
    files[p] = {'sha256': sha(p), 'size': os.path.getsize(p)}

fresh = {e['session']: e for e in
         load(r'D:/Code/ldiar/docs/human_fall/evidence/2026-10-04_p02_session_check_r1/00_SCOPE_AND_BASELINE.json')['fresh_source_checks']}
for label in ('A', 'B', 'C'):
    sdir = inv[SESS[label]]['path']
    assert files[os.path.join(sdir, 'meta.json')]['sha256'] == fresh[SESS[label]]['meta_sha256'], 'meta drift ' + label
    assert files[os.path.join(sdir, 'points.bin')]['sha256'] == fresh[SESS[label]]['bin_sha256'], 'bin drift ' + label

baseline = {
    'head': '73447d12ec1255643f6531e2d9e2287fb1481059',
    'supersedes': SRC,
    'role_scope': 'P02-C/D/E offline same-point-set estimator comparison; no production/capture/device writes',
    'files': files,
    'capture_sha_cross_check': 'matches 2026-10-04_p02_session_check_r1 fresh_source_checks for all 3 sessions',
}
with open(TARGET, 'w', encoding='utf-8') as f:
    json.dump(baseline, f, ensure_ascii=False, indent=1)
print('00 ok,', len(files), 'files; capture cross-check passed')
