"""Examine measured principal transverse axis and current support partitions."""
import json
import numpy as np
from experiment import source, roi
from common import EV, SK, save, jsonlines

src=source();records=jsonlines(EV/'FG_OLD_FRAMES.jsonl');out=[]
with np.load(EV/'FOREGROUND_LEDGER.npz',allow_pickle=False) as z:ledger={k:z[k] for k in z.files}
try:
    for fi,r in enumerate(records):
        p,rows=roi(src.frame(fi));sl=slice(ledger['indptr'][fi],ledger['indptr'][fi+1]);p=p[ledger['keep'][sl]]
        if r['axis'] is None or r['basis_lateral'] is None or len(p)<30:continue
        center=p.mean(0);values,vectors=np.linalg.eigh(np.cov((p-center).T));lat=np.asarray(r['basis_lateral']);axis=np.asarray(r['axis']);depth=np.cross(lat,axis)
        angle=float(np.degrees(np.arccos(np.clip(abs(lat@vectors[:,-2]),0,1))))
        local=(p-center)@np.column_stack([lat,depth,axis]);lo,hi=np.quantile(local[:,2],[.02,.98]);fraction=(local[:,2]-lo)/(hi-lo)
        chest=p[(fraction>=.52)&(fraction<.70)]
        out.append(dict(fi=fi,pca_values=values.tolist(),old_lateral_angle_to_second_pca_deg=angle,old_lateral=lat.tolist(),second_pca=vectors[:,-2].tolist(),chest_selected_count=len(chest),chest_span_local=None if not len(chest) else np.ptp((chest-center)@np.column_stack([lat,depth,axis]),0).tolist(),chest_reason=r['nodes']['CHEST']['reason'],outer_a=r['nodes']['OUTER_A']))
finally:src.close()
save('FOREGROUND_OLD_MECHANISM.json',dict(frames=out,hold_angle_quantiles=np.quantile([r['old_lateral_angle_to_second_pca_deg'] for r in out if 183<=r['fi']<334],[0,.5,1]).tolist(),cases=[r for r in out if r['fi'] in (183,188,189,250,333)]))
