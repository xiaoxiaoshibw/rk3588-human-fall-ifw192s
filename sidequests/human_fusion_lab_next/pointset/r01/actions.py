"""Extend pointset r01: frozen XYZ background, causal central-person association."""
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import yaml
from scipy.spatial import cKDTree

from core import R, T, cluster, independence, roi_mask, skeleton

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
OUT=HERE/'action_output'
EVIDENCE=ROOT/'docs/human_capture/evidence/2026-10-14_hfus_pointset_actions_r1'


def read(p): return json.loads(Path(p).read_text(encoding='utf8'))


def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(1<<20),b''):h.update(b)
    return h.hexdigest()


def dump(p,obj):
    with Path(p).open('x',encoding='utf8') as f:
        json.dump(obj,f,ensure_ascii=False,allow_nan=False,separators=(',',':'))


def load(sid):
    folder=ROOT/'captures/remote'/sid;m=read(folder/'meta.json')
    if m['point_stride_bytes']!=28 or (folder/'points.bin').stat().st_size!=m['total_points']*28:raise ValueError('Bad source contract')
    end=0;stamps=[]
    for f in m['frames']:
        if f['offset_points']!=end or f['count_points']<0:raise ValueError('Bad frame')
        end+=f['count_points'];stamps.append(f['stamp_sec']+f['stamp_nanosec']*1e-9)
    if end!=m['total_points'] or np.any(np.diff(stamps)<=0):raise ValueError('Bad time')
    buf=np.memmap(folder/'points.bin',dtype='u1',mode='r')
    xyz=np.ndarray((m['total_points'],3),dtype='<f4',buffer=buf,strides=(28,4))
    return m,xyz,{'meta':sha(folder/'meta.json'),'points':sha(folder/'points.bin')}


class Posture:
    """No session/action-name input, no future frames, no medical fall confirmation."""
    def __init__(self,cfg):
        self.cfg=cfg;self.last=None;self.history=[];self.low_since=None;self.stood=False;self.emitted=False

    def update(self,t,points):
        gap=self.last is not None and (t<=self.last or t-self.last>self.cfg['max_gap_s'])
        if gap:self.history=[];self.low_since=None;self.stood=False;self.emitted=False
        self.last=t
        if points is None:
            self.low_since=None;self.history=[]
            return {'state':'LOST','event':None,'confirmed':False,'time_reset':gap}
        med,p90=np.quantile(points[:,2],[.5,.9]);span=np.quantile(points,.98,axis=0)-np.quantile(points,.02,axis=0)
        horizontal=max(span[:2]);low=p90<=self.cfg['lying_p90_m'] and horizontal>=self.cfg['lying_min_extent_xy_m'] and span[2]<=self.cfg['lying_max_extent_z_m']
        upright=p90>=self.cfg['standing_p90_m'] and span[2]>=self.cfg['standing_extent_z_m']
        if upright:self.stood=True;self.emitted=False
        velocity=None
        past=[v for v in self.history if t-v[0]>=self.cfg['velocity_window_s']]
        if past:
            a=past[-1];velocity=float((med-a[1])/(t-a[0]))
        self.history.append((t,float(med)));self.history=[a for a in self.history if t-a[0]<=self.cfg['history_s']]
        event=None
        if low:
            if self.low_since is None:self.low_since=t
            sustained=t-self.low_since>=self.cfg['lying_hold_s']
            state=('LYING' if self.stood else 'INITIAL_LOW_POSTURE') if sustained else 'LOW_PENDING'
            if sustained and self.stood and not self.emitted:
                event='DOWN_POSTURE_CANDIDATE';self.emitted=True
        else:
            self.low_since=None
            state='STANDING' if upright else ('DESCENDING' if velocity is not None and velocity < -self.cfg['descent_speed_mps'] else 'CROUCH_OR_SIT')
        return {'state':state,'event':event,'confirmed':False,'time_reset':gap,'height_median':float(med),
                'height_p90':float(p90),'extent':span.tolist(),'vertical_velocity_mps':velocity,
                'reason':'Ground-relative geometry; controlled lying/fall cannot be separated without independent evidence'}


def choose(groups,p,fg,cfg,last,dt):
    choices=[]
    for i,g in enumerate(groups):
        q=p[fg[g]];center=np.median(q,axis=0);lo,hi=np.quantile(q,[.02,.98],axis=0);span=hi-lo
        fraction=float(roi_mask(q,cfg['roi_xy']).mean())
        if len(g)<cfg['person_min_points'] or fraction<cfg['person_min_roi_fraction']:continue
        if max(span)>cfg['person_max_span_m'] or np.quantile(q[:,2],.9)<cfg['person_min_p90_m']:continue
        distance=float(np.linalg.norm(center[:2]-last)) if last is not None else 0
        if last is not None and distance>cfg['association_gate_m']:continue
        rank=len(g)*fraction/(1+distance/cfg['association_scale_m'])
        choices.append((rank,i,center,fraction))
    if not choices:return None
    return max(choices,key=lambda c:c[0])


def describe_object(p,ids,dist,others,tau,cfg,ident):
    q=p[ids];count=min(len(ids),cfg['display_sample_points'])
    sample=np.linspace(0,len(ids)-1,count,dtype=int)
    score=independence(q,dist[ids],others,tau,cfg)
    score['separation_status']='GEOMETRICALLY_SEPARATE' if score['dense_core_fraction']>=.75 else 'CONTACT_OR_FRAGMENTATION'
    return {'id':ident,'kind':'AUTOMATIC_CANDIDATE','points':np.round(q[sample],4).tolist(),
        'display_source_indices':ids[sample].tolist(),'source_indices':ids.tolist(),'point_count':len(ids),
        'bbox':{'min':q.min(axis=0).tolist(),'max':q.max(axis=0).tolist()},'skeleton':skeleton(q,ids,cfg),
        'roi_point_fraction':float(roi_mask(q,cfg['roi_xy']).mean()),'independence':score,
        'pointnet_prob':0.,'rf_xyz_prob':0.,'model_status':'NOT_USED_GEOMETRY_AND_CAUSAL_ASSOCIATION',
        'semantic_identity':'AI_INFERRED_SINGLE_PERSON_CANDIDATE_NOT_GT'}


def main():
    if OUT.exists():raise ValueError('Exclusive new action_output required')
    OUT.mkdir()
    cfg=yaml.safe_load((HERE/'config.yaml').read_text(encoding='utf8'))
    cfg.update(yaml.safe_load((HERE/'config_actions.yaml').read_text(encoding='utf8')))
    prior=Path(cfg['background_experiment']);manifest=read(prior/'manifest.json');bgmeta=read(prior/'background.json')
    bgfile=prior/'background.npz';tree=cKDTree(np.load(bgfile)['xyz']);tau=bgmeta['tolerance_m']
    _,_,refhash=load(manifest['reference'])
    assert refhash=={'meta':manifest['reference_sha256']['meta.json'],'points':manifest['reference_sha256']['points.bin']}
    sessions=[];reports=[]
    for record in manifest['sessions']+[{'sid':manifest['reference'],'name':'空场独立留帧','frames':97}]:
        sid=record['sid'];m,raw,hashes=load(sid);folder=OUT/sid;folder.mkdir()
        is_empty=sid==manifest['reference'];alignment=None if is_empty else read(prior/(sid+'_registration.json'))
        if alignment and alignment['gate']['status']!='PASS':raise ValueError('Rejected numerical alignment cannot supply this candidate replay')
        if not is_empty:assert hashes=={'meta':record['source_sha256']['meta.json'],'points':record['source_sha256']['points.bin']}
        state=Posture(cfg);last_center=None;last_t=None;last_seen=None;track_generation=0;rows=[];events=[];ids_all=[];offsets=[0]
        t0=m['frames'][0]['stamp_sec']+m['frames'][0]['stamp_nanosec']*1e-9
        for fi,f in enumerate(m['frames']):
            t=f['stamp_sec']+f['stamp_nanosec']*1e-9
            # Empty FIT/CAL are omitted entirely; only unconsumed temporal HOLDOUT is evaluated.
            if is_empty and fi%3!=2:continue
            rawp=raw[f['offset_points']:f['offset_points']+f['count_points']].astype('f8');radius=np.linalg.norm(rawp,axis=1)
            valid=np.isfinite(rawp).all(axis=1)&np.any(rawp!=0,axis=1)&(radius>cfg['range_min_m'])&(radius<cfg['range_max_m'])
            p=rawp@R.T+T
            if alignment:p=p@np.array(alignment['R']).reshape(3,3).T+alignment['t']
            domain=valid&(p[:,2]>=cfg['z_min_m'])&(p[:,2]<=cfg['z_max_m'])
            dist=np.full(len(p),np.inf);dist[domain]=tree.query(p[domain])[0]
            fg=np.flatnonzero(domain&(dist>tau));groups,_=cluster(p[fg],cfg)
            if last_t is not None and (t<=last_t or t-last_t>cfg['max_gap_s']):last_center=None;last_seen=None
            if last_seen is not None and t-last_seen>cfg['max_gap_s']:last_center=None
            winner=choose(groups,p,fg,cfg,last_center,None if last_t is None else t-last_t);last_t=t
            body=[];selected_ids=np.empty(0,dtype=int)
            if winner:
                _,index,center,_=winner;selected_ids=fg[groups[index]]
                if last_center is None:
                    if track_generation:state=Posture(cfg)
                    track_generation+=1
                last_center=center[:2];last_seen=t
                others=p[np.setdiff1d(fg,selected_ids)]
                body=[describe_object(p,selected_ids,dist,others,tau,cfg,'BODY-'+str(track_generation))]
            posture=state.update(t,p[selected_ids] if len(selected_ids) else None)
            if posture['event']:events.append({'frame':fi,'t_sec':t-t0,'kind':posture['event'],'confirmed':False})
            selection={'selected_source_indices':selected_ids.tolist(),'removed_background':int(np.count_nonzero(domain))-len(fg),
                       'rejected_foreground':len(fg)-len(selected_ids),'candidate_count':len(groups),'uses_future_action_points':False}
            sample=np.linspace(0,len(fg)-1,min(1800,len(fg)),dtype=int) if len(fg) else []
            row={'schema_version':'pointset-episode/1','session_id':sid,'frame_index':fi,'source_frame':f,'t_sec':t-t0,
                 'raw_count':f['count_points'],'background_removed':selection['removed_background'],'fg_count':len(fg),
                 'roi_fg_count':int(roi_mask(p[fg],cfg['roi_xy']).sum()),'foreground_display':np.round(p[fg[sample]],4).tolist(),
                 'body_3d':body,'full_3d':body,'roi_3d':body,'full_2d':[],'reference':[],
                 'metrics':{'body_3d':{'persons':[]},'full_3d':{'persons':[]},'roi_3d':{'persons':[]},'full_2d':{'persons':[]}},
                 'posture':posture,'selection':selection,'source_sha256':hashes,'coordinate_frame':'empty_nominal_pointset_frame',
                 'background_status':'NUMERICALLY_ALIGNED_OFFLINE_CANDIDATE_PHYSICAL_UNVERIFIED'}
            dump(folder/f'{fi:04d}.json',row)
            ids_all.append(selected_ids.astype('u4'));offsets.append(offsets[-1]+len(selected_ids))
            rows.append({'fi':fi,'t_sec':t-t0,'reference_persons':0,'selected_points':len(selected_ids),'fg_points':len(fg),
                         'state':posture['state'],'height_p90':posture.get('height_p90'),'candidate_count':len(groups),
                         'center':None if not winner else winner[2].tolist(),'valid_nodes':sum(n['valid'] for n in body[0]['skeleton']['nodes'].values()) if body else 0})
        np.savez_compressed(folder/'candidate_source_indices.npz',indices=np.concatenate(ids_all),offsets=np.array(offsets),frames=np.array([r['fi'] for r in rows]))
        summary={'frames':rows,'events':events,'observed_frames':sum(r['selected_points']>0 for r in rows),'evaluated_frames':len(rows),
                 'complete_human_precision':None,'confirmed_fall_events':None,'semantic_gt':'UNAVAILABLE'}
        dump(folder/'summary.json',summary);dump(folder/'action_report.json',summary)
        sessions.append({'session_id':sid,'activity':record['name'],'frame_count':len(m['frames']),'duration_sec':m['duration_sec'],
             'available_frames':[r['fi'] for r in rows],'source_sha256':hashes,'reference_status':'AI_INFERRED_NOT_MANUAL_GT'})
        reports.append({'session_id':sid,'roi_candidate_frames':summary['observed_frames'],'reference_frames':0,'events':events,
                        'evaluated_frames':len(rows),'state_counts':{name:sum(r['state']==name for r in rows) for name in sorted({r['state'] for r in rows})}})
        print(sid,summary['observed_frames'],'/',len(rows),'observed; events',events,flush=True)
        assert load(sid)[2]==hashes
    dump(OUT/'catalog.json',{'schema_version':'pointset-episode/1','dataset':'actions','sessions':sessions,'roi_xy':cfg['roi_xy'],
         'background':{'session':manifest['reference'],'sha256':refhash,'background_file_sha256':sha(bgfile),'tolerance_m':tau,
                       'note':'131958 new action scenes; S1 model is historical spatial/ROI context, not interchangeable foreground subtraction'},
         'scope':'offline candidate localization, no anatomical precision or medical fall confirmation'})
    dump(OUT/'action_catalog.json',reports);dump(OUT/'RUN_MANIFEST.json',{'config':cfg,'source_sha256':{s['session_id']:s['source_sha256'] for s in sessions},
        'command':sys.argv,'method':'unchanged pointset core + ROI membership ranking + bounded causal XY association + posture state',
        'physical_calibration':'UNVERIFIED','code_sha256':{n:sha(HERE/n) for n in ['actions.py','config_actions.yaml','core.py','config.yaml']}})


if __name__=='__main__':main()
