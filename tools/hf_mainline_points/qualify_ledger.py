"""Append exact candidate-rejection reasons without rewriting the initial ledger."""
import sys,time
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[2];PS=ROOT/'sidequests/human_fusion_lab_next/pointset/r01';sys.path.insert(0,str(PS))
from actions import read,dump,sha,OUT
from core import roi_mask
from research_retention import E,RESULT


def main():
    while not (E/'BASELINE_REPRODUCTION.json').exists():time.sleep(2)
    baseline=read(E/'BASELINE_REPRODUCTION.json');folder=RESULT/baseline['baseline_id'];cat=read(OUT/'catalog.json');cfg=read(OUT/'RUN_MANIFEST.json')['config']
    summaries=[]
    for rec in cat['sessions']:
        sid=rec['session_id'];last=None;seen=None;last_t=None
        for fi in rec['available_frames']:
            base=read(OUT/sid/f'{fi:04d}.json');t=base['t_sec']
            if last_t is not None and (t<=last_t or t-last_t>cfg['max_gap_s']):last=None;seen=None
            if seen is not None and t-seen>cfg['max_gap_s']:last=None
            with np.load(folder/sid/f'{fi:04d}.npz') as a:
                p=a['xyz'];stage=a['first_terminal_reason'].copy();labels=a['cluster_id'];bits=np.zeros(len(p),dtype='u1')
                for g in np.unique(labels[labels>=0]):
                    ix=np.flatnonzero(labels==g);pts=p[ix];span=np.quantile(pts,.98,axis=0)-np.quantile(pts,.02,axis=0)
                    reasons=[len(ix)<cfg['person_min_points'],roi_mask(pts,cfg['roi_xy']).mean()<cfg['person_min_roi_fraction'],max(span)>cfg['person_max_span_m'],
                         np.quantile(pts[:,2],.9)<cfg['person_min_p90_m'],last is not None and np.linalg.norm(np.median(pts,axis=0)[:2]-last)>cfg['association_gate_m']]
                    bits[ix]=sum(1<<k for k,v in enumerate(reasons) if v)
                    eligible=bits[ix][0]==0;not_target=ix[stage[ix]!=10];stage[not_target]=9 if eligible else 8
                assert np.all(stage>0) and len(stage)==len(p)
                np.savez_compressed(folder/sid/f'{fi:04d}_qualification.npz',first_terminal_reason=stage,candidate_qualification_bits=bits)
                summaries.append({'sid':sid,'fi':fi,'qualification_rejected':int(np.sum(stage==8)),'unselected':int(np.sum(stage==9)),'source_count':len(stage)})
                ids=a['baseline_target'];
                if len(ids):last=np.median(p[ids],axis=0)[:2];seen=t
            last_t=t
        print('QUALIFIED',sid,flush=True)
    dump(E/'QUALIFIED_LEDGER.json',{'frames':summaries,'baseline_id':baseline['baseline_id'],'extension':'*_qualification.npz supersedes stage8/9 classification only; old archives preserved',
        'code_sha':sha(Path(__file__)),'candidate_bits':['PERSON_MIN_POINTS','ROI_FRACTION','MAX_SPAN','MIN_P90','ASSOCIATION_GATE'],
        'ROI_is_not_baseline_point_crop':True,'frame_source_count_conserved':True})


if __name__=='__main__':main()
