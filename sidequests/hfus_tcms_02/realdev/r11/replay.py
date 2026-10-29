"""Replay all original 780 frames with exact candidate source-row membership.

Only association/lifecycle changes; reuse the original transform, estimate,
axis/display history and CalibrationLayer through r08.process_track.
"""
import json
import sys
import time
import numpy as np
from common import W, SK, ROOT, EV, save, jsonlines, sha
from association import associate_tracks, expire, OLD

BASE = ROOT/'docs/human_fall/evidence/2026-10-18_hfus_human_skeleton_02_r1/RUN_R4'

def run():
    start=time.perf_counter()
    old=jsonlines(BASE/'frames.jsonl')
    src,times=W.load_source()
    transform=W.r04_transform().Transform(W.load(W.S3/'TRANSFORM/TRANSFORM_S3.json'))
    tracks={};active=[];seq=0;records=[];deltas=[]
    try:
        for fi,prior in enumerate(old):
            f=src.frame(fi);t=times[fi]
            local=transform.points(f['xyz'],transform.tag(fi,False),fi,source_validity=True)
            with np.load(BASE/'frames'/('%04d.npz'%fi),allow_pickle=False) as z:
                labels=z['candidate'];candidates=[]
                for c in prior['candidate_summaries']:
                    rows=np.flatnonzero(labels==c['engine_id'])
                    assert len(rows)==c['count']
                    candidates.append(dict(candidate_id=c['candidate_id'],engine_id=c['engine_id'],position_m=c['center'],size_m=c['size_m'],count=c['count'],rows=rows.tolist()))
            active=expire(active,fi,t,W.TTL_S)
            a=associate_tracks([dict(track_id=tr['id'],position_m=tr['center'].tolist(),size_m=tr['size_m']) for tr in active],candidates,dt_s=0 if not fi else t-times[fi-1])
            byid={c['candidate_id']:c for c in candidates}
            matches={m['track_id']:m['candidate_id'] for m in a['matches']}
            results=[]
            for tr in active:
                cid=matches.get(tr['id'])
                state='MATCHED' if cid is not None else ('AMBIGUOUS' if tr['id'] in a['ambiguous_track_ids'] else 'UNMATCHED')
                if tr['state']!=state:tr['events'].append(dict(fi=fi,old=tr['state'],new=state,reason='ASSOCIATION_'+state))
                tr['state']=state
                if cid is None:continue
                assert cid not in a['ambiguous_candidate_ids']
                c=byid[cid];tr['center']=np.asarray(c['position_m']);tr['size_m']=c['size_m']
                results.append(W.process_track(tr,c,fi,t,f,local,SK,0 if not fi else t-times[fi-1]))
                tr['last_t']=t;tr['last_fi']=fi;tr['matched_frames']+=1
            for cid in a['unmatched_candidate_ids']:
                assert cid not in a['ambiguous_candidate_ids']
                seq+=1;tr=W.make_new_track('U%04d'%seq,byid[cid],t,fi,SK.EDGES)
                tracks[tr['id']]=tr;active.append(tr)
                r=W.process_track(tr,byid[cid],fi,t,f,local,SK,0 if not fi else t-times[fi-1]);r['association_event']='SEEDED_FROM_UNMATCHED_CANDIDATE';results.append(r)
            best=max([r['valid_nodes'] for r in results],default=0)
            rec=dict(fi=fi,relative_s=t,phase=prior['phase'],association=a,candidate_summaries=prior['candidate_summaries'],track_results=results,best_valid_nodes=best,states={k:dict(state=tr['state'],last_measurement_frame=tr['last_fi']) for k,tr in tracks.items()})
            records.append(rec)
            illegal=[r['candidate_id'] for r in prior['track_results'] if r['candidate_id'] in prior['association']['ambiguous_candidate_ids']]
            deltas.append(dict(fi=fi,phase=prior['phase'],candidates=len(candidates),old_best=prior['best_valid_nodes'],new_best=best,old_association=prior['association'],new_association=a,old_tracks=[dict(track_id=r['track_id'],candidate_id=r['candidate_id'],valid_nodes=r['valid_nodes'],edges=r['edges']) for r in prior['track_results']],new_tracks=[dict(track_id=r['track_id'],candidate_id=r['candidate_id'],valid_nodes=r['valid_nodes'],edges=r['edges']) for r in results],old_illegal_candidate_measurements=illegal,changed=prior['best_valid_nodes']!=best or prior['association']!=a))
            if fi%100==0:print('replay',fi,flush=True)
    finally:src.close()
    save('ASSOCIATION_FRAMES.jsonl',''.join(json.dumps(r,separators=(',',':'),allow_nan=False)+'\n' for r in records))
    save('ASSOCIATION_DIFF.jsonl',''.join(json.dumps(r,separators=(',',':'),allow_nan=False)+'\n' for r in deltas))
    summaries={k:dict(state=tr['state'],events=tr['events'],first_fi=tr['first_fi'],last_fi=tr['last_fi'],skeleton_frames=tr['skeleton_frames'],calibration=tr['calibration'].summary()) for k,tr in tracks.items()}
    save('ASSOCIATION_TRACKS.json',summaries)
    action=[r for r in records if r['phase']=='ACTION']
    out=dict(frames=len(records),candidate_membership='exact original source row ledger, unchanged candidate summaries; S06 envelope not used',action_frames=len(action),action_candidates=sum(bool(r['candidate_summaries']) for r in action),old_six=sum(r['phase']=='ACTION' and r['best_valid_nodes']>=6 for r in old),new_six=sum(r['best_valid_nodes']>=6 for r in action),old_illegal_measurements=sum(len(r['old_illegal_candidate_measurements']) for r in deltas),new_illegal_measurements=sum(r['candidate_id'] in f['association']['ambiguous_candidate_ids'] for f in records for r in f['track_results']),changed_frames=[r['fi'] for r in deltas if r['changed']],ambiguous_frames=sum(bool(r['association']['ambiguous_candidate_ids']) for r in records),track_count=len(tracks),ever_calibrated_track_edges=sum(tr['calibration']['ever_calibrated_edges'] for tr in summaries.values()),unique_ever_calibrated_edges=sorted({k for tr in summaries.values() for k,e in tr['calibration']['edges'].items() if e['ever_calibrated']}),seconds=time.perf_counter()-start,source_sha={n:sha(W.SOURCE/n) for n in ('meta.json','points.bin')})
    save('ASSOCIATION_SUMMARY.json',out);print(json.dumps(out),flush=True)

if __name__=='__main__':run()
