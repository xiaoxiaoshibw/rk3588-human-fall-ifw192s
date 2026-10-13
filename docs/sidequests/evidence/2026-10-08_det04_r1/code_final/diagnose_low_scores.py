"""DET-03 paired causal probes, no training, device access or production changes."""
import argparse
import json
from pathlib import Path
import time

import numpy as np
import torch
from torch import nn
from cpu_pointpillars import load_model, limit_period
from experiment import sha, read_frame, adapt
from audit_truth import covers_xy
from upstream_kernel_check import fixed_nms, legacy_nms as nms_cuda

ROOT = Path(__file__).resolve().parent
EVIDENCE = ROOT.parents[1] / 'docs/sidequests/evidence/2026-10-08_det03_r1'
SEED_FILE = ROOT.parents[1] / 'docs/sidequests/evidence/2026-10-07_det01_r2/user_truth_seeds.json'
FG = ROOT / 'artifacts/det02_foreground_r1'
PRE = ROOT / 'artifacts/det02_prepared_r1'
UP = ROOT / 'artifacts/upstream'


def containing(boxes, xy, clockwise=True):
    dx, dy = xy[0] - boxes[:,0], xy[1] - boxes[:,1]
    c, s = np.cos(boxes[:,6]), np.sin(boxes[:,6])
    if clockwise:s = -s
    return (np.abs(c*dx+s*dy)<=boxes[:,3]/2)&(np.abs(-s*dx+c*dy)<=boxes[:,4]/2)


def cylinder(points, xy):
    return (np.sum((points[:,:2]-xy)**2,axis=1)<=.55**2)&(points[:,2]>=.05)&(points[:,2]<=2.30)


def height_summary(points, xy):
    p = points[cylinder(points,xy)]
    return dict(count=len(p),bands=np.histogram(p[:,2],[.05,.3,.6,.9,1.2,1.5,1.8,2.3])[0].tolist(),
                legs_proxy=int((p[:,2]<.6).sum()),head_proxy=int(((p[:,2]>=1.5)&(p[:,2]<1.8)).sum()),
                raised_hands_proxy=int((p[:,2]>=1.8).sum()),top=float(p[:,2].max()) if len(p) else None,
                scope='Height band in approximate cylinder; furniture included, not body-part GT')


class SamplingProbe(nn.Module):
    def __init__(self, base):
        super().__init__()
        self.base = base
        self.mode = 'first32'
        self.freeze = None
        self.selected = None

    def forward(self, points):
        vox, coords, counts = self.base(points)
        p = points.numpy()
        valid=np.isfinite(p).all(1)&((p[:,:3]>=self.base.bounds[:3])&(p[:,:3]<self.base.bounds[3:])).all(1)
        indices=np.flatnonzero(valid)
        c=np.floor((p[valid,:3]-self.base.bounds[:3])/self.base.size).astype('i4')
        groups={}
        for i,key in zip(indices,map(tuple,c)):groups.setdefault(key,[]).append(i)
        chosen=[];full_counts=[]
        for j,key in enumerate(map(tuple,coords.numpy())):
            ids=np.asarray(groups[key]);full_counts.append(len(ids))
            if self.mode=='z_rank32' and len(ids)>self.base.max_points:
                ordered=ids[np.argsort(p[ids,2],kind='stable')]
                ids=ordered[np.rint(np.linspace(0,len(ids)-1,self.base.max_points)).astype(int)]
            else:ids=ids[:self.base.max_points]
            chosen.extend(ids.tolist())
            if self.mode=='z_rank32':vox[j,:len(ids)]=torch.from_numpy(p[ids])
        if self.freeze:
            for j,key in enumerate(map(tuple,coords.numpy())):
                if key in self.freeze:
                    arr,n=self.freeze[key];vox[j]=arr;counts[j]=n
        self.selected=np.asarray(chosen,dtype='i8')
        self.last=(vox.clone(),coords.clone(),counts.clone(),np.asarray(full_counts))
        return vox,coords,counts


def trace_heads(model, heads, xy, path, save_full):
    cls, reg, direction = [h[0] for h in heads]
    scores=cls.permute(1,2,0).reshape(-1,3).sigmoid()
    deltas=reg.permute(1,2,0).reshape(-1,7)
    dirs=direction.permute(1,2,0).reshape(-1,2).argmax(1)
    anchors=model.anchors_generator.get_multi_anchors(torch.tensor(list(cls.shape[-2:]))).reshape(-1,7)
    decode=model.get_predicted_bboxes_single.__globals__['anchors2bboxes']
    boxes=decode(anchors,deltas)
    boxes[:,6]=limit_period(boxes[:,6],1,np.pi)+(1-dirs)*np.pi
    b=boxes.numpy();s=scores.numpy()
    local=((anchors[:,:2]-torch.tensor(xy))**2).sum(1).numpy()<=.55**2
    hits=containing(b,xy)
    old_hits=containing(b,xy,False)
    top=scores.max(1).values.topk(model.nms_pre).indices
    # Complete rank is recorded for every relevant anchor; ties follow torch topk.
    order=scores.max(1).values.argsort(descending=True)
    rank=torch.empty_like(order);rank[order]=torch.arange(len(order))
    keep_by_nms={}; finals={}; nms_suppressors={}
    raw_boxes=decode(anchors[top],deltas[top])
    bev=torch.cat([raw_boxes[:,:2]-raw_boxes[:,3:5]/2,raw_boxes[:,:2]+raw_boxes[:,3:5]/2,raw_boxes[:,6:]],1)
    for name,op in [('legacy',nms_cuda),('clockwise',fixed_nms)]:
        kept=[];supp=[]
        for label in range(3):
            eligible=torch.where(scores[top,label]>model.score_thr)[0]
            k=op(bev[eligible],scores[top[eligible],label],model.nms_thr)
            selected=eligible[k]
            kept.extend((int(top[i]),label) for i in selected)
            if label==0:
                rejected=[i for i in eligible.tolist() if i not in selected.tolist()]
                for i in rejected:
                    blocker=None
                    for j in selected.tolist():
                        if scores[top[j],0]>=scores[top[i],0] and len(op(bev[[j,i]],scores[top[[j,i]],0],model.nms_thr))==1:
                            blocker=int(top[j]);break
                    supp.append(dict(anchor_id=int(top[i]),suppressed_by=blocker))
        keep_by_nms[name]=kept;nms_suppressors[name]=supp
        if len(kept)>model.max_num:
            v=torch.tensor([s[i,l] for i,l in kept]);idx=v.topk(model.max_num).indices.tolist();finals[name]=[kept[i] for i in idx]
        else:finals[name]=kept
    # Instrumentation must reproduce the unmodified network postprocessor.
    original=model.get_predicted_bboxes_single(cls,reg,direction,anchors)
    actual=[] if not isinstance(original,dict) else list(zip(original['labels'].tolist(),original['scores'].tolist()))
    expected=[(l,float(s[i,l])) for i,l in finals['clockwise']]
    assert actual==expected,(actual,expected)
    if isinstance(original,dict):np.testing.assert_array_equal(original['lidar_bboxes'],b[[i for i,l in finals['clockwise']]])
    top_np=top.numpy()
    relevant=np.flatnonzero(local|hits|(np.arange(len(b))[:,None]==top_np).any(1))
    # Full raw heads for representatives; per-frame full local/candidate evidence otherwise.
    arrays=dict(anchor_ids=relevant,anchors=anchors.numpy()[relevant],raw_cls_scores=s[relevant],
                deltas=deltas.numpy()[relevant],dir_class=dirs.numpy()[relevant],decoded_boxes=b[relevant],
                rank=rank.numpy()[relevant],top100=top_np,global_top_anchor_id=np.argmax(s,axis=0))
    if save_full:arrays.update(cls_logits=cls.numpy(),reg=reg.numpy(),dir_logits=direction.numpy())
    np.savez_compressed(path,**arrays)
    stages={}
    for name in finals:
        final_p=[i for i,l in finals[name] if l==0];nms_p=[i for i,l in keep_by_nms[name] if l==0]
        stages[name]=dict(final_target_max=max([float(s[i,0]) for i in final_p if hits[i]],default=0),
                          final_global_ped_max=max([float(s[i,0]) for i in final_p],default=0),
                          final_global_any_max=max([float(s[i,l]) for i,l in finals[name]],default=0),
                          final_target_count=sum(bool(hits[i]) for i in final_p),
                          target_nms_removed=sum(bool(hits[r['anchor_id']]) for r in nms_suppressors[name]),
                          target_max50_removed=sum(bool(hits[i]) for i in nms_p if i not in final_p),
                          detections=[dict(anchor_id=i,label=l,score=float(s[i,l]),box=b[i].tolist()) for i,l in finals[name]],
                          nms_suppressors=nms_suppressors[name])
    threshold=hits&(s[:,0]>model.score_thr)
    topmask=np.zeros(len(s),bool);topmask[top_np]=True
    return dict(local_anchor_max=float(s[local,0].max()),raw_containing_max=float(s[hits,0].max()) if hits.any() else 0,
                global_raw_ped_max=float(s[:,0].max()),global_raw_any_max=float(s.max()),
                raw_containing_gt01=int(threshold.sum()),target_top100_removed=int((threshold&~topmask).sum()),
                local_top100_count=int(local[top_np].sum()),old_ccw_final_target=max([float(s[i,0]) for i,l in finals['legacy'] if l==0 and old_hits[i]],default=0),
                stages=stages,trace=str(path),trace_sha256=sha(path))


def load_cloud(session, frame, variant, raw_session):
    rec=frame['variants'][variant];p=FG/session['sid']/rec['file'];idsfile=Path(str(p)+'.ids')
    assert sha(p)==rec['sha256'] and sha(idsfile)==rec['ids_sha256']
    pts=np.fromfile(p,dtype='<f4').reshape(-1,4);ids=np.fromfile(idsfile,dtype='<u4')
    rawrec=raw_session['frames'][frame['index']];rawp=PRE/session['sid']/rawrec['file']
    assert sha(rawp)==rawrec['sha256']
    raw=np.fromfile(rawp,dtype='<f4').reshape(-1,4)
    np.testing.assert_array_equal(pts,raw[ids])
    return pts,ids


def run_probe(model, probe, cloud, ids, xy, out, tag, mode='first32',z=-1.73,divisor=1023,zero=False,freeze=None,full=True):
    p=cloud.copy();p[:,2]+=np.float32(z);p[:,3]/=np.float32(divisor)
    if zero:p[:,3]=0
    probe.mode=mode;probe.freeze=freeze
    captured=[]
    hook=model.head.register_forward_hook(lambda m,i,o:captured.extend([t.detach() for t in o]))
    start=time.perf_counter()
    try:
        with torch.inference_mode():model([torch.from_numpy(p)],mode='test')
    finally:hook.remove()
    with torch.inference_mode():row=trace_heads(model,captured,xy,out/(tag+'_trace.npz'),full)
    selected=cloud[probe.selected]
    v,c,n,total=probe.last
    actual_selected=np.concatenate([arr[:int(num)] for arr,num in zip(v.numpy(),n.numpy())])
    actual_selected[:,2]-=np.float32(z)
    local=(np.sum((selected[:,:2]-xy)**2,axis=1)<=.55**2)
    coords=c.numpy()
    local_pillars=np.sum((coords[:,:2]*probe.base.size[:2]+probe.base.bounds[:2]+probe.base.size[:2]/2-xy)**2,axis=1)<=.7**2
    np.savez_compressed(out/(tag+'_pillars.npz'),coords=coords[local_pillars],input_counts=total[local_pillars],
                        counts=n.numpy()[local_pillars],selected_xyzi=v.numpy()[local_pillars],selected_source_ids=ids[probe.selected[local]])
    inside=((p[:,:3]>=probe.base.bounds[:3])&(p[:,:3]<probe.base.bounds[3:])).all(1)
    row.update(tag=tag,sampling=mode,model_z=z,intensity_divisor=divisor,zero_intensity=zero,
               seconds=time.perf_counter()-start,input_points=len(p),input_sha256=sha_bytes(cloud),adapted_sha256=sha_bytes(p),ids_sha256=sha_bytes(ids),
               before=height_summary(cloud,xy),after=height_summary(actual_selected,xy),model_range_dropped=int((~inside).sum()),
               local_model_range_dropped=int((cylinder(cloud,xy)&~inside).sum()),voxels=len(coords),
               pillars_over32=int((total>32).sum()),source_ids=np.unique(ids).size,
               freeze_pillars=len(freeze) if freeze else 0)
    print(json.dumps({k:row[k] for k in ['tag','local_anchor_max','raw_containing_max','old_ccw_final_target','seconds']},ensure_ascii=False),flush=True)
    return row


def sha_bytes(a):
    import hashlib
    return hashlib.sha256(a.tobytes()).hexdigest()


def context_cloud(b,bids,other,otherids,xy):
    local=cylinder(b,xy);allowed=set(otherids[~cylinder(other,xy)].tolist())|set(bids[local].tolist())
    keep=np.array([int(i) in allowed for i in bids]);cloud=b[keep];ids=bids[keep]
    np.testing.assert_array_equal(cloud[cylinder(cloud,xy)],b[local])
    np.testing.assert_array_equal(ids[cylinder(cloud,xy)],bids[local])
    return cloud,ids


def self_check(model):
    # Oblique yaw regression, upstream zero-delta bottom-box contract.
    b=np.array([[0,0,-.6,4,.2,1.73,np.pi/4]],dtype='f4')
    assert containing(b,[1,-1])[0] and not containing(b,[1,1])[0]
    assert covers_xy(b[0],[1,-1]) and not covers_xy(b[0],[1,1])
    decode=model.get_predicted_bboxes_single.__globals__['anchors2bboxes']
    np.testing.assert_allclose(decode(torch.from_numpy(b),torch.zeros((1,7))).numpy(),b,atol=1e-7)
    bad=model.state_dict().copy();bad.pop(next(iter(bad)))
    try:model.load_state_dict(bad,strict=True)
    except RuntimeError:pass
    else:raise AssertionError('partial checkpoint accepted')
    print('PASS: oblique handedness, anchor zero delta bottom/wlh, strict missing key rejects',flush=True)


def main():
    p=argparse.ArgumentParser();p.add_argument('stage',choices=['representative','all']);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False)
    model=load_model(UP/'epoch_160.pth',UP);torch.set_num_threads(4)
    self_check(model)
    base=model.pillar_layer.voxel_layer;probe=SamplingProbe(base);model.pillar_layer.voxel_layer=probe
    mf=json.loads((FG/'manifest.json').read_text(encoding='utf-8'));rawmf=json.loads((PRE/'manifest.json').read_text(encoding='utf-8'))
    assert mf['input_manifest_sha256']==sha(PRE/'manifest.json')
    truth={s['session']:s for s in json.loads(SEED_FILE.read_text(encoding='utf-8'))['sessions']}
    config=dict(stage=a.stage,checkpoint_sha256=sha(UP/'epoch_160.pth'),foreground_manifest_sha256=sha(FG/'manifest.json'),
                prepared_manifest_sha256=sha(PRE/'manifest.json'),seed_sha256=sha(SEED_FILE),script_sha256=sha(Path(__file__)),
                thresholds=dict(score=model.score_thr,nms=model.nms_thr,topk=model.nms_pre,max_num=model.max_num),
                sampling='stable z-order then 32 equally spaced rounded ranks including endpoints, same voxels/capacity',
                accuracy='NOT_RUN: approximate seeds only',physical=False,registration='WARN preserved')
    (a.out/'config.json').write_text(json.dumps(config,indent=2),encoding='utf-8')
    rows=[]
    if a.stage=='representative':
        cloud=np.fromfile(UP/'000134.bin',dtype='<f4').reshape(-1,4)
        # KITTI input must not receive our sensor intensity normalization or leveling.
        rows.append(run_probe(model,probe,cloud,np.arange(len(cloud)),[10,0],a.out,'kitti_positive',z=0,divisor=1))
        empty=rawmf['sessions'][0];cloud=np.fromfile(PRE/empty['sid']/empty['frames'][27]['file'],dtype='<f4').reshape(-1,4)
        rows.append(run_probe(model,probe,cloud,np.arange(len(cloud)),[2.1,-.5],a.out,'empty_template27'))
    with (a.out/'rows.jsonl').open('x',encoding='utf-8') as log:
        for s in mf['sessions']:
            sid=s['sid'];xy=truth[sid]['xy_m'];rawsession=next(r for r in rawmf['sessions'] if r['sid']==sid)
            frames=s['frames'] if a.stage=='all' else [s['frames'][len(s['frames'])//2]]
            for frame in frames:
                prefix=sid+'_'+str(frame['index'])
                variants=['B_workspace','E_cleanup'] if a.stage=='all' else ['A_full','B_workspace','C_reference','E_cleanup']
                cached={}
                for variant in variants:
                    cloud,ids=load_cloud(s,frame,variant,rawsession);cached[variant]=(cloud,ids)
                    experiments=[('base',{})]
                    if variant in ['B_workspace','E_cleanup']:
                        experiments += [('zrank',dict(mode='z_rank32'))]
                        if a.stage=='representative':experiments += [('int65535',dict(divisor=65535)),('intzero',dict(zero=True)),('z_anchor',dict(z=-.6)),('z_ground',dict(z=0))]
                    for name,kwargs in experiments:
                        row=run_probe(model,probe,cloud,ids,xy,a.out,prefix+'_'+variant+'_'+name,full=a.stage=='representative',**kwargs)
                        row.update(sid=sid,index=frame['index'],variant=variant,experiment=name)
                        rows.append(row);log.write(json.dumps(row,ensure_ascii=False)+'\n');log.flush()
                        if a.stage=='representative' and variant=='B_workspace' and name=='base':
                            v,c,n,total=probe.last
                            # Freeze every pillar intersecting the seed cylinder (using actual B points).
                            q=cloud.copy();q[:,2]-=np.float32(1.73)
                            keys=set(map(tuple,np.floor((q[cylinder(cloud,xy),:3]-base.bounds[:3])/base.size).astype('i4')))
                            frozen={tuple(k):(v[j].clone(),n[j].clone()) for j,k in enumerate(c.numpy()) if tuple(k) in keys}
                if a.stage=='representative':
                    b,bids=cached['B_workspace']
                    for other in ['C_reference','E_cleanup']:
                        cloud,ids=context_cloud(b,bids,*cached[other],xy)
                        for name,freeze in [('context_points',None),('context_pillars',frozen)]:
                            row=run_probe(model,probe,cloud,ids,xy,a.out,prefix+'_'+other+'_'+name,freeze=freeze)
                            row.update(sid=sid,index=frame['index'],variant=other,experiment=name,local_input_identical_to_B=True)
                            if freeze:
                                v,c,n,_=probe.last
                                found={tuple(k):(v[j],n[j]) for j,k in enumerate(c.numpy())}
                                for key,(bv,bn) in frozen.items():
                                    assert key in found;np.testing.assert_array_equal(found[key][0].numpy(),bv.numpy());assert found[key][1]==bn
                                row['local_intersecting_pillars_equal_B']=True
                            rows.append(row);log.write(json.dumps(row,ensure_ascii=False)+'\n');log.flush()
    (a.out/'rows.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
    print('DONE',a.stage,len(rows),flush=True)


if __name__=='__main__':main()
