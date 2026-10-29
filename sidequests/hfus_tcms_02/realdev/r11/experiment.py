"""Fixed empty reference and complete per-frame regional ablations."""
import json
import sys
import time
from collections import Counter
import numpy as np
from scipy.spatial import cKDTree
from common import ROOT, EV, HERE, W, SK, module, save, read, jsonlines, sha
from calibrate import CalibrationLayer

JITTER=ROOT/'docs/human_fall/evidence/2026-10-18_hfus_pose_jitter_01_r1'
D=module('s07_legacy_statistics',JITTER/'diagnose.py')
PROTOCOL=read(EV/'PROTOCOL_V1.json')
BOUNDS=np.asarray(PROTOCOL['roi'])
WINDOWS=PROTOCOL['windows']

def foreground_mask(tree, points):
    distance=tree.query(points)[0]
    return distance>.06, distance

def source():
    C=module('s07_source',W.R01/'contracts.py')
    path=ROOT/'data/sessions/cap_20261018_110029'
    binding={k:sha(path/n) for k,n in [('meta','meta.json'),('points','points.bin')]}
    frozen=read(EV/'INPUTS.json')[path.name]
    assert all(binding[k]==frozen[n]['sha256'] for k,n in [('meta','meta.json'),('points','points.bin')])
    src=C.Source(dict(kind='REAL_DEVELOPMENT',role='B',independent_test=False,path=str(path),sid=path.name,coordinate_version='RAW/innolidar',source_sha256=binding))
    return src

def roi(f):
    p=f['xyz'];mask=np.isfinite(p).all(1)&np.any(p!=0,axis=1)&np.all(p>=BOUNDS[:,0],1)&np.all(p<=BOUNDS[:,1],1)
    rows=np.flatnonzero(mask)
    return p[rows],rows+f['offset']

def ledger():
    start=time.perf_counter();src=source();clouds=[];rows=[];ptr=[0]
    try:
        # Only preceding empty frames; calibration window [50,100) untouched.
        for fi in range(50):clouds.append(roi(src.frame(fi))[0])
        reference=np.concatenate(clouds);tree=cKDTree(reference)
        kept=[];distance=[];counts=[]
        for fi in range(386):
            p,r=roi(src.frame(fi))
            if fi<50:keep,dist=np.zeros(len(p),bool),np.full(len(p),np.nan)
            else:keep,dist=foreground_mask(tree,p)
            rows.append(r);ptr.append(ptr[-1]+len(r));kept.append(keep);distance.append(dist)
            counts.append(dict(fi=fi,roi_rows=len(p),foreground_rows=int(keep.sum()),background_rows=int((~keep).sum()),phase='MAP_BUILDING' if fi<50 else 'FROZEN_REFERENCE',reference_max_frame=49 if fi>=50 else None))
        with (EV/'FOREGROUND_LEDGER.npz').open('xb') as f:np.savez_compressed(f,global_rows=np.concatenate(rows),indptr=np.asarray(ptr),keep=np.concatenate(kept),nearest_distance_m=np.concatenate(distance))
        save('FOREGROUND_COUNTS.json',dict(frames=counts,fit_frames=[0,50],background_reference_points=len(reference),reference_sha=__import__('hashlib').sha256(reference.tobytes()).hexdigest(),purity='UNKNOWN',recall='UNKNOWN',seconds=time.perf_counter()-start))
    finally:src.close()

def distribution(values):
    return None if not values else dict(n=len(values),min=min(values),p50=float(np.quantile(values,.5)),p95=float(np.quantile(values,.95)),p99=float(np.quantile(values,.99)),max=max(values))

def summarize(records):
    result={}
    for name,(lo,hi) in WINDOWS.items():
        rs=records[lo:hi];candidate=sum(r['candidate_rows']>=30 for r in rs)
        nodes={}
        for k in SK.SLOTS:
            raw=D.vector_stats(rs,k);rel=D.vector_stats(rs,k,'CHEST')
            steps=[float(np.linalg.norm(np.asarray(b['nodes'][k]['xyz'])-a['nodes'][k]['xyz']))*1000 for a,b in zip(rs,rs[1:]) if b['fi']==a['fi']+1 and a['nodes'][k]['valid'] and b['nodes'][k]['valid']]
            raw['step_distribution_mm']=distribution(steps)
            paired=[r for r in rs if r['nodes'][k]['valid'] and r['nodes']['CHEST']['valid']]
            relative_steps=[float(np.linalg.norm((np.asarray(b['nodes'][k]['xyz'])-b['nodes']['CHEST']['xyz'])-(np.asarray(a['nodes'][k]['xyz'])-a['nodes']['CHEST']['xyz']))*1000) for a,b in zip(paired,paired[1:]) if b['fi']==a['fi']+1]
            rel['step_distribution_mm']=distribution(relative_steps)
            raw.update(missing_frames=len(rs)-raw['valid_frames'],candidate_frames=candidate,valid_per_candidate=None if not candidate else raw['valid_frames']/candidate)
            nodes[k]=dict(raw=raw,relative_chest=rel,reasons=dict(Counter(r['nodes'][k]['reason'] for r in rs)))
        edges={}
        for a,b in SK.EDGES:
            key=a+'|'+b
            es=[r['calibration']['edges'][key] for r in rs]
            edges[key]=dict(measured_frames=sum(e['measurement'] is not None for e in es),current_measured_calibrated_frames=sum(e['measurement'] is not None and e['state']=='CALIBRATED' for e in es),states=dict(Counter(e['state'] for e in es)),drift_reset_count=sum(e.get('drift') is not None for e in es),measurement_distribution_m=distribution([e['measurement'] for e in es if e['measurement'] is not None]))
        result[name]=dict(frames=len(rs),candidate_frames=candidate,six_frames=sum(r['valid_nodes']>=6 for r in rs),six_per_all=sum(r['valid_nodes']>=6 for r in rs)/len(rs),six_per_candidate=None if not candidate else sum(r['valid_nodes']>=6 for r in rs)/candidate,total_valid_nodes=sum(r['valid_nodes'] for r in rs),candidate_point_distribution=distribution([r['candidate_rows'] for r in rs]),nodes=nodes,edges=edges)
    return result

def run(group):
    start=time.perf_counter();src=source()
    foreground=group.startswith('fg');new=group.endswith('new')
    if new:
        assert (EV/'REGION_PROTOCOL_V1.json').exists()
        from regions import estimate
    else:estimate=SK.estimate
    cal=CalibrationLayer(SK.EDGES);records=[]
    with np.load(EV/'FOREGROUND_LEDGER.npz',allow_pickle=False) as z:
        ledger={k:z[k] for k in z.files}
    verify=dict(frames=0,nodes=0,max_recompute_error_m=0.,partition=True)
    try:
        for fi in range(386):
            f=src.frame(fi);p,rows=roi(f);sl=slice(ledger['indptr'][fi],ledger['indptr'][fi+1])
            assert np.array_equal(rows,ledger['global_rows'][sl])
            mask=ledger['keep'][sl] if foreground else np.ones(len(p),bool)
            p=p[mask];rows=rows[mask]
            sk,_=(estimate(p,rows.tolist(),coordinate_version='RAW/innolidar',session_id='cap_20261018_110029') if new else estimate(p,rows.tolist()))
            measurements=W.skeleton_measurements(sk,SK.EDGES)
            cf=cal.update(fi,measurements)
            # Every valid node must remain reproducible from current source rows.
            byrow={int(r):i for i,r in enumerate(rows)}
            for key,n in sk['nodes'].items():
                if not n['valid']:continue
                assert all(r in byrow for r in n['support_rows'])
                ids=[byrow[r] for r in n['support_rows']]
                if new:expected=np.median(p[ids],axis=0)
                else:
                    axis=np.asarray(sk['axis']);lat=np.asarray(sk['basis_lateral']);basis=np.column_stack([lat,np.cross(lat,axis),axis]);center=np.mean(p,axis=0)
                    expected=np.median((p[ids]-center)@basis,axis=0)@basis.T+center
                err=float(np.max(np.abs(expected-n['xyz'])))
                assert err<1e-10
                verify['nodes']+=1;verify['max_recompute_error_m']=max(verify['max_recompute_error_m'],err)
            verify['frames']+=1
            records.append(dict(fi=fi,t=src.times[fi],candidate_rows=len(p),valid_nodes=W.valid_nodes(sk),nodes=sk['nodes'],reason=sk['reason'],axis=sk.get('axis'),basis_lateral=sk.get('basis_lateral'),diagnostics=sk.get('diagnostics'),calibration=cf))
    finally:src.close()
    save(group.upper()+'_FRAMES.jsonl',''.join(json.dumps(r,separators=(',',':'),allow_nan=False)+'\n' for r in records))
    summary=summarize(records)
    save(group.upper()+'_SUMMARY.json',summary)
    save(group.upper()+'_CALIBRATION.json',cal.summary())
    save(group.upper()+'_VERIFY.json',dict(**verify,seconds=time.perf_counter()-start,source_sha=sha(HERE/'experiment.py'),extractor_sha=sha(HERE/'regions.py') if new else sha(W.R04S/'skeleton.py')))
    hold=summary['hold'];print(group,'six',hold['six_frames'],'chest',hold['nodes']['CHEST']['raw']['valid_frames'],'outer',hold['nodes']['OUTER_A']['raw'],flush=True)

if __name__=='__main__':
    if sys.argv[1]=='ledger':ledger()
    else:run(sys.argv[1])
