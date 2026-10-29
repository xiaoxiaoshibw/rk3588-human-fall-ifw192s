"""Frozen causal RF evaluated on another environment's cached 19-dim frame features."""
import argparse
import json
from pathlib import Path
import joblib
import numpy as np
from causal_public_lidar import dump,matrix,report
from train_public_lidar import sha


def run(cache_path,model_path,out,stem,window=30):
    out.mkdir(parents=True,exist_ok=True)
    with np.load(cache_path,allow_pickle=False) as cache:
        X,y,groups,seq,rows=matrix(cache,window)
    frozen=joblib.load(model_path)
    model=frozen['model'] if isinstance(frozen,dict) else frozen
    p=model.predict_proba(X)
    result=report(out,stem,rows,y,p,seq,groups)
    predicted=np.bincount(p.argmax(1),minlength=27)
    dump(out/(stem+'_EVAL.json'),{'cache':str(cache_path),'cache_sha256':sha(cache_path),
         'model':str(model_path),'model_sha256':sha(model_path),'window_frames':window,'windows':len(y),
         'sequences':len(set(seq)),'subjects':sorted(set(groups)),
         'labels':'inherited sequence action id; inference only, no fitting on this environment',
         'classes_predicted':int((predicted>0).sum()),'largest_predicted_class_share':float(predicted.max()/len(y)),
         'scores':{k:{s:result[k][s] for s in ['samples','accuracy','macro_f1']} for k in ['window','sequence_mean_probability']},
         'scope':'cross-environment inference of the frozen E01 30-frame handcrafted-feature RF'})
    print(stem,{k:{s:result[k][s] for s in ['accuracy','macro_f1']} for k in ['window','sequence_mean_probability']},flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--input',type=Path,required=True);p.add_argument('--model',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--stem',required=True)
    p.add_argument('--window',type=int,default=30);a=p.parse_args()
    run(a.input,a.model,a.output,a.stem,a.window)