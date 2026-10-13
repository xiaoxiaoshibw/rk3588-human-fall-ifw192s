"""Visually initialized single-target offline tracking, unverified fall alerts."""
from collections import deque
import hashlib
import json
import sys
import numpy as np
from paths import ROOT, OUT
sys.path.insert(0, str(ROOT/'src/human_fall_detection'))
from core.features import FeatureExtractor
from core.fall_state import FallStateMachine

SID='cap_20261013_094333'
CONFIG={'voxel_m': .08, 'cell_min_points': 2, 'component_min_points': 80,
        'association_gate_m': .65, 'seed_xy': [2.2,1.6], 'max_gap_s': .5,
        'alert_p90_max_m': .65, 'alert_extent_z_max_m': .75, 'alert_hold_s': 1.5}


def components(points, cfg=CONFIG):
    good=np.isfinite(points[:,:3]).all(axis=1)
    valid=np.flatnonzero(good)
    xyz=points[valid,:3]
    keys=np.floor(xyz/cfg['voxel_m']).astype('i4')
    cells={}
    for idx,key in zip(valid,keys):
        cells.setdefault(tuple(key),[]).append(int(idx))
    cells={k:v for k,v in cells.items() if len(v)>=cfg['cell_min_points']}
    remaining=set(cells);out=[]
    while remaining:
        seed=min(remaining);remaining.remove(seed);queue=deque([seed]);rows=[]
        while queue:
            key=queue.popleft();rows.extend(cells[key])
            for dx in (-1,0,1):
                for dy in (-1,0,1):
                    for dz in (-1,0,1):
                        neighbor=(key[0]+dx,key[1]+dy,key[2]+dz)
                        if neighbor in remaining:
                            remaining.remove(neighbor);queue.append(neighbor)
        if len(rows)>=cfg['component_min_points']:
            rows=np.array(sorted(rows),dtype='i4');p=points[rows,:3]
            out.append({'rows':rows,'center':np.median(p,axis=0),'count':len(rows)})
    return out


def run():
    manifest=json.loads((OUT/(SID+'_foreground.json')).read_text(encoding='utf8'))
    blob=(OUT/(SID+'_foreground.bin')).read_bytes()
    assert hashlib.sha256(blob).hexdigest()==manifest['data_sha256']
    points=np.frombuffer(blob,dtype='<f4').reshape(-1,4)
    binding=dict(session_id=SID,track_id='REAL-01',time_epoch=0,action_generation=1,
                 selection_version=1,calibration_version='offline-'+manifest['source']['meta_sha256'])
    features=FeatureExtractor(SID);machine=FallStateMachine(SID)
    baseline=None;stance=[];center=np.array(CONFIG['seed_xy']);last_seen=None
    rows=[];events=[];low_since=None;episode=False;recover_since=None;lost=False
    for f in manifest['frames']:
        i,t=f['frame'],f['t'];p=points[f['offset']:f['offset']+f['count']]
        candidate=None;selected=None;comp=[]
        if not lost:
            comp=components(p)
            choices=[c for c in comp if np.linalg.norm(c['center'][:2]-center)<=CONFIG['association_gate_m']]
            if last_seen is None:
                choices=[c for c in choices if np.quantile(p[c['rows'],2],.9)>1.2 and np.median(p[c['rows'],2])>.7 and np.ptp(p[c['rows'],2])>.8]
            if choices:
                selected=min(choices,key=lambda c:(np.linalg.norm(c['center'][:2]-center),-c['count']))
                original_rows=selected['rows'].copy();q=p[original_rows,:3];removed=0
                center=selected['center'][:2];last_seen=t
                med,p10,p90=np.quantile(q[:,2],[.5,.1,.9]);extent=np.ptp(q,axis=0)
                values,vectors=np.linalg.eigh(np.cov(q.T));axis=vectors[:,-1]
                ambiguous=values[-1]<=0 or values[-1]/max(values[-2],1e-9)<1.2
                candidate={'ground_relative_available':True,'height_m':{'median':float(med),'p10':float(p10),'p90':float(p90)},
                           'horizontal_extent_m':{'max':float(max(extent[:2]))},'axis':{'ambiguous':bool(ambiguous),'verticality':None if ambiguous else float(abs(axis[2]))},
                           'point_count':len(q)}
                if baseline is None and p90>1.2 and med>.7:
                    stance.append((t,float(med)))
                    if len(stance)>=6 and t-stance[0][0]>=.5:
                        baseline=dict(binding,status='ready',baseline_version=1,height_m={'median':float(np.median([v for _,v in stance]))})
            elif last_seen is not None and t-last_seen>CONFIG['max_gap_s']:
                lost=True  # no silent reassignment to furniture after prolonged loss
        obs=dict(binding,source_stamp_s=t,track_status='locked' if selected else 'lost',
                 position_predicted=False,candidate=candidate)
        feat=features.update(obs,baseline);state=machine.update(feat,obs,baseline)
        alert=False
        if selected is not None:
            low=candidate['height_m']['p90']<=CONFIG['alert_p90_max_m'] and float(extent[2])<=CONFIG['alert_extent_z_max_m']
            if low and baseline is not None and state['state']=='suspected':
                if low_since is None:low_since=t
                if t-low_since>=CONFIG['alert_hold_s'] and not episode:
                    events.append({'id':'REAL-01-%d'%(len(events)+1),'frame':i,'t':t,'kind':'prototype_fall_alert','verified':False})
                    episode=True;alert=True
            else:low_since=None
            if baseline and candidate['height_m']['p90']>1.2 and candidate['height_m']['median']>.7:
                if recover_since is None:recover_since=t
                if t-recover_since>=1:episode=False
            else:recover_since=None
        else:low_since=None;recover_since=None
        rows.append({'frame':i,'t':t,'observed':selected is not None,'track_id':'REAL-01' if selected else None,
                     'reason':('prolonged_loss_requires_reselection' if lost else ('measured' if selected else 'no_associated_component')),
                     'source_fg_indices':[] if selected is None else selected['rows'].tolist(),
                     'center':None if selected is None else selected['center'].tolist(),
                     'candidate':candidate,'features':feat,'state':state,'prototype_alert':alert,'alert_active':episode,'bbox':None if selected is None else {'min':q.min(axis=0).tolist(),'max':q.max(axis=0).tolist()},
                     'upright_removed_points':0 if selected is None else removed,'extent':None if selected is None else extent.tolist(),'component_count':len(comp)})
    result={'sid':SID,'config':CONFIG,'initialization':'assistant visually selected seed; not fully automatic human detection',
            'background':manifest['background'],'confirmed_enabled':False,'events':events,'rows':rows,
            'limits':['development session only','assistant visual inference is not human GT','active lying indistinguishable','occlusion and nearby furniture may contaminate or lose target']}
    payload=json.dumps(result,ensure_ascii=False,allow_nan=False,separators=(',',':')).encode()
    with (OUT/(SID+'_tracking.json')).open('xb') as f:f.write(payload)
    print(json.dumps({'frames':len(rows),'observed':sum(r['observed'] for r in rows),'events':events,'states':sorted(set(r['state']['state'] for r in rows))},ensure_ascii=False))


if __name__=='__main__':
    if len(sys.argv)>1:SID=sys.argv[1]
    run()
