import ast
import hashlib
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[5]
OUT=Path(__file__).resolve().parent
def sha(name):
    return hashlib.sha256((ROOT/name).read_bytes()).hexdigest()
submitted=json.loads((OUT.parent/'22_source_manifest.json').read_text())
matches={name:sha(name)==value for section in ['sources','acceptance','data'] for name,value in submitted[section].items()}
assert all(matches.values()),matches
for name in submitted['sources']:
    if name.endswith('.py'):
        ast.parse((ROOT/name).read_text(encoding='utf-8-sig'),feature_version=(3,8))
start=json.loads((OUT/'00_baseline.json').read_text())['files']
changed={name:sha(name) for name,value in start.items() if not value.startswith('UNREADABLE:') and sha(name)!=value}
assert not changed,changed
previous=json.loads((OUT.parent.parent/'2026-10-02_gl03_r3/codex_review_01/00_baseline.json').read_text())['files']
prefixes=('src/inno_lidar_ros/','src/inno_lidar_msg/','src/human_fall_detection/config/','webui/')
protected={name:sha(name)==value for name,value in previous.items() if name.startswith(prefixes)}
assert all(protected.values()),[name for name,valid in protected.items() if not valid]
print(json.dumps(dict(submitted_sha=matches,baseline_deltas=changed,
    protected_since_r3_review_count=len(protected),protected_since_r3_review_match=True,
    python38_ast='PASS',device_runtime='NOT_RUN',production_written=False),indent=2))
