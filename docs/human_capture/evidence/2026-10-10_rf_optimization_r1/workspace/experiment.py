"""Nested session CV; outer holdouts never select params/threshold/features.

All results are weak-label same-room exploration, never a production gate.
"""
import argparse
import json
import platform
import time
from pathlib import Path

import joblib
import numpy as np
import sklearn
from sklearn.ensemble import RandomForestClassifier, HistGradientBoostingClassifier
from sklearn.inspection import permutation_importance
from sklearn.metrics import confusion_matrix, precision_recall_curve
from sklearn.model_selection import GroupKFold
from threadpoolctl import threadpool_limits

from prepare import HERE, save, sha

GRID = [dict(max_depth=8, min_samples_leaf=5, max_features='sqrt', class_weight='balanced'),
        dict(max_depth=20, min_samples_leaf=1, max_features=.5, class_weight=None),
        dict(max_depth=None, min_samples_leaf=10, max_features=1., class_weight='balanced')]
HGRID = [dict(max_depth=3, min_samples_leaf=10, learning_rate=.05),
         dict(max_depth=6, min_samples_leaf=20, learning_rate=.1),
         dict(max_depth=None, min_samples_leaf=30, learning_rate=.05)]
THRESHOLDS = np.linspace(.05, .95, 19)
POSITION = [5,6,7,8,9,10,23,24,48,68]


def probability(model, X):
    if list(model.classes_) != [0, 1]:
        raise ValueError('both classes required')
    return model.predict_proba(X)[:, 1]


def metrics(y, p, threshold):
    tn, fp, fn, tp = confusion_matrix(y, p>=threshold, labels=[0,1]).ravel()
    return {'n':len(y), 'tn':int(tn), 'fp':int(fp), 'fn':int(fn), 'tp':int(tp),
            'precision':float(tp/(tp+fp)) if tp+fp else None,
            'recall':float(tp/(tp+fn)) if tp+fn else None,
            'specificity':float(tn/(tn+fp)) if tn+fp else None,
            'threshold':float(threshold)}


def choose_threshold(y, p):
    rows = [metrics(y,p,t) for t in THRESHOLDS]
    valid = [r for r in rows if r['precision'] is not None and r['precision']>=.95]
    if valid:
        return max(valid, key=lambda r: ((r['recall'] or 0), r['threshold']))['threshold'], True
    def f1(r):
        pr, re = r['precision'] or 0, r['recall'] or 0
        return 2*pr*re/max(pr+re,1e-9)
    return max(rows, key=f1)['threshold'], False


def present_class_score(y, pred):
    return float(np.mean([np.mean(pred[y==c]==c) for c in np.unique(y)]))


def importance_score(model, X, y):
    return present_class_score(y, model.predict(X))


def optional_mean(values):
    present = [v for v in values if v is not None]
    return float(np.mean(present)) if present else None


def grouped_splits(X, y, groups):
    if len(set(groups))<3:
        raise ValueError('at least 3 inner groups required')
    splits = list(GroupKFold(n_splits=3).split(X,y,groups))
    for tr, va in splits:
        if set(groups[tr]) & set(groups[va]):
            raise ValueError('group overlap')
        if len(np.unique(y[tr]))!=2:
            raise ValueError('single class training fold')
    return splits


def make(route, params):
    if route=='gbdt':
        return HistGradientBoostingClassifier(max_iter=100, early_stopping=False,
                                             random_state=17, **params)
    return RandomForestClassifier(n_estimators=100, n_jobs=1, random_state=17, **params)


def nested_fit(route, X, y, groups):
    splits = grouped_splits(X,y,groups)
    trials = []
    for params in (HGRID if route=='gbdt' else GRID):
        p = np.empty(len(y))
        scores = []
        for tr, va in splits:
            model=make(route,params).fit(X[tr],y[tr])
            p[va]=probability(model,X[va])
            # 单类验证仍生成OOF用于描述/阈值，但不参与选参均值。
            if len(np.unique(y[va])) == 2:
                scores.append(present_class_score(y[va],p[va]>=.5))
        if not scores:
            raise ValueError('no two-class inner validation fold for tuning')
        trials.append({'params':params,'score':float(np.mean(scores)), 'oof':p})
    best=max(trials,key=lambda r:r['score'])
    threshold, reached=choose_threshold(y,best['oof'])
    model=make(route,best['params']).fit(X,y)
    return model,threshold,{'params':best['params'], 'inner_score':best['score'],
        'inner_precision_target_reached':reached,
        'trials':[{'params':r['params'],'score':r['score']} for r in trials],
        'splits':[{'train_sessions':sorted(set(groups[a])), 'validation_sessions':sorted(set(groups[b])),
                   'validation_classes':np.unique(y[b]).tolist()}
                  for a,b in splits]}


def no_cross_group_duplicates(X, groups):
    keys={}
    for i,row in enumerate(X):
        key=tuple(np.round(row,6))
        keys.setdefault(key,set()).add(str(groups[i]))
    cross=sum(len(g)>1 for g in keys.values())
    if cross:
        raise ValueError(f'{cross} duplicated vectors span groups')
    return len(X)-len(keys)


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--out',required=True)
    ap.add_argument('--routes', nargs='+', default=None)
    args=ap.parse_args()
    out=Path(args.out)
    out.mkdir(exist_ok=False)
    data=HERE/'prepared/dataset.npz'
    with np.load(data,allow_pickle=False) as d:
        X,y,groups=d['X'],d['y'],d['sid']
    if X.shape[1]!=69 or not np.isfinite(X).all():
        raise ValueError('finite 69 columns required')
    duplicates=no_cross_group_duplicates(X,groups)
    with (HERE/'prepared/bindings.json').open(encoding='utf8') as f: bindings=json.load(f)
    with (HERE/'prepared/feature_audit.json').open(encoding='utf8') as f: names=json.load(f)['actual_names']
    routes={'baseline51':np.arange(51),'rf_v2':np.arange(51),'rf_v3':np.arange(69),
            'gbdt':np.arange(69),'v3_no_position':np.array([i for i in range(69) if i not in POSITION]),
            'v3_no_layers':np.array(list(range(51))+list(range(62,69))),
            'v3_no_pca':np.array(list(range(51))+list(range(51,62))+[68])}
    if args.routes is not None:
        routes={route:routes[route] for route in args.routes}
    result={'qualification':'BLOCKED: weak labels / no cold scene or person GT',
            'dataset_sha256':sha(data),'sklearn':sklearn.__version__,'numpy':np.__version__,
            'python':platform.python_version(),'platform':platform.platform(),
            'within_session_duplicates':duplicates,'outer_unit':'session',
            'duplicate_audit_scope':'rounded exact full-69 vector only; near duplicates and repeated person/scene not excluded',
            'routes':{}}
    all_predictions=[]
    for route,columns in routes.items():
        folds, importances=[],[]
        for hold in sorted(set(groups)):
            tr=np.flatnonzero(groups!=hold); te=np.flatnonzero(groups==hold)
            A=X[:,columns]
            if route=='baseline51':
                model=make('rf',dict(max_depth=20,min_samples_leaf=1,max_features='sqrt',class_weight=None)).fit(A[tr],y[tr])
                threshold,info=.55,{'params':'frozen cluster baseline, not original frame model'}
            else:
                model,threshold,info=nested_fit('gbdt' if route=='gbdt' else 'rf',A[tr],y[tr],groups[tr])
            if model.n_features_in_!=len(columns): raise ValueError('model dimension mismatch')
            p=probability(model,A[te])
            tick=time.perf_counter()
            for row in A[te[:min(32,len(te))]]:
                probability(model,row.reshape(1,-1))
            ms=(time.perf_counter()-tick)*1000/min(32,len(te))
            fold={'holdout':str(hold),'train_sessions':sorted(set(groups[tr])), 'n_features':len(columns),
                  'selection':info, 'metrics':metrics(y[te],p,threshold),'single_candidate_inference_mean_ms':ms,
                  'threshold_scan_reporting_only':[metrics(y[te],p,t) for t in THRESHOLDS]}
            pr,re,ts=precision_recall_curve(y[te],p)
            fold['pr_curve']={'precision':pr.tolist(),'recall':re.tolist(),'thresholds':ts.tolist()}
            fold['slices']={}
            distance=np.array([bindings[i]['horizontal_range'] for i in te])
            for label,mask in [('range_0_2',(distance<2)),('range_2_4',(distance>=2)&(distance<4)),
                               ('range_4_6',(distance>=4)&(distance<6)),('points_lt500',X[te,0]<500),
                               ('stand_weak',np.ones(len(te),bool))]:
                fold['slices'][label]=metrics(y[te][mask],p[mask],threshold) if mask.any() else {'status':'BLOCKED','n':0}
            for missing in ['bend','occluded','dynamic','unseen_person','unseen_furniture']:
                fold['slices'][missing]={'status':'BLOCKED','reason':'no verified label/coverage'}
            fold['slices']['stand_weak']['coverage_note']='entire weak standing scenario; no verified per-candidate posture split'
            if route in ('rf_v2','rf_v3','gbdt'):
                imp=permutation_importance(model,A[te],y[te],scoring=importance_score,
                                           n_repeats=2,random_state=17,n_jobs=1)
                importances.append(imp.importances_mean)
                fold['permutation_importance']={'names':[names[i] for i in columns],
                                                'mean':imp.importances_mean.tolist(),'std':imp.importances_std.tolist(),
                                                'note':'outer descriptive only; two repeats; correlated/time-dependent features limit interpretation'}
            for i,prob in zip(te,p):
                all_predictions.append(dict(bindings[i],route=route,p=float(prob),threshold=float(threshold),
                                            predicted=int(prob>=threshold),error=bool(int(prob>=threshold)!=y[i])))
            folds.append(fold)
            print(route,hold,fold['metrics'],flush=True)
        aggregate={k:sum(f['metrics'][k] for f in folds) for k in ['tn','fp','fn','tp','n']}
        tp,fp,fn=aggregate['tp'],aggregate['fp'],aggregate['fn']
        aggregate.update(precision=tp/max(tp+fp,1),recall=tp/max(tp+fn,1))
        result['routes'][route]={'folds':folds,'pooled_descriptive':aggregate,
                                'session_macro_recall':optional_mean([f['metrics']['recall'] for f in folds]),
                                'columns':columns.tolist()}
        # 模型只保存作研究复现；全量重拟合不赋予生产资格。
        if route in ('rf_v2','rf_v3','gbdt'):
            model,threshold,info=nested_fit('gbdt' if route=='gbdt' else 'rf',X[:,columns],y,groups)
            path=out/(route+'.joblib')
            joblib.dump(model,path)
            result['routes'][route]['research_artifact']={'path':path.name,'sha256':sha(path),'bytes':path.stat().st_size,
                   'threshold':threshold,'selection':info,'production_eligible':False}
    save(out/'results.json',result)
    save(out/'predictions_and_review_queue.json',all_predictions)
    lines=['# RF离线探索结果','', '资格 BLOCKED；六静态同房间、位置弱标签。所有指标仅是弱标签候选级描述。', '',
           '| route | dims | precision | recall | FP | FN |','|---|---|---|---|---|---|']
    for route,r in result['routes'].items():
        m=r['pooled_descriptive']
        lines.append(f"| {route} | {len(r['columns'])} | {m['precision']:.4f} | {m['recall']:.4f} | {m['fp']} | {m['fn']} |")
    lines += ['', '外层各折使用各自内层选定阈值；pool不是共同阈值成绩。未依据外层选冠军或部署阈值。',
              '真实困难样本补充、新人/新家具/跨场景及弯腰/遮挡/动态/4–6m验证 BLOCKED。R3/R4 NOT_RUN。']
    (out/'SUMMARY.md').write_text('\n'.join(lines)+'\n',encoding='utf8')


if __name__=='__main__':
    with threadpool_limits(limits=1):
        main()
