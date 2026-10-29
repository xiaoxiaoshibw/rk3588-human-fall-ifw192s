"""Descriptive breakdowns only; no model fitting or test-driven selection."""
import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import numpy as np
from causal_public_lidar import scores
from train_public_lidar import sha


def read(path):return json.loads(path.read_text(encoding='utf-8'))


def run(evidence, models):
    source=read(evidence/'E01_cache/INPUT.json');target=read(evidence/'E02_cache/INPUT.json')
    hashes=defaultdict(list)
    for env,doc in [('E01',source),('E02',target)]:
        for seq in doc['sequences']:
            digest=hashlib.sha256(''.join(m['sha256'] for m in seq['members']).encode()).hexdigest()
            hashes[digest].append(seq['sequence'])
    duplicates=[members for members in hashes.values() if len(members)>1]
    if any(any(s.startswith('E01/') for s in members) and any(s.startswith('E02/') for s in members) for members in duplicates):
        raise ValueError('Exact complete sequence duplicated across environments')
    cuts=np.percentile([r['point_mean'] for r in source['sequences']],[25,50,75])
    audit={'exact_sequence_duplicates':duplicates,'point_bins_from_E01_only':cuts.tolist(),
           'frame_timestamp_and_action_interval':'UNKNOWN; contiguous numbered LiDAR frames aligned by count to joints only',
           'coordinate_contract':'author loader reads float64 XYZ; no verified cross-sensor axis/unit or pose-GT reference transformation inferred',
           'pose_GT_use':'finite 297x17x3 alignment audit only; never used for prediction',
           'environment_people':{},'breakdowns':{}}
    for env,doc in [('E01',source),('E02',target)]:
        audit['environment_people'][env]=sorted(set(r['subject'] for r in doc['sequences']))
        if env=='E01':summaries=read(evidence/'E01_COMPARISON.json')
        else:summaries=read(evidence/'E02_RESULTS.json')['results']
        for window in [10,20,30,60]:
            for kind in (['full_train','window_train'] if env=='E01' else ['window_train']):
                stem='%s_w%d_%s'%(env,window,kind) if env=='E01' else '%s_w%d'%(env,window)
                rows=read(evidence/(stem+'_sequences.json'))
                p=np.asarray([r['probabilities'] for r in rows]);y=np.asarray([r['truth'] for r in rows])
                cm=np.asarray((summaries[str(window)][kind] if env=='E01' else summaries[str(window)])['sequence_mean_probability']['confusion_matrix'])
                per_class={str(i+1):{'truth_sequences':int(cm[i].sum()),'predicted_sequences':int(cm[:,i].sum()),
                    'recall':float(cm[i,i]/cm[i].sum()) if cm[i].sum() else None,
                    'precision':float(cm[i,i]/cm[:,i].sum()) if cm[:,i].sum() else None} for i in range(27)}
                point_counts={r['sequence']:r['point_mean'] for r in doc['sequences']}
                bins=np.digitize([point_counts[r['sequence']] for r in rows],cuts)
                audit['breakdowns'][stem]={'per_class':per_class,'by_mean_point_count':{
                    str(b):scores(y[bins==b],p[bins==b]) for b in range(4) if np.any(bins==b)},
                    'occlusion_truth':'UNKNOWN; point counts are observable proxies, not measured occlusion'}
    # Primary first-window comparison is distinct from retrospective sequence aggregation.
    first={}
    for env in ['E01','E02']:
        for window in [10,20,30,60]:
            for kind in (['full_train','window_train'] if env=='E01' else ['window_train']):
                stem='%s_w%d_%s'%(env,window,kind) if env=='E01' else '%s_w%d'%(env,window)
                rows=[json.loads(line) for line in (evidence/(stem+'_windows.jsonl')).read_text(encoding='utf-8').splitlines()]
                selected=[r for r in rows if r['begin_index']==0]
                first[stem]=scores([r['truth'] for r in selected],np.asarray([r['probabilities'] for r in selected]))
    audit['first_window_scores']=first
    audit['source_sha256']={env:doc['sha256'] for env,doc in [('E01',source),('E02',target)]}
    audit['models']={p.name:sha(p) for p in models.glob('*') if p.is_file()}
    with (evidence/'DESCRIPTIVE_ANALYSIS.json').open('x',encoding='utf-8') as f:json.dump(audit,f,indent=2)
    print('descriptive comparisons',len(audit['breakdowns']),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--evidence',type=Path,required=True);p.add_argument('--models',type=Path,required=True)
    a=p.parse_args();run(a.evidence,a.models)
