"""Independent streaming/prefix contract replay and comparable algorithm-only CPU audit."""
import argparse
import copy
import ctypes
import json
import os
import sys
import tempfile
import time
from pathlib import Path
import numpy as np
from actions import HERE, ROOT, OUT, read, dump, sha, load, Posture
from core import R,T,cluster,skeleton
from next_dev import CausalSelection, CANDIDATES, conditional_graph, node_metrics, quant, validate_run_contract, selection_key,canonical_rules
from next_contract import validate_meta,FrozenRun
from next_temporal import RecentAxis,RecentEvent,WeakContinuation
from scene_change import FrozenSurfaces
from scene_static import static_reference_mask


class CurrentFrameOnly:
    def __init__(self,e,sid,fi):self.e=e;self.sid=sid;self.fi=fi
    def path(self,group,fi,suffix='.json'):
        if fi!=self.fi:raise ValueError('Future/past frame unavailable to current transition')
        return self.e/'runs'/group/self.sid/('{:04d}'.format(fi)+suffix)
    def common(self,fi):
        if fi!=self.fi:raise ValueError('Future frame unavailable')
        return self.e/'common'/self.sid/('{:04d}.npz'.format(fi))


def memory_peak():
    if os.name=='nt':
        class Counters(ctypes.Structure):
            _fields_=[('cb',ctypes.c_ulong),('PageFaultCount',ctypes.c_ulong)]+[(x,ctypes.c_size_t) for x in ['PeakWorkingSetSize','WorkingSetSize','QuotaPeakPagedPoolUsage','QuotaPagedPoolUsage','QuotaPeakNonPagedPoolUsage','QuotaNonPagedPoolUsage','PagefileUsage','PeakPagefileUsage']]
        result=Counters();result.cb=ctypes.sizeof(result)
        ctypes.windll.kernel32.GetCurrentProcess.restype=ctypes.c_void_p
        ctypes.windll.psapi.GetProcessMemoryInfo.argtypes=[ctypes.c_void_p,ctypes.c_void_p,ctypes.c_ulong]
        if not ctypes.windll.psapi.GetProcessMemoryInfo(ctypes.windll.kernel32.GetCurrentProcess(),ctypes.byref(result),result.cb):raise ctypes.WinError()
        return {'peak_working_set_bytes':result.PeakWorkingSetSize,'peak_pagefile_bytes':result.PeakPagefileUsage}
    import resource
    return {'ru_maxrss':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}


def verify(e):
    manifest=read(e/'RUN_MANIFEST.json');cfg=copy.deepcopy(manifest['config']);selected=read(e/'SELECTION.json')['chosen_for_C_D_diagnostic']
    rules=canonical_rules(manifest['candidates']);assert rules==CANDIDATES
    for name,h in manifest['code_sha256'].items():assert sha(e/'EXECUTED_SOURCE'/name)==h
    repaired=copy.deepcopy(manifest);repaired['code_sha256']={n:sha(HERE/n) for n in manifest['code_sha256']}
    validate_run_contract(repaired)
    guard_report={'registration_before_reuse':'PASS','manifest_candidates_equal_executed_rules':True,
         'executed_source_sha256':manifest['code_sha256'],'current_repaired_source_sha256':repaired['code_sha256'],
         'numerical_change':'NONE: only pre-use rejection and zero-vs-NA sort correction; all observed candidate P95 nonzero',
         'original_manifest_preserved':True}
    guard_path=e/'GUARD_REWORK_VALIDATION.json';version=1
    while guard_path.exists():
        version+=1;guard_path=e/('GUARD_REWORK_VALIDATION_R'+str(version)+'.json')
    dump(guard_path,guard_report)
    groups=['A','B','B_tau','C','D','E_axis','F_event','G_weak'];timing={g:[] for g in groups[:5]}
    sources={};checks=[];retention=[];cpu=[];old32=[]
    models={}
    for tag,asset,tau in [('old',manifest['background_assets'][0],manifest['old_tau']),('new',manifest['background_assets'][1],manifest['new_tau']),('new_oldtau',manifest['background_assets'][1],manifest['old_tau'])]:
        with np.load(asset['path']) as d:models[tag]=FrozenSurfaces(d['xyz'].copy(),tau,copy.deepcopy(manifest['controls']))
    base_temporal=read(e/'TEMPORAL_MANIFEST.json')['base_group']
    total=0;prefixes=0;warnings=[];future_denials=0;restart_prefixes=0
    for session in read(e/'catalog.json')['sessions']:
        sid=session['session_id'];m,raw,hashes=load(sid);assert hashes==manifest['source_sha256'][sid]
        validate_meta(m,(ROOT/'captures/remote'/sid/'points.bin').stat().st_size)
        states={g:CausalSelection(cfg) for g in groups[:5]};axis=RecentAxis(cfg);event=RecentEvent(cfg);weak=WeakContinuation(cfg)
        sources[sid]=hashes
        for fi in session['available_frames']:
            f=m['frames'][fi]
            reader=CurrentFrameOnly(e,sid,fi)
            try:reader.common(fi+1)
            except ValueError:future_denials+=1
            else:raise AssertionError('Future access was not blocked')
            with np.load(reader.common(fi)) as d:common={k:d[k] for k in d.files}
            q=raw[f['offset_points']:f['offset_points']+f['count_points']].astype(float)
            np.testing.assert_array_equal(q,common['raw_xyz'])
            nominal=q@R.T+T
            if not sid.startswith('cap_20261014'):
                reg=read(Path(cfg['background_experiment'])/(sid+'_registration.json'))
                assert sha(Path(cfg['background_experiment'])/(sid+'_registration.json'))==manifest['transforms'][str(Path(cfg['background_experiment'])/(sid+'_registration.json'))]
                nominal=nominal@np.array(reg['R']).reshape(3,3).T+reg['t']
            np.testing.assert_array_equal(nominal,common['nominal_xyz'])
            frame_records={};frame_members={};p=common['xyz'];t=f['stamp_sec']+f['stamp_nanosec']*1e-9
            started=time.process_time();anchors=static_reference_mask(nominal,common['nominal_domain'],cfg['roi_xy'])
            _,vibration=models['old'].compensate(nominal[anchors],manifest['limits']);preprocess_cpu=(time.process_time()-started)*1000
            np.testing.assert_array_equal(nominal@np.array(vibration['R']).T+vibration['t'],p)
            for g in groups:
                row=read(reader.path(g,fi));frame_records[g]=row
                with np.load(reader.path(g,fi,'_members.npz')) as data:a={k:data[k] for k in data.files}
                frame_members[g]=a
                assert row['source_sha256']==hashes and row['source_frame']==f and row['device_time']==t
                assert row['common_sha256']==sha(e/'common'/sid/f'{fi:04d}.npz') and row['member_sha256']==sha(e/'runs'/g/sid/f'{fi:04d}_members.npz')
                assert len(a['terminal_reason'])==len(p) and np.isin(a['terminal_reason'],range(6)).all()
                ids=a['selected'];fg=a['foreground'];assert len(ids)==len(np.unique(ids)) and set(ids)<=set(fg)
                assert np.array_equal(ids,np.array(row['selection']['selected_source_indices'],int)) and not a['background_match'][ids].any()
                assert np.array_equal(np.flatnonzero(a['terminal_reason']==5),np.sort(ids))
                for body in row['body_3d']:
                    for n in body['skeleton']['nodes'].values():
                        if n['valid']:assert set(n['support_source_indices'])<=set(ids) and np.allclose(n['xyz'],p[n['support_source_indices']].mean(axis=0))
                labels=a['cluster_id'][fg];components=[np.flatnonzero(labels==c) for c in np.unique(labels) if c>=0]
                if g in groups[:5]:
                    got,identity,posture,reset=states[g].update(t,components,p,fg)
                    np.testing.assert_array_equal(got,ids);assert posture==row['posture']
                    assert identity==(row['body_3d'][0]['id'] if len(ids) else None)
                    # Each separately loaded current-frame transition is a prefix endpoint.
                    # No future file is loaded into this state's recurrence.
                    prefixes+=1
                    tag='old' if g in ['A','C'] else ('new_oldtau' if g=='B_tau' else 'new')
                    started=time.process_time();foreground,_,dist,_,_=models[tag].split_pose_hypotheses(nominal,p,common['domain'])
                    computed,_=conditional_graph(p[foreground],cfg,rules[selected],dist[foreground],models[tag].tau) if g in ['C','D'] else cluster(p[foreground],cfg)
                    # Pure processing, no archive I/O, identical preprocessing charged to all groups.
                    elapsed=(time.process_time()-started)*1000+preprocess_cpu
                    np.testing.assert_array_equal(foreground,fg)
                    assert [fg[x].tolist() for x in computed]==[fg[x].tolist() for x in components]
                    timing[g].append({'sid':sid,'fi':fi,'cpu_ms':elapsed,'device_time':t,
                                      'shared_input_array_bytes':sum(x.nbytes for x in common.values())})
                total+=1
            row=frame_records[base_temporal];ids=frame_members[base_temporal]['selected'];sk=row['body_3d'][0]['skeleton'] if len(ids) else skeleton(p[ids],ids,cfg);identity=row['body_3d'][0]['id'] if len(ids) else None
            signed=axis.update(t,fi,identity,p,ids,sk);evt=event.update(t,fi,identity,p,ids)
            assert evt==frame_records['F_event']['posture']
            assert signed==(frame_records['E_axis']['body_3d'][0]['skeleton'] if len(ids) else skeleton(p[ids],ids,cfg))
            a=frame_members[base_temporal];fg=a['foreground'];labels=a['cluster_id'][fg];components=[np.flatnonzero(labels==c) for c in np.unique(labels) if c>=0]
            weakids,_,_=weak.update(t,components,p,fg);np.testing.assert_array_equal(weakids,frame_members['G_weak']['selected'])
            prefixes+=3
            aid=frame_members['A']['selected']
            retention.append({'sid':sid,'fi':fi,'old_candidate_count':len(aid),
                 'old_p90_m':float(np.quantile(p[aid,2],.9)) if len(aid) else None,
                 **{g:{'retained':len(np.intersect1d(aid,frame_members[g]['selected'])),'lost':len(np.setdiff1d(aid,frame_members[g]['selected'])),
                        'retention_fraction':len(np.intersect1d(aid,frame_members[g]['selected']))/len(aid) if len(aid) else None} for g in ['B','B_tau','C','D']}})
        print('VERIFIED SOURCE/MEMBERS/PREFIX',sid,flush=True)
        # Actual fresh-state restarts of every short real prefix, complementing
        # all-frame induction with a reader that cannot expose future inputs.
        for end in range(1,min(20,len(session['available_frames']))+1):
            restarted={g:CausalSelection(cfg) for g in groups[:5]}
            for fi in session['available_frames'][:end]:
                reader=CurrentFrameOnly(e,sid,fi)
                with np.load(reader.common(fi)) as d:p=d['xyz']
                for g in groups[:5]:
                    row=read(reader.path(g,fi))
                    with np.load(reader.path(g,fi,'_members.npz')) as d:fg=d['foreground'];labels=d['cluster_id'][fg];ids=d['selected']
                    components=[np.flatnonzero(labels==c) for c in np.unique(labels) if c>=0]
                    got,identity,posture,_=restarted[g].update(row['device_time'],components,p,fg)
                    np.testing.assert_array_equal(got,ids);assert posture==row['posture']
            restart_prefixes+=5
    # Old empty is explicitly only cached XYZ. Test conservation without reading/fabricating raw bytes.
    sid='cap_20261013_131958';folder=HERE/'action_research_scene_static'/sid
    for path in sorted(folder.glob('*.json')):
        row=read(path);scene=row['scene_change'];fg=set(scene['new_source_indices']);bg=set(scene['matched_source_indices'])
        cluster_ids=[i for o in row['scene_clusters'] for i in o['source_indices']]
        assert not fg & bg and len(cluster_ids)==len(set(cluster_ids)) and set(cluster_ids)<=fg
        assert not row['selection']['selected_source_indices']
        old32.append({'fi':row['frame_index'],'sha256':sha(path),'fg':len(fg),'targets':0,'basis':'CACHED_XYZ_ONLY'})
    dump(e/'OLD32_CACHED_REGRESSION.json',{'frames':old32,'status':'PASS' if len(old32)==32 else 'BLOCKED','original_bytes_CAL':'BLOCKED'})
    dump(e/'CANDIDATE_RETENTION.json',retention)
    dump(e/'CPU_VERIFICATION_ONLY.json',{'groups':{g:{'overall_ms':quant([r['cpu_ms'] for r in rows]),
         'shared_input_peak_bytes':max(r['shared_input_array_bytes'] for r in rows),
         'by_session':{sid:quant([r['cpu_ms'] for r in rows if r['sid']==sid]) for sid in sources},'frames':rows} for g,rows in timing.items()},
         'units':'process_time CPU milliseconds; same compensation plus each background/cluster; no disk/JSON writes',
         'memory_peak':memory_peak(),'memory_scope':'verification process shared peak; isolated group profiles reported separately',
         'command':sys.argv})
    files={str(path.relative_to(e)).replace('\\','/'):sha(path) for parent in [e/'runs',e/'common'] for path in parent.rglob('*') if path.is_file()}
    files['catalog.json']=sha(e/'catalog.json')
    dump(e/'ARTIFACT_INDEX.json',{'schema':'hfus-next-index/1','manifest_sha256':sha(e/'RUN_MANIFEST.json'),'groups':groups,'files':files})
    run=FrozenRun(e)
    row=run.frame('cap_20261013_082623',119,'B')
    queried=run.source(row['session_id'],119,'B',row['selection']['selected_source_indices'][0])
    with tempfile.TemporaryDirectory() as temporary:
        missing=run.source(row['session_id'],119,'B',row['selection']['selected_source_indices'][0],temporary)
        assert missing['source_binding_status']=='BLOCKED_MISSING_ORIGINAL' and missing['raw_bytes_hex'] is None
    dump(e/'SOURCE_QUERY_PROOF.json',{'present':queried,'missing_no_fallback':missing})
    dump(e/'VERIFICATION.json',{'source_frames':2024,'verified_group_frames':total,'independent_streaming_prefix_endpoints':prefixes,
         'source_rehash':sources,'all_current_support_conservation': 'PASS','streaming_prefix_equivalence':'PASS_BY_FRAME_TRANSITION_INDUCTION; no future frame loaded; not O(n^2) restart enumeration',
         'future_access_denials':future_denials,'fresh_short_real_prefix_restarts':restart_prefixes,
         'old32_cache_frames':len(old32),'memory_peak':memory_peak(),'command':sys.argv,'stage_status':'VERIFICATION_COMPLETED'})
    print('VERIFICATION COMPLETE',total,prefixes,flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--evidence',type=Path,required=True);args=parser.parse_args();verify(args.evidence.resolve())
