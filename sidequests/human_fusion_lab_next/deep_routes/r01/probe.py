"""Source-preserving route pilots. No training, no new weights, no default change."""
import argparse
import copy
import hashlib
import json
import platform
import sys
import time
from pathlib import Path
import numpy as np
from scipy.spatial import cKDTree
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
from sklearn.cluster import HDBSCAN
import sklearn
import torch
from torch import nn

ROOT = Path(__file__).resolve().parents[4]
OLD_SOURCE = ROOT/'sidequests/human_fusion_lab_next/pointset/r01'
sys.path.insert(0,str(OLD_SOURCE))
from core import voxelize, cluster, skeleton
from next_dev import CausalSelection, node_metrics, load
from next_contract import FrozenRun, read, sha

def write(path, obj):
    with Path(path).open('x',encoding='utf-8') as stream:
        json.dump(obj,stream,ensure_ascii=False,allow_nan=False,indent=2)

class Shadow(nn.Module):
    def __init__(self):
        super().__init__()
        self.point=nn.Sequential(nn.Conv1d(3,32,1),nn.ReLU(),nn.Conv1d(32,64,1),nn.ReLU(),nn.Conv1d(64,128,1),nn.ReLU())
        self.head=nn.Sequential(nn.Linear(128,64),nn.ReLU(),nn.Linear(64,1))
    def forward(self,x):return self.head(self.point(x).amax(dim=2)).squeeze(1)

def pixels(raw,h,w,kind):
    distance=np.linalg.norm(raw,axis=1)
    finite=np.isfinite(raw).all(axis=1)&(distance>0)
    if kind=='pinhole':
        good=finite&(raw[:,0]>0)
        denominator=np.where(good,raw[:,0],1)
        u=.5+raw[:,1]/(2*np.tan(np.deg2rad(60))*denominator)
        v=.5-raw[:,2]/(2*np.tan(np.deg2rad(45))*denominator)
    else:
        yaw=np.arctan2(raw[:,1],raw[:,0]);pitch=np.arctan2(raw[:,2],np.hypot(raw[:,0],raw[:,1]))
        extent=(np.pi,np.pi/2) if kind=='sphere' else (np.deg2rad(60),np.deg2rad(40))
        u=.5+yaw/(2*extent[0]);v=.5-pitch/(2*extent[1]);good=finite
    good &= np.isfinite(u)&np.isfinite(v)&(u>=0)&(u<1)&(v>=0)&(v<1)
    ids=np.flatnonzero(good)
    flat=np.floor(v[ids]*h).astype(int)*w+np.floor(u[ids]*w).astype(int)
    # CSR contains every in-view source member, not just the z-buffer winner.
    order=np.lexsort((ids,distance[ids],flat));members=ids[order];sorted_pixels=flat[order]
    occupied,starts,counts=np.unique(sorted_pixels,return_index=True,return_counts=True)
    offsets=np.r_[starts,len(members)]
    nearest=members[starts]
    spread=np.maximum.reduceat(distance[members],starts)-np.minimum.reduceat(distance[members],starts) if len(starts) else np.empty(0)
    return {'pixels':occupied,'offsets':offsets,'members':members,'nearest':nearest,'counts':counts,'spread':spread,'outside':np.flatnonzero(~good)}

def projection_stats(raw,projection,h,w):
    n=len(raw);covered=len(projection['members']);k=len(projection['nearest'])
    return {'input_points':n,'in_view':covered,'outside':n-covered,'occupied':k,'empty_pixel_fraction':1-k/(h*w),
            'nearest_only_loss_fraction':None if not covered else 1-k/covered,
            'multi_depth_pixels':int(np.count_nonzero(projection['spread']>.17)),
            'max_depth_spread_m':float(projection['spread'].max()) if k else None}

def graph_groups(n,edges):
    if not n:return np.empty(0,dtype=int)
    edges=np.asarray(edges,dtype=int).reshape(-1,2)
    rows=np.r_[edges[:,0],edges[:,1]];cols=np.r_[edges[:,1],edges[:,0]]
    return connected_components(coo_matrix((np.ones(len(rows)),(rows,cols)),shape=(n,n)).tocsr(),directed=False)[1]

def point_groups(labels,inverse,cfg):
    return [ids for label in np.unique(labels) if label>=0
            for ids in [np.flatnonzero(labels[inverse]==label)] if len(ids)>=cfg['cluster_min_points']]

def routes(points,raw,cfg,net):
    groups,_=cluster(points,cfg)
    yield 'dbscan',groups,{'role':'same-window reset control'}
    if not len(points):
        for name in ['hdbscan','learned_edge','range_cc']:yield name,[],{'empty':True}
        return
    _,centers,inverse,_=voxelize(points,cfg['voxel_m'])
    labels=HDBSCAN(min_cluster_size=4,min_samples=4,allow_single_cluster=True,n_jobs=1,copy=True).fit_predict(centers) if len(centers)>=4 else np.full(len(centers),-1)
    yield 'hdbscan',point_groups(labels,inverse,cfg),{'nodes':len(centers),'noise_nodes':int((labels<0).sum())}
    edges=cKDTree(centers).query_pairs(.17,output_type='ndarray')
    centered=(centers-centers.mean(axis=0)).astype(np.float32)
    with torch.inference_mode():features=net.point(torch.from_numpy(centered.T[None].copy())).squeeze(0).T.numpy()
    norm=np.linalg.norm(features,axis=1,keepdims=True);features=features/np.maximum(norm,1e-8)
    cos=(features[edges[:,0]]*features[edges[:,1]]).sum(axis=1) if len(edges) else np.empty(0)
    kept=edges[cos>=.99]
    labels=graph_groups(len(centers),kept)
    yield 'learned_edge',point_groups(labels,inverse,cfg),{'nodes':len(centers),'candidate_edges':len(edges),'kept_edges':len(kept),
            'feature_role':'candidate-classifier frozen features, NOT metric-learned/semantic embeddings; full-FG centering is domain shift'}
    pr=pixels(raw,256,1024,'sphere');valid=pr['spread']<=.17
    eligible=pr['pixels'][valid];representatives=pr['nearest'][valid];lookup={int(v):i for i,v in enumerate(eligible)}
    edges=[]
    for i,pixel in enumerate(eligible):
        y,x=divmod(int(pixel),1024)
        for dy,dx in [(0,1),(1,-1),(1,0),(1,1)]:
            yy,xx=y+dy,x+dx
            if not 0<=xx<1024 or not 0<=yy<256:continue
            j=lookup.get(yy*1024+xx)
            if j is not None and np.linalg.norm(points[representatives[i]]-points[representatives[j]])<=.17:edges.append((i,j))
    labels=graph_groups(len(eligible),edges);all_labels=np.full(len(points),-1,dtype=int)
    for i,slot in enumerate(np.flatnonzero(valid)):
        all_labels[pr['members'][pr['offsets'][slot]:pr['offsets'][slot+1]]]=labels[i]
    groups=[ids for label in np.unique(all_labels) if label>=0 for ids in [np.flatnonzero(all_labels==label)] if len(ids)>=cfg['cluster_min_points']]
    yield 'range_cc',groups,{'ambiguous_pixel_points_UNKNOWN':int(sum(pr['counts'][~valid])),'nodes':len(eligible),'edges':len(edges)}

def checks():
    # Same ray/different depths must remain in CSR; nearest-only hides one.
    points=np.array([[1.,0,0],[2.,0,0],[0.,0,0],[np.nan,0,0]])
    q=pixels(points,64,256,'sphere')
    assert q['members'].tolist()==[0,1] and q['nearest'].tolist()==[0] and q['spread'].tolist()==[1.]
    assert q['outside'].tolist()==[2,3]
    labels=graph_groups(4,[[0,1],[1,2]])
    assert labels[0]==labels[2] and labels[0]!=labels[3]
    print('Source/collision/disconnected graph checks PASS',flush=True)

def run(e):
    if not __debug__:raise RuntimeError('Assertions required')
    m=read(e/'RUN_MANIFEST.json');old=Path(m['old_evidence']);out=e/'pilot';out.mkdir(exist_ok=False)
    frozen=FrozenRun(old);cfg=copy.deepcopy(frozen.manifest['config'])
    for relative,digest in m['source_before_sha256'].items():assert sha(ROOT/relative)==digest
    model=ROOT/'sidequests/human_fusion_lab/models/pointnet_shadow.pt'
    torch.set_num_threads(1);net=Shadow();net.load_state_dict(torch.load(model,map_location='cpu',weights_only=True),strict=True);net.eval()
    import onnxruntime as ort
    options=ort.SessionOptions();options.intra_op_num_threads=1;options.inter_op_num_threads=1
    inference=ort.InferenceSession(str(model.with_suffix('.onnx')),sess_options=options,providers=['CPUExecutionProvider'])
    rows=[];projected=[];sources=[];parity=[]
    for sid,frames in m['samples'].items():
        metadata,raw,hashes=load(sid);assert hashes==frozen.manifest['source_sha256'][sid]
        sources.append({'sid':sid,'sha256':hashes,'frames':len(metadata['frames'])})
        states={name:CausalSelection(cfg) for name in m['candidates']};previous={}
        folder=out/sid;folder.mkdir()
        for fi in frames:
            base=read(frozen.verified(old/'runs/B'/sid/f'{fi:04d}.json'))
            common=old/'common'/sid/f'{fi:04d}.npz';assert sha(common)==base['common_sha256']
            with np.load(common) as archive:
                p=archive['xyz'].copy();raw_p=archive['raw_xyz'].copy();valid=archive['valid'].copy()
            frame=metadata['frames'][fi];start=frame['offset_points'];original=np.asarray(raw[start:start+frame['count_points']])
            np.testing.assert_array_equal(original,raw_p)
            with np.load(frozen.verified(old/'runs/B'/sid/f'{fi:04d}_members.npz')) as archive:fg=archive['foreground'].astype(int)
            ledger={'source_sha256':hashes,'fi':fi,'device_time':base['device_time'],'source_frame':frame,'base_member_sha256':base['member_sha256'],
                    'common_sha256':base['common_sha256'],'identity':'UNKNOWN','routes':{}}
            for kind in ['sphere','angular_crop','pinhole']:
                for h,w in m['projection_resolutions']:
                    valid_rows=np.flatnonzero(valid);pr=pixels(raw_p[valid_rows],h,w,kind)
                    projected.append({'sid':sid,'fi':fi,'kind':kind,'h':h,'w':w,**projection_stats(raw_p[valid_rows],pr,h,w)})
                    # Only the highest-resolution CSR is stored, all metrics retained.
                    if (h,w)==(256,1024):
                        assert len(np.unique(pr['members']))==len(pr['members'])
                        assert len(pr['members'])+len(pr['outside'])==len(valid_rows)
                        np.savez_compressed(folder/f'{fi:04d}_{kind}_projection.npz',pixels=pr['pixels'],offsets=pr['offsets'],
                            source_members=valid_rows[pr['members']],nearest_source_rows=valid_rows[pr['nearest']],outside_source_rows=valid_rows[pr['outside']],depth_spread_m=pr['spread'])
            # The generator is timed per candidate, including candidate construction.
            iterator=routes(p[fg],raw_p[fg],cfg,net)
            for expected in m['candidates']:
                begin=time.perf_counter();name,groups,details=next(iterator);assert name==expected
                indices=np.concatenate(groups) if groups else np.empty(0,int)
                assert len(indices)==len(np.unique(indices)) and np.all((indices>=0)&(indices<len(fg)))
                ids,identity,posture,reset=states[name].update(base['device_time'],groups,p,fg)
                sk=skeleton(p[ids],ids,cfg);metrics=node_metrics(sk,previous.get(name),identity,base['device_time'],cfg)
                previous[name]={'sk':sk,'identity':identity,'t':base['device_time']}
                labels=np.full(len(p),-2,dtype=np.int32);labels[fg]=-1
                for ci,component in enumerate(groups):labels[fg[component]]=ci
                assert np.all(labels[ids]>=0)
                elapsed=(time.perf_counter()-begin)*1000
                model_result=None
                if len(ids):
                    selected=p[ids];sample=selected[np.floor(np.arange(256)*len(selected)/256).astype(int)].astype(np.float32)
                    sample-=sample.mean(axis=0,keepdims=True);tensor=sample.T[None].copy()
                    with torch.inference_mode():logit=float(net(torch.from_numpy(tensor)).item())
                    onnx_logit=float(inference.run(None,{'points':tensor})[0].reshape(-1)[0]);assert np.isclose(logit,onnx_logit,rtol=1e-4,atol=1e-4)
                    model_result={'logit':logit,'probability_uncalibrated':float(torch.sigmoid(torch.tensor(logit)).item()),'identity':'UNKNOWN_NOT_GT','feature_contract':'source-order 256 samples; mean center; no scale normalize'}
                    parity.append(abs(logit-onnx_logit))
                np.savez_compressed(folder/f'{fi:04d}_{name}_members.npz',foreground=fg,selected=ids,cluster_labels=labels)
                current={'selected_count':len(ids),'clusters':len(groups),'unassigned_foreground':int((labels[fg]<0).sum()),'ms':elapsed,
                         'axis_missing':metrics['axis_missing'],'slot_jump_m':metrics['slot_jump_m'],'axis_angle_rad':metrics['unoriented_axis_angle_rad'],
                         'valid_slots':metrics['valid_nodes'],'reset':reset,'details':details,'model':model_result}
                ledger['routes'][name]=current;rows.append({'sid':sid,'fi':fi,'route':name,'device_time':base['device_time'],**current})
            write(folder/f'{fi:04d}.json',ledger)
        del raw
        print(sid,len(frames),'pilot frames complete',flush=True)
    write(e/'PILOT_ROWS.json',rows);write(e/'PROJECTION_ROWS.json',projected)
    write(e/'PREFLIGHT.json',{'sources':sources,'original_frames':sum(x['frames'] for x in sources),'original_18_sha_rechecked':True,
                            'pilot_frames':sum(map(len,m['samples'].values())),'onnx_torch_comparisons':len(parity),'max_logit_error':max(parity,default=None),
                            'python':platform.python_version(),'numpy':np.__version__,'sklearn':sklearn.__version__,'torch':torch.__version__,
                            'cuda':False,'source_sha256':sha(Path(__file__)),'manifest_sha256':sha(e/'RUN_MANIFEST.json')})
    for relative,digest in m['source_before_sha256'].items():assert sha(ROOT/relative)==digest
    print('Pilot complete; previous source and weights unchanged',flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--evidence',type=Path);parser.add_argument('--check',action='store_true');a=parser.parse_args()
    if a.check:checks()
    elif a.evidence:run(a.evidence.resolve())
    else:parser.error('Use --check or --evidence')
