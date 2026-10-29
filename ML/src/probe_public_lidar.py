"""Read-only IFW192S replay of public models: predictions, never invented GT."""
import argparse
import json
from pathlib import Path
import time

import joblib
import numpy as np
from train_public_lidar import sequence_feature, sha


def run(model_dir, targets, output, final=False):
    paths=[model_dir/'final_model.joblib'] if final else sorted(model_dir.glob('fold_*.joblib'))
    models=[joblib.load(p)['model'] for p in paths]
    if len(models) != (1 if final else 5):
        raise ValueError('Unexpected model count')
    with np.load(model_dir/'features.npz',allow_pickle=False) as cache:
        low,high=cache['X'].min(0),cache['X'].max(0)
    with np.load(targets,allow_pickle=False) as archive:
        names=sorted(archive.files,key=lambda n:int(n[1:]))
        segments=[]
        for name in names:
            if not segments or int(name[1:]) != int(segments[-1][-1][1:])+1:
                segments.append([])
            segments[-1].append(name)
        rows=[]
        for segment in segments:
            for begin in range(0,len(segment)-59,15):
                selected=segment[begin:begin+60]
                start=time.perf_counter()
                feature=sequence_feature([archive[n] for n in selected])
                proba=np.mean([m.predict_proba(feature[None,:])[0] for m in models],axis=0)
                rows.append({'first_frame':selected[0],'last_frame':selected[-1],
                             'class_probabilities':{str(c):float(p) for c,p in zip(models[0].classes_,proba)},
                             'prediction':int(models[0].classes_[np.argmax(proba)]),
                             'feature_outside_source_range_fraction':float(((feature<low)|(feature>high)).mean()),
                             'feature_and_models_ms':(time.perf_counter()-start)*1000})
    result={'input':str(targets),'input_sha256':sha(targets),'target_frames':len(names),
            'contiguous_segments':[len(s) for s in segments],'window_frames':60,'stride_frames':15,
            'windows':rows,'truth':'UNKNOWN','accuracy':'UNKNOWN','fall_recall':'UNKNOWN',
            'scope':'Archived algorithm-selected targets; not person GT; no source-to-target sensor-axis alignment claimed',
            'timing_scope':'PC offline, presegmented targets; excludes LiDAR decode/detection/tracking; not board real-time performance',
            'models':[{'path':str(p),'sha256':sha(p)} for p in paths],
            'probe_script_sha256':sha(__file__),'deployment':'NOT_DEPLOYED'}
    if not rows:
        raise ValueError('No contiguous segment long enough for replay')
    output.write_text(json.dumps(result,indent=2),encoding='utf-8')
    print('replayed',len(names),'target frames,',len(rows),'windows; GT and effectiveness UNKNOWN')


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--model-dir',type=Path,required=True)
    ap.add_argument('--targets',type=Path,required=True)
    ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--final',action='store_true')
    args=ap.parse_args()
    run(args.model_dir,args.targets,args.output,args.final)
