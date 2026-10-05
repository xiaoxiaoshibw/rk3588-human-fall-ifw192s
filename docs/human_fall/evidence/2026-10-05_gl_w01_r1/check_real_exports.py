"""Read-only independent all-row / coordinate checks for the real browser exports."""
import hashlib
import json
import math
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
JOB = ROOT / 'captures/leveled/8b3bbb66b48e4ff5a83c12e589919420'
report = json.loads((JOB/'report.json').read_text('utf-8'))
directory = ROOT / 'captures/remote' / report['sid']

def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for b in iter(lambda:stream.read(1048576),b''):h.update(b)
    return h.hexdigest()

assert report['source'] == {'meta_sha256':sha(directory/'meta.json'),'bin_sha256':sha(directory/'points.bin')}
raw = np.memmap(directory/'points.bin',mode='r',dtype='u1').reshape(-1,28)
source = np.ndarray((len(raw),3),dtype='<f4',buffer=raw,strides=(28,4))
checks = []
for method in ('tls','svd','ransac'):
    model = json.loads((JOB/method/'transform.json').read_text('utf-8'))
    p,r = math.radians(model['pitch_deg']),math.radians(model['roll_deg'])
    # Independent Rx @ Ry; no workbench import / helper reuse.
    rx = np.array([[1,0,0],[0,math.cos(r),-math.sin(r)],[0,math.sin(r),math.cos(r)]])
    ry = np.array([[math.cos(p),0,math.sin(p)],[0,1,0],[-math.sin(p),0,math.cos(p)]])
    R = rx @ ry; t = np.array(model['t'])
    assert abs(np.linalg.det(R)-1)<1e-10
    assert np.allclose(R,model['R'],atol=1e-12) and t[0]==0 and t[1]==0
    assert not any(model[k] for k in ('physical_verified','extrinsics_verified','runtime_eligible'))
    target = np.memmap(JOB/method/'points.bin',mode='r',dtype='u1').reshape(-1,28)
    xyz = np.ndarray((len(target),3),dtype='<f4',buffer=target,strides=(28,4))
    maximum, inverse, valid_count = 0.,0.,0
    for lo in range(0,len(raw),65536):
        hi = min(lo+65536,len(raw)); a,b = source[lo:hi],xyz[lo:hi]
        valid = np.isfinite(a).all(axis=1)&np.any(a!=0,axis=1)
        assert np.array_equal(raw[lo:hi,12:],target[lo:hi,12:])
        assert np.array_equal(raw[lo:hi][~valid],target[lo:hi][~valid])
        expected = a[valid].astype(float)@R.T+t
        maximum = max(maximum,float(np.abs(expected-b[valid]).max()))
        inverse = max(inverse,float(np.abs((b[valid].astype(float)-t)@R-a[valid]).max()))
        valid_count += int(valid.sum())
    assert maximum<2e-5 and inverse<2e-5
    original = json.loads((directory/'meta.json').read_text('utf-8'))
    derived = json.loads((JOB/method/'meta.json').read_text('utf-8'))
    assert original['frames']==derived['frames'] and original['total_points']==derived['total_points']
    checks.append({'method':method,'rows':len(raw),'valid_rows':valid_count,'forward_max_m':maximum,
                   'inverse_max_m':inverse,'opaque_bytes':'PASS','frame_table':'PASS','original_sha':'PASS'})
with (OUT/'14_real_all_rows.json').open('x',encoding='utf-8') as stream:
    json.dump(checks,stream,indent=2)
print(json.dumps(checks,indent=2))
