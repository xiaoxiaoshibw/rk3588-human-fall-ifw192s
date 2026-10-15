from pathlib import Path
import json,gzip,sys
import numpy as np
r=Path('D:/Code/ldiar');ps=r/'sidequests/human_fusion_lab_next/pointset/r01';sys.path.insert(0,str(ps))
from actions import load,read,dump
sid='cap_20261010_180557';e=r/'docs/human_fall/evidence/2026-10-14_hf_mainline_points_r1';folder=e/'js_02'/sid;m=read(folder/'MANIFEST.json');meta,raw,hashes=load(sid)
counts={};lowcounts={}
for fi,f in enumerate(meta['frames']):
 humans=np.array([i for row in read(ps/'output'/sid/f'{fi:04d}.json')['reference'] for i in row['source_indices']],int)
 if not len(humans):continue
 q=raw[f['offset_points']:f['offset_points']+f['count_points']].astype('f8');p=q@np.array(m['R']).T+m['t'];low=humans[p[humans,2]<.1]
 for arm in ['C_V2_DIAGNOSTIC','C_b0.1_e0.1','C_b0.1_e-0.25','C_b-0.25_e0.1','C_b-0.25_e-0.25']:
  stage=np.frombuffer(gzip.decompress((folder/f'{fi:04d}_{arm}.stage.gz').read_bytes()),dtype='u1')
  counts.setdefault(arm,{str(i):0 for i in range(1,11)});lowcounts.setdefault(arm,{str(i):0 for i in range(1,11)})
  for i in range(1,11):counts[arm][str(i)]+=int(np.sum(stage[humans]==i));lowcounts[arm][str(i)]+=int(np.sum(stage[low]==i))
dump(e/'JS_LABEL_DELETION_CAUSES.json',{'full_partial_labels':counts,'z_below_point1':lowcounts,'denominator':57045,'low_denominator':1163,'note':'Native XY cleanup stages7..10 differ from original AB largest XYZ scoring; early source/range/height/background reasons1..6 are identical actual checks, not counterfactual.'})
print(json.dumps(lowcounts))
