"""追加诊断：相同输入删除显式XY位置/距离特征，禁止用于选最终模型。"""
import numpy as np
from threadpoolctl import threadpool_limits
from prepare import HERE, save
from experiment import nested_fit, probability, metrics


def main():
    out=HERE/'sensitivity01'
    out.mkdir(exist_ok=False)
    with np.load(HERE/'prepared/dataset.npz',allow_pickle=False) as d:
        X,y,s=d['X'],d['y'],d['sid']
    # 原no_position仍保留径向std(41)，此处也移除，仍不等于所有位置捷径消失。
    removed=[5,6,7,8,9,10,23,24,41,48,68]
    columns=[i for i in range(69) if i not in removed]
    report={'diagnostic_only':True,'removed':removed,'columns':columns,'n_features':len(columns),
            'note':'post-run position sensitivity; not preregistered model selection evidence; residual count/geometry may proxy range',
            'routes':{}}
    for route in ['rf','gbdt']:
        folds=[]
        for hold in sorted(set(s)):
            tr=s!=hold; te=~tr
            model,t,selection=nested_fit(route,X[tr][:,columns],y[tr],s[tr])
            m=metrics(y[te],probability(model,X[te][:,columns]),t)
            folds.append({'holdout':str(hold),'metrics':m,'selection':selection})
            print(route,hold,m,flush=True)
        report['routes'][route]={'folds':folds, 'totals':{k:sum(f['metrics'][k] for f in folds) for k in ['tp','fp','tn','fn']}}
    save(out/'results.json',report)


if __name__=='__main__':
    with threadpool_limits(limits=1): main()
