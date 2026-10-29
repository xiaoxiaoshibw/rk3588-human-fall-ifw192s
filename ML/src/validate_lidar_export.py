"""Check primary RF exports on all OOF windows and float32 threshold probes."""
import argparse
import ast
import json
from pathlib import Path
import joblib
import numpy as np
from export_lidar_rf import export
from lidar_numpy_runtime import NumpyForest
from train_public_lidar import sha


def compare(model, runtime, X):
    model.n_jobs=1
    expected=model.predict_proba(X);actual=runtime.predict_proba(X)
    np.testing.assert_allclose(actual,expected,atol=1e-14,rtol=0)
    np.testing.assert_array_equal(runtime.classes[np.argmax(actual,axis=1)],model.classes_[np.argmax(expected,axis=1)])
    return {'samples':len(X),'max_abs_probability_error':float(np.max(np.abs(actual-expected))),
            'class_parity':True,'tolerance':1e-14}


def run(models,evidence):
    results={}
    with np.load(evidence/'E01_w30_features.npz',allow_pickle=False) as data:
        for fold in range(5):
            source=models/('w30_fold_%d.joblib'%fold);doc=joblib.load(source)
            path=models/('w30_fold_%d_numpy.npz'%fold);export(doc['model'],path)
            runtime=NumpyForest(path);mask=np.isin(data['groups'],doc['test_groups'])
            results['fold_%d'%fold]=compare(doc['model'],runtime,data['X'][mask])
    model=joblib.load(models/'w30_final.joblib')['model'];runtime=NumpyForest(models/'w30_numpy.npz')
    probes=[];nodes=0
    for i,estimator in enumerate(model.estimators_):
        tree=estimator.tree_
        for node,(feature,threshold) in enumerate(zip(tree.feature,tree.threshold)):
            if feature<0 or (i>0 and node>0):continue
            nodes+=1
            for value in [threshold,float(np.nextafter(np.float32(threshold),np.float32(-np.inf))),
                          float(np.nextafter(np.float32(threshold),np.float32(np.inf)))]:
                x=np.zeros(114);x[feature]=value;probes.append(x)
    results['threshold_probes']=dict(compare(model,runtime,np.asarray(probes)),split_nodes=nodes,
        scope='every split of tree 0 plus roots of all trees; threshold/exact float32 neighbors')
    for env in ['E01','E02']:
        path=evidence/(env+'_w30_features.npz')
        if path.exists():
            with np.load(path,allow_pickle=False) as data:results[env+'_final']=compare(model,runtime,data['X'])
    path=evidence/'raw_replay/inference_inputs.npz'
    if path.exists():
        with np.load(path,allow_pickle=False) as data:
            results['raw_replay']=compare(model,runtime,data['X'])
            np.testing.assert_allclose(runtime.predict_proba(data['X']),data['p'],atol=0,rtol=0)
    for path in [Path('ML/src/lidar_numpy_runtime.py')]:
        ast.parse(path.read_text(encoding='utf-8'),feature_version=(3,8))
    result={'checks':results,'runtime_python38_syntax':True,'native_python38_numpy117_execution':'UNKNOWN',
            'models':{p.name:sha(p) for p in models.glob('*numpy.npz')},
            'source':{p.name:sha(p) for p in Path('ML/src').glob('*.py')}}
    with (evidence/'EXPORT_PARITY.json').open('x',encoding='utf-8') as f:json.dump(result,f,indent=2)
    print(json.dumps(results,indent=2),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--models',type=Path,required=True);p.add_argument('--evidence',type=Path,required=True)
    a=p.parse_args();run(a.models,a.evidence)
