"""Untuned original E01 full-sequence model on untouched E02."""
import argparse
import json
from pathlib import Path
import joblib
import numpy as np
from causal_public_lidar import WINDOWS, matrix, report, summarize, scores, dump
from train_public_lidar import sha
from validate_lidar_export import compare
from lidar_numpy_runtime import NumpyForest


def run(evidence,baseline,models):
    freeze=json.loads((evidence/'FREEZE.json').read_text(encoding='utf-8'))
    path=baseline/'final_model.joblib'
    assert sha(path)==freeze['baseline_models'][path.name]
    model=joblib.load(path)['model'];results={}
    with np.load(evidence/'E02_cache/frames.npz',allow_pickle=False) as cache:
        for window in WINDOWS:
            X,y,groups,seq,rows=matrix(cache,window)
            results[str(window)]=report(evidence,'E02_w%d_full_train'%window,rows,y,model.predict_proba(X),seq,groups)
        X=np.asarray([summarize(cache[n]) for n in sorted(cache.files)])
        y=np.asarray([int(n.split('/')[2][1:]) for n in sorted(cache.files)])
        results['complete_sequence']=scores(y,model.predict_proba(X))
    dump(evidence/'E02_ORIGINAL_BASELINE.json',{'results':results,'model_sha256':sha(path),'selection':'none'})
    primary=joblib.load(models/'w30_final.joblib')['model'];runtime=NumpyForest(models/'w30_numpy.npz')
    with np.load(evidence/'E02_w30_features.npz',allow_pickle=False) as data:
        parity=compare(primary,runtime,data['X'])
    dump(evidence/'E02_EXPORT_PARITY.json',parity)
    print('E02 original full',results['complete_sequence'],flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--evidence',type=Path,required=True)
    p.add_argument('--baseline',type=Path,default=Path('ML/models/public_lidar_20261022/mmfi'))
    p.add_argument('--models',type=Path,required=True);a=p.parse_args();run(a.evidence,a.baseline,a.models)
