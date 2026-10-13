"""HF-REAL-03：生成 SOURCE_AND_END_BOUNDARY.json + ARTIFACTS_FINAL_SHA.json。
ponytail：一次性hash小工具，不为通用工具。"""
import hashlib, json
from pathlib import Path

ROOT = Path(r'D:/Code/ldiar')
SRC = ROOT / 'sidequests/human_fusion_lab_next/real_fall/r03'
EV = ROOT / 'docs/human_fall/evidence/2026-10-13_hf_real_03_r1'
EV_CAM = ROOT / 'docs/human_capture/evidence/2026-10-13_cam_hot_r1'

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()

files = []
for root in (SRC, EV, EV_CAM):
    for p in sorted(Path(root).rglob('*')):
        if p.is_file() and not p.name.endswith('.bak'):
            rel = str(p.relative_to(ROOT)).replace('\\', '/')
            files.append((rel, sha(p)))

boundary = {
    'scope': 'HF-REAL-03 r03',
    'baseline_head': '026e06303f60ed1bbe4ddc4d037836db68da6d27',
    'baseline_branch': 'master',
    'r02_source_unmodified_files': [
        'sidequests/human_fusion_lab_next/real_fall/r02/track_v2.py',
        'sidequests/human_fusion_lab_next/real_fall/r02/skeleton_v2.py',
        'sidequests/human_fusion_lab_next/real_fall/r02/render_v2.py',
        'sidequests/human_fusion_lab_next/real_fall/r02/views_example',
        'docs/human_fall/evidence/2026-10-13_hf_real_02_r1/process_v2.json',
    ],
    'r02_source_sha_snapshot': {f: sha(ROOT / f) for f in [
        'sidequests/human_fusion_lab_next/real_fall/r02/track_v2.py',
        'docs/human_fall/evidence/2026-10-13_hf_real_02_r1/process_v2.json',
        'docs/human_fall/evidence/2026-10-13_hf_real_02_r1/cap_20261013_094333_foreground.bin',
        'docs/human_fall/evidence/2026-10-13_hf_real_01_r1/cap_20261013_093958_leveling.json',
    ]},
    'files_written_this_round': files,
}
(EV / 'SOURCE_AND_END_BOUNDARY.json').write_text(json.dumps(boundary, ensure_ascii=False, indent=1), encoding='utf8')

artifacts = {fp: sh for fp, sh in files if fp.startswith('docs/human_fall/evidence/2026-10-13_hf_real_03_r1/')}
artifacts['_scope'] = 'artefacts written by HF-REAL-03 R1 (relpath -> sha256)'
(EV / 'ARTIFACTS_FINAL_SHA.json').write_text(json.dumps(artifacts, ensure_ascii=False, indent=1), encoding='utf8')
print('files:', len(files), 'artifacts:', len(artifacts))
