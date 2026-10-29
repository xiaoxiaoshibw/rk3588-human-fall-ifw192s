"""Handcrafted-feature RF trained on three environments, tested once on a fourth."""
import argparse
import json
from pathlib import Path
import joblib
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from causal_public_lidar import PARAMS,dump,matrix,report
from train_public_lidar import sha


def run(window_caches,frame_caches,test_cache,out,models,window=30):
    out.mkdir(parents=True,exist_ok=True);models.mkdir(parents=True,exist_ok=True)
    train_X=[];train_y=[]
    for path in list(window_caches)+list(frame_caches):
        if str(path).endswith('_features.npz'):
            with np.load(path,allow_pickle=False) as z:
                train_X.append(z['X']);train_y.append(z['y'])
        else:
            with np.load(path,allow_pickle=False) as cache:
                X,y,_,_,_=matrix(cache,window)
            train_X.append(X);train_y.append(y)
    X=np.concatenate(train_X);y=np.concatenate(train_y)
    model=RandomForestClassifier(**PARAMS).fit(X,y)
    path=models/('w%d_multi.joblib'%window)
    joblib.dump({'model':model,'window':window,'schema':'sequence_xyz_v1','train_samples':int(len(y))},path)
    with np.load(test_cache,allow_pickle=False) as cache:
        Xt,yt,groups,seq,rows=matrix(cache,window)
    p=joblib.load(path)['model'].predict_proba(Xt)
    result=report(out,'TEST_rf_multi',rows,yt,p,seq,groups)
    dump(out/'RF_MULTI_SUMMARY.json',{'train_sources':[str(p) for p in list(window_caches)+list(frame_caches)],
         'train_samples':int(len(y)),'test_source':str(test_cache),'model':str(path),'model_sha256':sha(path),
         'window_frames':window,'parameters':PARAMS,'selection':'single fit, no tuning on the test environment',
         'scores':{k:{s:result[k][s] for s in ['samples','accuracy','macro_f1']} for k in ['window','sequence_mean_probability']}})
    print({k:{s:result[k][s] for s in ['accuracy','macro_f1']} for k in ['window','sequence_mean_probability']},flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--window-caches',type=Path,nargs='*',default=[])
    p.add_argument('--frame-caches',type=Path,nargs='*',default=[]);p.add_argument('--test',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--models',type=Path,required=True)
    p.add_argument('--window',type=int,default=30);a=p.parse_args()
    run(a.window_caches,a.frame_caches,a.test,a.output,a.models,a.window)