"""Small PointNet-style encoder + causal temporal convolutions. PC research only."""
import argparse
import hashlib
import json
from pathlib import Path
import random
import time
import zipfile
import joblib
import numpy as np
import torch
from torch import nn
from torch.nn import functional as F
from causal_public_lidar import bounds, scores, report, dump
from train_public_lidar import ordered_names, sha

SEED=42
POINTS=64
WINDOW=30


class CausalPointNet(nn.Module):
    def __init__(self,classes=27):
        super().__init__()
        self.point=nn.Sequential(nn.Linear(3,16),nn.ReLU(),nn.Linear(16,32),nn.ReLU())
        self.convs=nn.ModuleList([nn.Conv1d(64,64,3,dilation=d) for d in [1,2,4,8]])
        self.norms=nn.ModuleList([nn.LayerNorm(64) for _ in self.convs])
        self.head=nn.Linear(64,classes)

    def forward(self,x):
        if x.ndim!=4 or x.shape[-1]!=3 or x.shape[1]<1 or x.shape[2]<1 or not torch.isfinite(x).all():
            raise ValueError('Expected finite B,T,N,3 XYZ')
        # Translation removed using the first available frame only, never future statistics.
        origin=x[:,0].median(dim=1).values[:,None,None,:]
        point=self.point(x-origin)
        features=torch.cat((point.amax(dim=2),point.mean(dim=2)),dim=-1).transpose(1,2)
        for dilation,conv,norm in zip([1,2,4,8],self.convs,self.norms):
            block=conv(F.pad(features,(2*dilation,0)))
            block=norm(block.transpose(1,2)).transpose(1,2)
            features=F.relu(features+block)
        return self.head(features.transpose(1,2))


def prepare(archive,out,points=POINTS):
    out.mkdir(parents=True,exist_ok=False);groups={};source=[]
    with zipfile.ZipFile(archive) as z:
        by_sequence={}
        for name in z.namelist():
            if '/lidar/' in name and name.endswith('.bin'):
                by_sequence.setdefault('/'.join(name.split('/')[:3]),[]).append(name)
        for sequence,names in sorted(by_sequence.items()):
            frames=[];members=[]
            for name in ordered_names(names,'mmfi'):
                raw=z.read(name)
                if len(raw)%24:raise ValueError('Invalid XYZ bytes')
                p=np.frombuffer(raw,dtype='<f8').reshape(-1,3)
                if len(p)<10 or not np.isfinite(p).all():raise ValueError('Invalid frame '+name)
                # Fixed source-only seed and sampling without replacement when possible.
                seed=int.from_bytes(hashlib.sha256(name.encode()).digest()[:8],'little')
                rng=np.random.default_rng(seed)
                idx=rng.choice(len(p),points,replace=len(p)<points)
                frames.append(p[idx].astype(np.float32))
                members.append(hashlib.sha256(raw).hexdigest())
            groups[sequence]=np.asarray(frames)
            source.append({'sequence':sequence,'frames':len(frames),
                           'ordered_member_sha256':members})
            if len(groups)%30==0:print('point cache',len(groups),flush=True)
    np.savez_compressed(out/('points%d.npz'%points),**groups)
    dump(out/'INPUT.json',{'archive':str(archive),'archive_sha256':sha(archive),
         'points_per_frame':points,'sampling':'deterministic random source rows; no GT crop',
         'labels':'inherited sequence action, not frame GT','sequences':source})


def windows(cache,window=WINDOW,allow_short=True):
    arrays={s:torch.from_numpy(cache[s]) for s in sorted(cache.files)}
    rows=[]
    for sequence,x in arrays.items():
        spans=bounds(len(x),window)
        # Short sequences keep one causal window over their real length instead of being dropped.
        if not spans and allow_short and len(x)>=1:spans=[(0,len(x))]
        for lo,hi in spans:
            rows.append({'sequence':sequence,'subject':sequence.split('/')[1],
                         'truth':int(sequence.split('/')[2][1:]),'begin_index':lo,'end_index_exclusive':hi,
                         'label_kind':'inherited_sequence_action'})
    return arrays,rows


def batch(arrays,rows,index):
    items=[arrays[rows[i]['sequence']][rows[i]['begin_index']:rows[i]['end_index_exclusive']] for i in index]
    lengths=torch.tensor([len(x) for x in items],dtype=torch.long)
    if int(lengths.max())==int(lengths.min()):
        x=torch.stack(items)
    else:
        x=torch.zeros((len(items),int(lengths.max()),items[0].shape[-2],3))
        for i,item in enumerate(items):x[i,:len(item)]=item
    y=torch.tensor([rows[i]['truth']-1 for i in index],dtype=torch.long)
    return x,y,lengths


def last_step(logits,lengths):
    return logits[torch.arange(len(lengths)),lengths-1]


def predict(model,arrays,rows,index,batch_size=32):
    model.eval();all_p=[]
    with torch.no_grad():
        for lo in range(0,len(index),batch_size):
            x,_,lengths=batch(arrays,rows,index[lo:lo+batch_size])
            all_p.append(torch.softmax(last_step(model(x),lengths),dim=-1).numpy())
    return np.concatenate(all_p)


def train(cache_path,out,models,epochs,fold_count,only_fold=None):
    # Resumable per fold: an existing checkpoint is only reloaded, never retrained.
    out.mkdir(parents=True,exist_ok=True);models.mkdir(parents=True,exist_ok=True)
    torch.set_num_threads(4);torch.use_deterministic_algorithms(True)
    random.seed(SEED);np.random.seed(SEED);torch.manual_seed(SEED)
    with np.load(cache_path,allow_pickle=False) as cache:arrays,rows=windows(cache)
    points=sorted({int(x.shape[1]) for x in arrays.values()})
    if len(points)!=1:raise ValueError('All cached frames must share one point budget')
    points=points[0]
    y=np.asarray([r['truth'] for r in rows]);groups=np.asarray([r['subject'] for r in rows]);seq=np.asarray([r['sequence'] for r in rows])
    probabilities=np.full((len(rows),27),np.nan);splits=[]
    for fold in ([only_fold] if only_fold is not None else range(fold_count)):
        prior=joblib.load(Path('ML/models/public_lidar_20261022/mmfi')/('fold_%d.joblib'%fold))
        tr=np.flatnonzero(np.isin(groups,prior['train_groups']));te=np.flatnonzero(np.isin(groups,prior['test_groups']))
        assert not set(groups[tr])&set(groups[te])
        path=models/('fold_%d.pt'%fold);trained_this_invocation=False
        if path.is_file():
            torch.manual_seed(SEED);model=CausalPointNet()
            model.load_state_dict(torch.load(path,map_location='cpu',weights_only=True));print('fold',fold,'checkpoint reused',flush=True)
        else:
            torch.manual_seed(SEED);model=CausalPointNet();optim=torch.optim.AdamW(model.parameters(),lr=.001,weight_decay=.01)
            generator=np.random.default_rng(SEED);started=time.perf_counter()
            for epoch in range(epochs):
                model.train();order=generator.permutation(tr);total_loss=0.;correct=0
                for lo in range(0,len(order),32):
                    ix=order[lo:lo+32];x,target,lengths=batch(arrays,rows,ix)
                    optim.zero_grad(set_to_none=True);logits=last_step(model(x),lengths)
                    loss=F.cross_entropy(logits,target)
                    if not torch.isfinite(loss):raise ValueError('Nonfinite loss')
                    loss.backward();torch.nn.utils.clip_grad_norm_(model.parameters(),5.);optim.step()
                    total_loss+=float(loss.detach())*len(ix);correct+=int((logits.argmax(1)==target).sum())
                p=predict(model,arrays,rows,te)
                rec={'fold':fold,'epoch':epoch+1,'loss':total_loss/len(tr),'train_online_accuracy':correct/len(tr),
                     'heldout_accuracy':float((p.argmax(1)+1==y[te]).mean()),'elapsed_s':time.perf_counter()-started}
                with (out/'TRAINING.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(rec)+'\n')
                print(json.dumps(rec),flush=True)
            with path.open('xb') as f:torch.save(model.state_dict(),f)
            trained_this_invocation=True
        p=predict(model,arrays,rows,te)
        loaded=CausalPointNet();loaded.load_state_dict(torch.load(path,map_location='cpu',weights_only=True))
        np.testing.assert_array_equal(p,predict(loaded,arrays,rows,te))
        np.savez_compressed(out/('fold_%d_probs.npz'%fold),index=te,probabilities=p)
        record={'fold':fold,'train_groups':prior['train_groups'],'test_groups':prior['test_groups'],
                'train_windows':len(tr),'test_windows':len(te),'checkpoint_sha256':sha(path),
                'trained_this_invocation':trained_this_invocation}
        splits.append(record);dump(out/('fold_%d_SPLIT.json'%fold),record)
        probabilities[te]=p
        print('fold',fold,'predictions saved',flush=True)
    available=[f for f in range(fold_count) if (out/('fold_%d_probs.npz'%f)).is_file()]
    if len(available)!=fold_count:
        (out/'PARTIAL.json').write_text(json.dumps({'folds_saved':available,'requested':fold_count,
            'note':'resume remaining folds'},indent=2),encoding='utf-8')
        return
    probabilities=np.full((len(rows),27),np.nan)
    for fold in available:
        with np.load(out/('fold_%d_probs.npz'%fold),allow_pickle=False) as z:probabilities[z['index']]=z['probabilities']
    splits=[json.loads((out/('fold_%d_SPLIT.json'%f)).read_text(encoding='utf-8')) for f in available]
    history=[json.loads(line) for line in (out/'TRAINING.jsonl').read_text(encoding='utf-8').splitlines()] if (out/'TRAINING.jsonl').is_file() else []
    valid=np.isfinite(probabilities).all(1)
    result=report(out,'E01_deep30',[r for r,v in zip(rows,valid) if v],y[valid],probabilities[valid],seq[valid],groups[valid])
    dump(out/'TRAINING.json',history);dump(out/'SPLITS.json',splits)
    dump(out/'SUMMARY.json',{'scores':result,'folds_completed':fold_count,'epochs_fixed':epochs,
         'selection':'last fixed epoch, no heldout epoch selection','network':'point MLP3-16-32, mean+max pool, 4 causal TCN64 blocks dilation1/2/4/8, head27',
         'parameters':sum(p.numel() for p in model.parameters()),'window_frames':WINDOW,'stride':10,'points':points,
         'optimizer':'AdamW lr0.001 weight_decay0.01 batch32 clip5','seed':SEED,
         'training_cache_sha256':sha(cache_path),'source_sha256':sha(__file__),
         'torch':torch.__version__,'cuda':torch.cuda.is_available(),'scope':'CPU small deep baseline; %d sampled points, unsegmented whole cloud; no claim of optimized deep model'%points,
         'E02_use':'not read by this training; future development may use E02 but must no longer call it independent after selection',
         'histories':'TRAINING.json holds per-epoch records written by this resumable runner; folds retrained after a runner crash may lack earlier epochs',
         'IFW192S_effectiveness':'UNKNOWN','deployment':'NOT_DEPLOYED'})


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['prepare','train']);p.add_argument('--input',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--models',type=Path)
    p.add_argument('--epochs',type=int,default=10);p.add_argument('--folds',type=int,default=5)
    p.add_argument('--fold',type=int);p.add_argument('--points',type=int,default=POINTS);a=p.parse_args()
    if a.mode=='prepare':prepare(a.input,a.output,a.points)
    else:train(a.input,a.output,a.models,a.epochs,a.folds,a.fold)
