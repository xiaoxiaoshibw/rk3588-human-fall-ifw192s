import ast
import hashlib
import json
import subprocess
from pathlib import Path
ROOT = Path(__file__).resolve().parents[5]
OUT = Path(__file__).resolve().parent
def sha(path):
    return hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
submitted = json.loads((OUT.parent / '22_source_manifest.json').read_text())
for item in submitted['changed']:
    assert sha(item['path']) == item['sha256'], item['path']
    ast.parse((ROOT/item['path']).read_text(encoding='utf-8-sig'), feature_version=(3,8))
baseline = json.loads((OUT.parent/'00_before_manifest.json').read_text())
allowed = {item['path'] for item in submitted['changed']} | {
    'docs/human_fall/GL03_ACCEPTANCE.md','docs/human_fall/returns/GL-03.md',
    'src/human_fall_detection/scripts/fall_replay.py'}
unexpected = [name for name,value in baseline.items() if name not in allowed and sha(name)!=value]
assert not unexpected, unexpected
review_start = json.loads((OUT/'00_baseline.json').read_text())
live = {}
for name,value in review_start['files'].items():
    if value.startswith('UNREADABLE:'):
        continue
    if sha(name)!=value:
        live[name] = sha(name)
assert not live, live
result = dict(submitted_source_sha_match=True, frozen_pre_r3_baseline_match=True,
              all_review_start_files_unchanged=True, python38_ast_parse=True,
              device_runtime='NOT_RUN', external_replay_sha=sha('src/human_fall_detection/scripts/fall_replay.py'),
              external_new_sha={p:sha(p) if (ROOT/p).exists() else 'ABSENT_AT_REVIEW_START_AND_END'
                                for p in submitted['external_concurrent_preserved_not_attributed']['new']},
              head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT).decode().strip())
print(json.dumps(result, indent=2))
