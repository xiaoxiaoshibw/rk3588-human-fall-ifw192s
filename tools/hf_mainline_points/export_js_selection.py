"""Full-member export of the fixed C XYZ scorer, separate from native XY cleanup."""
import sys,json,gzip
from pathlib import Path
import numpy as np
import yaml
ROOT=Path(__file__).resolve().parents[2];PS=ROOT/'sidequests/human_fusion_lab_next/pointset/r01';sys.path.insert(0,str(PS))
from actions import read,load,dump
from core import cluster
E=ROOT/'docs/human_fall/evidence/2026-10-14_hf_mainline_points_r1'
def main():
 cfg=yaml.safe_load((PS/'config.yaml').read_text(encoding='utf8'));checked=[]
 for sid in ['cap_20261013_094333','cap_20261010_180557']:
  folder=E/'js_02'/sid;export=folder/'selection_v2';export.mkdir(exist_ok=False);meta,raw,_=load(sid);m=read(folder/'MANIFEST.json');rows=0
  with (folder/'members.jsonl').open(encoding='utf8') as lines:
   for line in lines:
    row=json.loads(line);fi=row['frame'];f=meta['frames'][fi];q=raw[f['offset_points']:f['offset_points']+f['count_points']].astype('f8');p=q@np.array(m['R']).T+m['t']
    fg=np.array(row['arms']['C_V2_DIAGNOSTIC'],int);groups,_=cluster(p[fg],cfg);ids=fg[max(groups,key=len)] if groups else np.empty(0,int)
    stage=np.frombuffer(gzip.decompress((folder/f'{fi:04d}_C_V2_DIAGNOSTIC.stage.gz').read_bytes()),dtype='u1').copy()
    stage[fg]=7
    for g in groups:stage[fg[g]]=9
    stage[ids]=10
    np.savez_compressed(export/f'{fi:04d}_C_AB_XYZ_selected.npz',target=ids.astype('u4'),first_terminal_reason=stage)
    assert np.all(stage>0) and len(stage)==len(q);rows+=1
  checked.append({'sid':sid,'frames':rows});print('EXPORTED JS C',sid,rows,flush=True)
 dump(E/'JS_SELECTION_EXPORT_V2.json',{'sessions':checked,'baseline':'C_V2_DIAGNOSTIC','codes':{1:'NONFINITE',2:'ZERO',3:'RANGE',4:'HEIGHT_LOW',5:'HEIGHT_HIGH',6:'BACKGROUND_MATCH',7:'XYZ_CLUSTER_NOISE_MIN_POINTS',9:'UNSELECTED_XYZ_CLUSTER',10:'TARGET_LARGEST_XYZ'},
    'native_XY_cleanup':'NOT_APPLICABLE in frozen AB scorer; native XY ledger remains separate','identity':'UNKNOWN except scored bound partial labels','GT_used_for_selection':False})
if __name__=='__main__':main()
