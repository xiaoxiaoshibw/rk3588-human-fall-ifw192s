"""Independent post-submission source identity audit; no author writes."""
import hashlib
import json
from pathlib import Path
import sys
import numpy as np

OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[3]
sys.path.insert(0,str(ROOT/'src/human_fall_detection'))
from core.capture_input import load_adapted

r=OUT/'research_01'
submission=json.loads((r/'11_submission_manifest.json').read_text(encoding='utf8'))
mismatches=[p for p,h in submission['files'].items()
    if hashlib.sha256((ROOT/p).read_bytes()).hexdigest()!=h]
assert not mismatches,mismatches
manifest,points=load_adapted(str(ROOT/'docs/human_fall/evidence/2026-10-03_gl_i02_r1/08_real/real_candidate.adapted.npz'))
html=(r/'spatial_02/source_review.html').read_text(encoding='utf8')
payload=json.loads(html.split('<script>const D=',1)[1].split(';</script>',1)[0])
checked=0
for key,rows in payload['records'].items():
    box,group=key.split('\n')
    meta=manifest['frame_groups'][group]
    assert len(rows)==payload['stats'][key]['count']
    frame=next(f for f in payload['frames'] if f['frame_group']==group)
    assert frame['ordinal']==meta['ordinal'] and frame['seq']==meta['seq']
    for row,local,xyz in rows:
        assert meta['rows'][0]<=row<meta['rows'][1]
        assert local==row-meta['rows'][0]
        assert np.array_equal(np.asarray(xyz),points[row].astype(np.float64))
        checked+=1
ledger=json.loads((r/submission['active_ledger']).read_text(encoding='utf8'))
cases=ledger['synthetic']+ledger['real_WHAT_IF']
assert all(e['sequence_sha256']==e['old_sequence_sha256']==e['prototype_sequence_sha256'] for e in cases)
assert all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h
           for p,h in ledger['implementation_sha256'].items())
result=dict(kind='codex_post_submission_identity_audit',manifest_mismatches=mismatches,
    source_xyz_exact_rows=checked,frames=len(payload['frames']),box_frames=len(payload['records']),
    all_case_sequence_digest_parity=True,all_fullpath_implementation_shas_match=True,
    B01='BLOCKED',B02='BLOCKED',D01='NOT_RUN',D02='NOT_RUN')
with (OUT/'21_codex_source_audit.json').open('x',encoding='utf8') as f:json.dump(result,f,indent=2)
print(json.dumps(result))
