"""CPU sequence baselines; never deploys models or modifies source datasets.

MM-Fi: 27 action classes, subject-disjoint evaluation, LiDAR-only input.
Synthetic: fall/nonfall sequence labels, parent motion family-disjoint evaluation.
Synthetic labels describe whole animations, not the instant a fall starts.
"""
import argparse
from collections import Counter, defaultdict
import hashlib
import io
import json
from pathlib import Path
import platform
import re
import time
import zipfile

import joblib
import numpy as np
import sklearn
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, balanced_accuracy_score, confusion_matrix, f1_score
from sklearn.model_selection import StratifiedGroupKFold


def sha(path):
    with Path(path).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def frame_feature(points):
    """XYZ shape and centroid; no intensity, class IDs, mesh or GT as input."""
    p = np.asarray(points, dtype=np.float64)
    if p.ndim != 2 or p.shape[1] != 3 or len(p) < 10 or not np.isfinite(p).all():
        raise ValueError('A frame needs at least 10 finite XYZ points')
    center = np.median(p, axis=0)
    q = p-center
    quantiles = np.percentile(q, [10, 50, 90], axis=0).reshape(-1)
    eigen = np.maximum(np.linalg.eigvalsh(np.cov(q.T)), 0)[::-1]
    return np.concatenate(([np.log1p(len(p))], center, quantiles, eigen,
                           eigen/max(eigen.sum(), 1e-12)))


def sequence_feature(frames):
    """Fixed-length summary with ordered temporal differences; no assumed fps."""
    x = np.asarray([frame_feature(f) for f in frames])
    if len(x) < 5:
        raise ValueError('Sequence too short')
    # Remove absolute location: retain framewise displacement from sequence origin.
    x[:, 1:4] -= x[0, 1:4]
    delta = np.diff(x, axis=0)
    result = np.concatenate((x.mean(0), x.std(0), np.percentile(x, [10, 90], axis=0).ravel(),
                             np.abs(delta).mean(0), x[-1]-x[0]))
    assert np.isfinite(result).all()
    return result.astype(np.float32)


def ordered_names(names, dataset):
    if dataset == 'mmfi':
        return sorted(names, key=lambda n:int(re.search(r'frame(\d+)\.bin$', n).group(1)))
    return sorted(names, key=lambda n:int(re.search(r'_frame_(\d+)\.csv$', n).group(1)))


def synthetic_xyz(data):
    # Reuse the existing streaming CSV parser; only XYZ are model inputs.
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]/'pc_apps/human_ml'))
    from lidata_load import parse_csv_bytes
    points = parse_csv_bytes(data)[:, :3]
    lines=[line for line in data.decode('utf-8',errors='strict').splitlines() if line.strip()]
    if not lines or 'X' not in lines[0] or len(points) != len(lines)-1:
        raise ValueError('empty CSV, invalid header or skipped malformed rows')
    return points


def collect(archives, dataset, out):
    rows, audit = [], []
    for path in archives:
        with zipfile.ZipFile(path) as z:
            assert z.testzip() is None
            groups = defaultdict(list)
            for name in z.namelist():
                if dataset == 'mmfi' and re.search(r'/lidar/frame\d+\.bin$', name):
                    groups['/'.join(name.split('/')[:3])].append(name)
                elif dataset == 'synthetic' and re.search(r'_frame_\d+\.csv$', name):
                    groups[name.rsplit('/', 1)[0]].append(name)
            for seq, names in sorted(groups.items()):
                ordered = ordered_names(names, dataset)
                frames, dropped, hashes = [], [], []
                for name in ordered:
                    payload = z.read(name)
                    try:
                        if dataset == 'mmfi':
                            if len(payload) % 24:
                                raise ValueError('XYZ float64 byte count')
                            points = np.frombuffer(payload, dtype='<f8').reshape(-1, 3)
                        else:
                            points = synthetic_xyz(payload)
                        frame_feature(points)
                    except ValueError as exc:
                        dropped.append({'path':name, 'reason':str(exc)})
                        continue
                    frames.append(points)
                    hashes.append(hashlib.sha256(payload).hexdigest())
                if dataset == 'mmfi':
                    env, subject, action = seq.split('/')
                    label, group = int(action[1:]), subject
                    gt_name = seq+'/ground_truth.npy'
                    gt = np.load(io.BytesIO(z.read(gt_name)), allow_pickle=False)
                    if not np.isfinite(gt).all() or len(gt) != len(ordered):
                        raise ValueError('GT/frame alignment mismatch: '+seq)
                else:
                    label = 1 if '/Fall Data ' in seq else 0 if '/No Fall Data ' in seq else -1
                    if label < 0:
                        raise ValueError('Unknown synthetic label: '+seq)
                    group = seq.rsplit('/', 1)[0]
                    gt = None
                rec = {'sequence':seq, 'source_archive':str(path), 'label':label, 'group':group,
                       'frames':len(ordered), 'usable_frames':len(frames), 'dropped_frames':dropped,
                       'point_min':min(map(len, frames)) if frames else 0,
                       'point_max':max(map(len, frames)) if frames else 0,
                       'content_sha256':hashlib.sha256(''.join(hashes).encode()).hexdigest(),
                       'gt_shape':list(gt.shape) if gt is not None else None}
                # Missing frames can distort temporal differences; exclude the whole sequence.
                rec['eligible'] = len(frames) >= 5 and not dropped
                audit.append(rec)
                if rec['eligible']:
                    rows.append((sequence_feature(frames), label, group, seq))
                if len(audit) % 25 == 0:
                    print('checked',len(audit),'sequences; eligible',len(rows),flush=True)
    with (out/'DATA_AUDIT.json').open('x',encoding='utf-8') as f:
        json.dump(audit,f,indent=2)
    if not rows:
        raise ValueError('No eligible sequences')
    X=np.asarray([r[0] for r in rows]); y=np.asarray([r[1] for r in rows])
    groups=np.asarray([r[2] for r in rows]); names=np.asarray([r[3] for r in rows])
    np.savez_compressed(out/'features.npz',X=X,y=y,groups=groups,names=names)
    return X,y,groups,names


def run(args):
    out=Path(args.output); out.mkdir(parents=True,exist_ok=False)
    started=time.monotonic()
    inputs=[{'path':str(p),'bytes':p.stat().st_size,'sha256':sha(p)} for p in map(Path,args.archive)]
    X,y,groups,names=collect(list(map(Path,args.archive)),args.dataset,out)
    labels=sorted(np.unique(y).tolist())
    # Identical complete sequences must not cross folds, even under different paths.
    content_groups=defaultdict(list)
    for rec in json.loads((out/'DATA_AUDIT.json').read_text(encoding='utf-8')):
        if rec['eligible']:
            content_groups[rec['content_sha256']].append(rec['group'])
    for memberships in content_groups.values():
        if len(set(memberships)) > 1:
            raise ValueError('Duplicate sequence appears in different groups')
    folds=StratifiedGroupKFold(n_splits=args.folds,shuffle=True,random_state=42)
    predictions=np.full(len(y),-1,dtype=int); split_records=[]
    model_paths=[]
    for fold,(tr,te) in enumerate(folds.split(X,y,groups)):
        assert not set(groups[tr]) & set(groups[te])
        if set(y[tr]) != set(labels) or set(y[te]) != set(labels):
            raise ValueError('Every fold must contain all classes in training and test')
        model=RandomForestClassifier(n_estimators=200,max_depth=16,min_samples_leaf=2,
                                     class_weight='balanced',n_jobs=4,random_state=42)
        model.fit(X[tr],y[tr]); prediction=model.predict(X[te]); predictions[te]=prediction
        artifact=out/('fold_%d.joblib'%fold)
        joblib.dump({'model':model,'dataset':args.dataset,'feature_schema':'sequence_xyz_v1',
                     'train_groups':sorted(set(groups[tr])),'test_groups':sorted(set(groups[te]))},artifact)
        loaded=joblib.load(artifact)['model']; assert np.array_equal(loaded.predict(X[te]),prediction)
        model_paths.append({'path':str(artifact),'sha256':sha(artifact)})
        rec={'fold':fold,'train_groups':sorted(set(groups[tr])),'test_groups':sorted(set(groups[te])),
             'train_sequences':len(tr),'test_sequences':len(te),
             'accuracy':float(accuracy_score(y[te],prediction)),
             'macro_f1':float(f1_score(y[te],prediction,labels=labels,average='macro',zero_division=0))}
        split_records.append(rec); print('fold',fold,rec,flush=True)
    assert (predictions >= 0).all()
    with (out/'predictions.jsonl').open('x',encoding='utf-8') as f:
        for name,group,truth,pred in zip(names,groups,y,predictions):
            f.write(json.dumps({'sequence':name,'group':group,'truth':int(truth),'prediction':int(pred)})+'\n')
    summary={'task':args.dataset,'input':inputs,'samples':len(y),'features':X.shape[1],
             'class_counts':dict(Counter(map(str,y))),'groups':len(set(groups)),
             'folds':split_records,'accuracy':float(accuracy_score(y,predictions)),
             'balanced_accuracy':float(balanced_accuracy_score(y,predictions)),
             'macro_f1':float(f1_score(y,predictions,labels=labels,average='macro',zero_division=0)),
             'labels':labels,'confusion_matrix':confusion_matrix(y,predictions,labels=labels).tolist(),
             'python':platform.python_version(),'numpy':np.__version__,'sklearn':sklearn.__version__,
             'elapsed_s':time.monotonic()-started,'models':model_paths,'reload_prediction_parity':True,
             'seed':42,'trainer_sha256':sha(__file__),'IFW192S_fall_effectiveness':'UNKNOWN',
             'deployment':'NOT_DEPLOYED','frame_fall_onset':'UNKNOWN',
             'group_definition':'subject' if args.dataset=='mmfi' else 'parent animation directory',
             'original_motion_provenance':'UNKNOWN' if args.dataset=='synthetic' else 'subject-disjoint only; one environment',
             'limit':'Public dataset sequence baseline; no physical or board-runtime validity claim; synthetic motion variants may share underlying animations'}
    (out/'SUMMARY.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in summary.items() if k not in ('folds','confusion_matrix')},indent=2),flush=True)


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--dataset',choices=['mmfi','synthetic'],required=True)
    ap.add_argument('--archive',action='append',required=True)
    ap.add_argument('--output',required=True)
    ap.add_argument('--folds',type=int,default=5)
    run(ap.parse_args())
