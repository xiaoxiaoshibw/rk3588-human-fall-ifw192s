"""Frozen E01 deep checkpoints evaluated on untouched environments. Inference only."""
import argparse
from pathlib import Path
import numpy as np
import torch
from train_deep_lidar import CausalPointNet,predict,windows
from causal_public_lidar import dump,report
from train_public_lidar import sha


def run(cache_path,models,out,stem,folds=5):
    out.mkdir(parents=True,exist_ok=True)
    with np.load(cache_path,allow_pickle=False) as cache:arrays,rows=windows(cache)
    y=np.asarray([r['truth'] for r in rows]);seq=np.asarray([r['sequence'] for r in rows])
    groups=np.asarray([r['subject'] for r in rows]);index=np.arange(len(rows))
    total=np.zeros((len(rows),27));paths=[]
    for fold in range(folds):
        path=models/('fold_%d.pt'%fold);paths.append(path)
        model=CausalPointNet();model.load_state_dict(torch.load(path,map_location='cpu',weights_only=True))
        total+=predict(model,arrays,rows,index)
        print(stem,'fold',fold,'done',flush=True)
    probabilities=total/folds
    result=report(out,stem,rows,y,probabilities,seq,groups)
    dump(out/(stem+'_EVAL.json'),{'cache':str(cache_path),'cache_sha256':sha(cache_path),
         'checkpoints':{p.name:sha(p) for p in paths},'ensemble':'mean softmax of the five E01 fold checkpoints',
         'folds':folds,'windows':len(rows),'sequences':len(set(seq)),'subjects':sorted(set(groups)),
         'points_per_frame':int(next(iter(arrays.values())).shape[1]),'window_frames':30,'stride':10,
         'labels':'inherited sequence action id; no fitting, no threshold tuning on this environment',
         'scores':{k:{s:result[k][s] for s in ['samples','accuracy','macro_f1']} for k in ['window','sequence_mean_probability']},
         'scope':'cross-environment inference of frozen E01 model; environment and participants both shift'})
    print(stem,{k:{s:result[k][s] for s in ['accuracy','macro_f1']} for k in ['window','sequence_mean_probability']},flush=True)
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--input',type=Path,required=True)
    p.add_argument('--models',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--stem',required=True);p.add_argument('--folds',type=int,default=5);a=p.parse_args()
    run(a.input,a.models,a.output,a.stem,a.folds)