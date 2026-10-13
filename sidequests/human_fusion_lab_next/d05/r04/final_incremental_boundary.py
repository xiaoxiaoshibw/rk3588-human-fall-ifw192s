"""Append-only, non-atomic final record audit; unchanged hashes are inherited."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time


ROOT = Path(__file__).resolve().parents[4]
OUT = ROOT / 'docs/human_capture/evidence/2026-10-12_hfus_d05_r4'
TARGET = OUT / 'FINAL_INCREMENTAL_BOUNDARY.json'
PREFIXES = [
    'sidequests/human_fusion_lab_next/d05/r02/',
    'sidequests/human_fusion_lab_next/d05/r03/',
    'sidequests/human_fusion_lab_next/d05/r04/',
    'docs/human_capture/evidence/2026-10-11_hfus_d05_r2/',
    'docs/human_capture/evidence/2026-10-12_hfus_d05_r3/',
    'docs/human_capture/evidence/2026-10-12_hfus_d05_r4/',
]


def own(path):
    return any(path.startswith(p) for p in PREFIXES) or path in [
        'docs/human_capture/README.md', 'docs/human_capture/returns/HFUS-D05.md']


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(8 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


assert not TARGET.exists()
started = time.time()
baseline = json.loads((OUT / 'FINAL_TREE_SHA.json').read_text(encoding='utf-8'))
before = {r['path']: r for r in baseline['files']}
current = set()
hashed = []
errors = []
drift = []
inherited = 0
for base, dirs, names in os.walk(ROOT):
    dirs[:] = [d for d in dirs if d != '.git']
    for name in names:
        path = Path(base) / name
        if path == TARGET:
            continue
        rel = path.relative_to(ROOT).as_posix()
        current.add(rel)
        try:
            first = path.stat()
            old = before.get(rel)
            if old and (first.st_size, first.st_mtime_ns) == (old['size'], old['mtime_ns']):
                inherited += 1
                continue
            digest = sha(path)
            last = path.stat()
            if (first.st_size, first.st_mtime_ns) != (last.st_size, last.st_mtime_ns):
                drift.append(rel)
            hashed.append({'path': rel, 'sha256': digest, 'size': first.st_size,
                           'mtime_ns': first.st_mtime_ns, 'own_scope': own(rel),
                           'kind': 'ADDED' if old is None else 'METADATA_CHANGED',
                           'previous_sha256': old['sha256'] if old else None})
        except Exception as exc:
            errors.append({'path': rel, 'error': str(exc)})

# Independently rehash all loaded JavaScript dependencies and current Demo tooling.
source_checks = []
for manifest in sorted(OUT.parent.glob('*hfus_d05_r[234]/**/runs/**/*SUMMARY.json')):
    doc = json.loads(manifest.read_text(encoding='utf-8'))
    sources = doc.get('sources', doc.get('SOURCES', []))
    if isinstance(sources, dict):
        sources = [{'path': p, 'sha256': h} for p, h in sources.items()]
    for item in sources:
        if not isinstance(item, dict) or 'path' not in item or 'sha256' not in item:
            raise ValueError('Unexpected source manifest shape: ' + str(manifest))
        path = Path(item['path'])
        if not path.is_absolute():
            path = ROOT / path
        actual = sha(path)
        source_checks.append({'manifest': manifest.relative_to(ROOT).as_posix(),
                              'path': item['path'], 'sha256': actual,
                              'matches_loaded': actual == item['sha256']})
tool_checks = []
assert source_checks, 'No loaded source manifests were checked'
for item in json.loads((OUT / 'TOOLING_SOURCES_V3.json').read_text(encoding='utf-8'))['files']:
    actual = sha(ROOT / item['path'])
    tool_checks.append({'path': item['path'], 'sha256': actual,
                        'matches_v3': actual == item['sha256']})
missing = sorted(set(before) - current)
report = {
    'baseline': 'FINAL_TREE_SHA.json', 'baseline_sha256': sha(OUT / 'FINAL_TREE_SHA.json'),
    'branch': subprocess.check_output(['git', 'branch', '--show-current'], cwd=ROOT).decode().strip(),
    'head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT).decode().strip(),
    'status': subprocess.check_output(['git', 'status', '--porcelain=v1', '--untracked-files=all'], cwd=ROOT).decode('utf-8'),
    'files_enumerated': len(current), 'metadata_unchanged_hashes_inherited': inherited,
    'actual_rehashed_new_or_changed': hashed, 'missing': missing,
    'outside_sha_changes': [r for r in hashed if not r['own_scope'] and r['sha256'] != r['previous_sha256']],
    'outside_missing': [p for p in missing if not own(p)],
    'loaded_sources_actual_rehashed': source_checks, 'tooling_v3_actual_rehashed': tool_checks,
    'errors': errors, 'drift': drift, 'started_unix': started, 'finished_unix': time.time(),
    'scope': 'tracked/untracked/ignored, .git internals excluded; non-atomic. Unchanged size+mtime inherits prior actual SHA, not a second full content freeze. Output itself excluded; no later file changes claimed.'}
with TARGET.open('x', encoding='utf-8') as f:
    json.dump(report, f, ensure_ascii=False, indent=2)
print(json.dumps({'files': len(current), 'new_or_changed': len(hashed),
                  'outside_changes': report['outside_sha_changes'], 'outside_missing': report['outside_missing'],
                  'source_checks': len(source_checks), 'source_mismatch': [r for r in source_checks if not r['matches_loaded']],
                  'tool_mismatch': [r for r in tool_checks if not r['matches_v3']], 'errors': errors, 'drift': drift}, ensure_ascii=False))
