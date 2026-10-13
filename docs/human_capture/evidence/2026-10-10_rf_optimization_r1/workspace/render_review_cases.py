"""为人工候选签核提供同一源点的XY/XZ视图；不生成真值。"""
import hashlib
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from prepare import HERE, ROOT, candidates, save


def main():
    with (HERE/'run01/predictions_and_review_queue.json').open(encoding='utf8') as f: rows=json.load(f)
    with (ROOT/'pc_apps/human_replay/bg_envelope.json').open(encoding='utf8') as f: bg=json.load(f)
    chosen=[]
    for route,label in [('rf_v3','person'),('rf_v3','furniture'),('gbdt','furniture')]:
        subset=[r for r in rows if r['route']==route and r['error'] and r['weak_label']==label]
        if subset:
            chosen.append(subset[0])
            if len(subset)>1: chosen.append(subset[len(subset)//2])
    fig,axes=plt.subplots(len(chosen),2,figsize=(9,3*len(chosen)),layout='constrained')
    queue=[]
    for pair,row in zip(axes,chosen):
        folder=ROOT/'captures/remote'/row['sid']
        with (folder/'meta.json').open(encoding='utf8') as f: meta=json.load(f)
        frame=meta['frames'][row['frame_index']]
        raw=np.memmap(folder/'points.bin',dtype=np.uint8,mode='r').reshape(-1,28).view('<f4').reshape(-1,7)
        a=frame['offset_points']; b=a+frame['count_points']
        pts,ids=candidates(raw[a:b],bg)[row['rank']]
        assert hashlib.sha256(ids.astype('<i8').tobytes()).hexdigest()==row['source_point_indices_sha256']
        for ax,other,label in [(pair[0],1,'Y'),(pair[1],2,'Z')]:
            ax.scatter(pts[:,0],pts[:,other],c=pts[:,2],s=5,cmap='viridis',vmin=.1,vmax=2.3)
            ax.set(xlabel='X (m)',ylabel=label+' (m)')
            ax.set_aspect('equal',adjustable='datalim')
            ax.grid(alpha=.2)
        pair[0].set_title(f"{row['sid'][-6:]} frame_index={row['frame_index']} seq={row['frame_seq']} rank={row['rank']} n={len(pts)}",fontsize=9)
        pair[1].set_title(f"{row['route']} p={row['p']:.3f} threshold={row['threshold']:.2f}; weak={row['weak_label']}",fontsize=9)
        queue.append(dict(row,human_candidate_label=None,human_quality_label=None,
                          allowed_quality_labels=['complete','fragment','mixed_furniture','uncertain'],
                          signature=None,view_note='same candidate XY/XZ views; no full-frame context, review whole source before assigning'))
        del raw
    fig.suptitle('Candidate review queue | weak labels only; no human ground truth assigned',fontsize=11)
    path=HERE/'run01/review_cases.png'
    if path.exists(): raise FileExistsError(path)
    fig.savefig(path,dpi=150)
    plt.close(fig)
    save(HERE/'run01/manual_review_cases.json',queue)


if __name__=='__main__': main()
