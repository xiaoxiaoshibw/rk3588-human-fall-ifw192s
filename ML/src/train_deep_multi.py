"""Train one causal deep model across environments and test a held-out environment."""
import argparse
import json
from pathlib import Path
import numpy as np
import torch
from torch.nn import functional as F
from train_deep_lidar import CausalPointNet,SEED,WINDOW,batch,last_step,predict,windows
from causal_public_lidar import dump,report
from train_public_lidar import sha


def load(paths):
    arrays={};rows=[]
    for path in paths:
        with np.load(path,allow_pickle=False) as cache:
            a,r=windows(cache)
        overlap=set(arrays)&set(a)
        if overlap:raise ValueError('Duplicate sequence across caches: %r'%sorted(overlap)[:3])
        arrays.update(a);rows.extend(r)
    return arrays,rows


def run(train_caches,test_cache,out,models,epochs):
    out.mkdir(parents=True,exist_ok=True);models.mkdir(parents=True,exist_ok=True)
    torch.set_num_threads(4);torch.use_deterministic_algorithms(True)
    torch.manual_seed(SEED);np.random.seed(SEED)
    arrays,rows=load(train_caches)
    points=sorted({int(x.shape[1]) for x in arrays.values()})
    if len(points)!=1:raise ValueError('Mixed point budgets')
    y=np.asarray([r['truth'] for r in rows])
    history=[json.loads(line) for line in (out/'TRAINING.jsonl').read_text(encoding='utf-8').splitlines()] if (out/'TRAINING.jsonl').is_file() else []
    state_path=models/'multi_state.pt'
    model=CausalPointNet();optim=torch.optim.AdamW(model.parameters(),lr=.001,weight_decay=.01);start=0
    if state_path.is_file():
        state=torch.load(state_path,map_location='cpu',weights_only=True)
        model.load_state_dict(state['model']);optim.load_state_dict(state['optim']);start=state['epoch']
        print('resume at epoch',start,flush=True)
    for epoch in range(start,epochs):
        model.train();order=np.random.default_rng([SEED,epoch]).permutation(len(rows));total=0.;correct=0
        for lo in range(0,len(order),32):
            ix=order[lo:lo+32];x,target,lengths=batch(arrays,rows,ix)
            optim.zero_grad(set_to_none=True);logits=last_step(model(x),lengths)
            loss=F.cross_entropy(logits,target)
            if not torch.isfinite(loss):raise ValueError('Nonfinite loss')
            loss.backward();torch.nn.utils.clip_grad_norm_(model.parameters(),5.);optim.step()
            total+=float(loss.detach())*len(ix);correct+=int((logits.argmax(1)==target).sum())
        rec={'epoch':epoch+1,'loss':total/len(rows),'train_online_accuracy':correct/len(rows)}
        with (out/'TRAINING.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(rec)+'\n')
        history.append(rec);print(json.dumps(rec),flush=True)
        torch.save({'model':model.state_dict(),'optim':optim.state_dict(),'epoch':epoch+1},state_path)
    path=models/'multi.pt'
    with path.open('xb') as f:torch.save(model.state_dict(),f)
    loaded=CausalPointNet();loaded.load_state_dict(torch.load(path,map_location='cpu',weights_only=True))
    splits={}
    for name,caches in [('train',train_caches),('test',[test_cache])]:
        a,r=load(caches)
        p=predict(loaded,a,r,np.arange(len(r)))
        yy=np.asarray([x['truth'] for x in r]);seqs=np.asarray([x['sequence'] for x in r])
        groups=np.asarray([x['subject'] for x in r])
        result=report(out,'MULTI_'+name,r,yy,p,seqs,groups)
        splits[name]={'windows':len(r),'sequences':len(set(seqs)),'subjects':sorted(set(groups)),
                      'accuracy':result['window']['accuracy'],'sequence_accuracy':result['sequence_mean_probability']['accuracy'],
                      'macro_f1':result['window']['macro_f1'],'sequence_macro_f1':result['sequence_mean_probability']['macro_f1']}
        print(name,splits[name],flush=True)
    dump(out/'MULTI_SUMMARY.json',{'train_caches':{str(p):sha(p) for p in train_caches},'test_cache':{str(test_cache):sha(test_cache)},
         'checkpoint':{str(path):sha(path)},'epochs_fixed':epochs,'points':points[0],'window_frames':WINDOW,'stride':10,
         'selection':'last fixed epoch; test environment never used for fitting or selection',
         'label_kind':'inherited_sequence_action','splits':splits,'history':history,
         'scope':'multi-environment public-data training; IFW192S effect and per-frame fall GT remain UNKNOWN'})


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--train',type=Path,nargs='+',required=True)
    p.add_argument('--test',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--models',type=Path,required=True);p.add_argument('--epochs',type=int,default=24);a=p.parse_args()
    run(a.train,a.test,a.output,a.models,a.epochs)