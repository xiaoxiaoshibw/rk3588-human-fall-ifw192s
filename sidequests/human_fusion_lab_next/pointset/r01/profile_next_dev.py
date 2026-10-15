"""Each group in a fresh process: CPU without tracing and true Windows process peak."""
import argparse
import copy
import sys
import time
from pathlib import Path
import numpy as np
from actions import read,dump,sha
from core import R,T,cluster,skeleton
from next_dev import CausalSelection,conditional_graph,quant,canonical_rules
from next_temporal import RecentAxis,RecentEvent,RecentNonLowEvent,WeakContinuation
from scene_change import FrozenSurfaces
from scene_static import static_reference_mask
from verify_next_dev import memory_peak
from next_contract import validate_frozen_inputs


def profile(e,group,output=None):
    manifest=validate_frozen_inputs(e);cfg=copy.deepcopy(manifest['config']);rows=[]
    code_sha256={n:sha(Path(__file__).parent/n) for n in ['profile_next_dev.py','next_dev.py','next_temporal.py','core.py','actions.py','scene_change.py','scene_static.py','next_contract.py']}
    base_temporal=read(e/'TEMPORAL_MANIFEST.json')['base_group']
    temporal=group in ['E_axis','F_event','F_event_r2','G_weak'];tag='old' if group in ['A','C'] else ('new_oldtau' if group=='B_tau' else 'new')
    if not temporal:
        with np.load(manifest['background_assets'][0]['path']) as d:reference=FrozenSurfaces(d['xyz'].copy(),manifest['old_tau'],copy.deepcopy(manifest['controls']))
        asset=manifest['background_assets'][0 if tag=='old' else 1]
        tau=manifest['old_tau'] if tag in ['old','new_oldtau'] else manifest['new_tau']
        with np.load(asset['path']) as d:model=FrozenSurfaces(d['xyz'].copy(),tau,copy.deepcopy(manifest['controls']))
    rule=canonical_rules(manifest['candidates'])[read(e/'SELECTION.json')['chosen_for_C_D_diagnostic']]
    for session in read(e/'catalog.json')['sessions']:
        sid=session['session_id'];state=CausalSelection(cfg);axis=RecentAxis(cfg);event=RecentNonLowEvent(cfg) if group=='F_event_r2' else RecentEvent(cfg);weak=WeakContinuation(cfg)
        reg=None if sid.startswith('cap_20261014') else read(Path(cfg['background_experiment'])/(sid+'_registration.json'))
        for fi in session['available_frames']:
            base_group=base_temporal if temporal else group
            record=read(e/'runs'/base_group/sid/f'{fi:04d}.json')
            group_record=read(e/'runs'/group/sid/f'{fi:04d}.json') if temporal else record
            with np.load(e/'common'/sid/f'{fi:04d}.npz') as d:raw=d['raw_xyz'];p=d['xyz'];valid=d['domain'];nominal_domain=d['nominal_domain']
            if temporal:
                with np.load(e/'runs'/base_group/sid/f'{fi:04d}_members.npz') as d:ids=d['selected'];fg=d['foreground'];labels=d['cluster_id'][fg]
                identity=record['body_3d'][0]['id'] if len(ids) else None
                sk=record['body_3d'][0]['skeleton'] if len(ids) else skeleton(p[ids],ids,cfg)
            started=time.process_time()
            if temporal:
                if group=='E_axis':axis.update(record['device_time'],fi,identity,p,ids,sk)
                elif group in ['F_event','F_event_r2']:event.update(record['device_time'],fi,identity,p,ids)
                else:
                    components=[np.flatnonzero(labels==i) for i in np.unique(labels) if i>=0]
                    weak.update(record['device_time'],components,p,fg)
            else:
                nominal=raw@R.T+T
                if reg:nominal=nominal@np.array(reg['R']).reshape(3,3).T+reg['t']
                anchor=static_reference_mask(nominal,nominal_domain,cfg['roi_xy'])
                _,vibration=reference.compensate(nominal[anchor],manifest['limits'])
                corrected=nominal@np.array(vibration['R']).T+vibration['t']
                foreground,_,dist,_,_=model.split_pose_hypotheses(nominal,corrected,valid)
                components,_=conditional_graph(corrected[foreground],cfg,rule,dist[foreground],model.tau) if group in ['C','D'] else cluster(corrected[foreground],cfg)
                selected,identity,posture,reset=state.update(record['device_time'],components,corrected,foreground)
                skeleton(corrected[selected],selected,cfg)
            elapsed=(time.process_time()-started)*1000
            current_ids=group_record['selection']['selected_source_indices']
            rows.append({'sid':sid,'fi':fi,'cpu_ms':elapsed,'state':group_record['posture']['state'],
                         'distance_m':float(np.linalg.norm(np.median(p[current_ids],axis=0))) if current_ids else None})
        print('PROFILE',group,sid,flush=True)
    dump(output or e/('PROFILE_'+group+'.json'),{'group':group,'frames':len(rows),'manifest_sha256':sha(e/'RUN_MANIFEST.json'),'CPU_ms':quant([r['cpu_ms'] for r in rows]),
         'by_session':{s['session_id']:quant([r['cpu_ms'] for r in rows if r['sid']==s['session_id']]) for s in read(e/'catalog.json')['sessions']},
         'by_posture':{s:quant([r['cpu_ms'] for r in rows if r['state']==s]) for s in sorted(set(r['state'] for r in rows))},
         'by_distance':{s:quant([r['cpu_ms'] for r in rows if r['distance_m'] is not None and lo<=r['distance_m']<hi]) for s,lo,hi in [('0_2m',0,2),('2_4m',2,4),('4plus',4,float('inf'))]},
         'process_memory_peak':memory_peak(),'rows':rows,'scope':'single temporal factor on frozen pointset' if temporal else 'coordinate/compensation/background/cluster/selector/skeleton/posture; excludes disk/hash/archive IO',
         'code_sha256':code_sha256,'command':sys.argv,'stage_status':'PROFILE_COMPLETED'})


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--evidence',type=Path,required=True);parser.add_argument('--group',choices=['A','B','B_tau','C','D','E_axis','F_event','F_event_r2','G_weak'],required=True)
    parser.add_argument('--output',type=Path);args=parser.parse_args();profile(args.evidence.resolve(),args.group,args.output)
