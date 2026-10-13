"""Frozen 121647 clean-cell reconstruction; no new TLS estimation or export."""
import importlib.util,mmap,sys,time
import numpy as np
from prepare import E,I,save,load,sha
sys.path[:0]=[str(E/'candidate'),str(E/'frozen')]
import floor_sheet as fixed
from leveling_quality import rotation,statistics
spec=importlib.util.spec_from_file_location('old_sheet',E/'frozen/floor_sheet.py')
old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
base=load(E/'01_baseline.json')
for p,digest in base['input_files'].items():assert sha(p)==digest
job=I/'sidequests/traditional_clustering/artifacts/leveling/389dc570b0cd4eb38dd405244effbe20'
report=load(job/'report.json');cfg=report['config'];directory=I/'audit_inputs/cap_20261009_121647'
meta=load(directory/'meta.json');R=rotation(cfg['pitch_deg'],cfg['roll_deg'])
frames=len(meta['frames']);held={(frames-1)//3,2*(frames-1)//3,frames-1}
pts,ids=[],[]
with (directory/'points.bin').open('rb') as stream:
    with mmap.mmap(stream.fileno(),0,access=mmap.ACCESS_READ) as raw:
        xyz=np.ndarray((meta['total_points'],3),dtype='<f4',buffer=raw,strides=(28,4))
        target=None
        for o,f in enumerate(meta['frames']):
            q=xyz[f['offset_points']:f['offset_points']+f['count_points']].astype('f8')
            q=q[np.isfinite(q).all(axis=1)&np.any(q!=0,axis=1)]
            if o==72:target=q.copy()
            if o in held:continue
            inside=(np.abs(q)<=100).all(axis=1);q=q[inside]
            pts.append(q);ids.append(np.full(len(q),o,dtype='i4'))
        del xyz
work=np.concatenate(pts);frame_ids=np.concatenate(ids);del pts,ids
plane=dict(normal=cfg['auto_candidate']['normal_source'],offset_m=cfg['auto_candidate']['offset_source_m'])
started=time.perf_counter();cells=old._clean_cells(work,frame_ids,R,plane)
legacy=old._roi_metrics(cells);candidate=fixed._roi_metrics(cells)
assert legacy['ok'] and legacy==candidate and len(cells)==cfg['auto_candidate']['roi']['clean_cells']
bounds=[[int(x)*.25,(int(x)+1)*.25,int(y)*.25,(int(y)+1)*.25] for x,y in sorted(legacy['selected'])]
assert bounds==cfg['regions']
xy=target@R.T;xl,xh,yl,yh=cfg['regions'][1]
z=(xy[:,0]>=xl)&(xy[:,0]<xh)&(xy[:,1]>=yl)&(xy[:,1]<yh)
stat=statistics(target[z],np.array(report['estimators']['tls']['normal_source']),report['estimators']['tls']['offset_source_m'])
assert abs(stat['p95_m']-.05029186936019117)<1e-12 and stat['status']=='FAIL'
assert not report['estimators']['tls']['valid']
save('03_session121647.json',dict(clean_cell_count=len(cells),clean_keys=[c['key'] for c in cells],
    original_selector=legacy,candidate_selector=candidate,ROI_unchanged=True,original_holdouts=sorted(held),
    source_points_for_clean_cells=len(work),fixed_original_plane=plane,ROI2_ordinal72=stat,
    effective_TLS='BLOCKED',new_TLS_estimation=False,new_export=False,elapsed_sec=time.perf_counter()-started))
print('SESSION121647_ORIGINAL_ROI_AND_TLS_BLOCKED_PRESERVED',len(cells),stat['p95_m'])
