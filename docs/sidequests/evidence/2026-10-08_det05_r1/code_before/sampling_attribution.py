"""Separate local pillar sampling from surrounding-scene sampling, fixed representative frames."""
import json
from pathlib import Path
import sys

import numpy as np
import torch
from diagnose_low_scores import ROOT,UP,FG,PRE,SEED_FILE,SamplingProbe,load_cloud,run_probe,cylinder,height_summary
from cpu_pointpillars import load_model
from experiment import sha


def main(out):
    out.mkdir(exist_ok=False)
    model=load_model(UP/'epoch_160.pth',UP);torch.set_num_threads(4)
    base=model.pillar_layer.voxel_layer;probe=SamplingProbe(base);model.pillar_layer.voxel_layer=probe
    mf=json.loads((FG/'manifest.json').read_text(encoding='utf-8'));rm=json.loads((PRE/'manifest.json').read_text(encoding='utf-8'))
    truth={r['session']:r['xy_m'] for r in json.loads(SEED_FILE.read_text(encoding='utf-8'))['sessions']}
    rows=[]
    for s in mf['sessions']:
        sid=s['sid'];xy=truth[sid];fr=s['frames'][len(s['frames'])//2];raw=next(x for x in rm['sessions'] if x['sid']==sid)
        for variant in ['B_workspace','E_cleanup']:
            cloud,ids=load_cloud(s,fr,variant,raw);tag=sid+'_'+str(fr['index'])+'_'+variant
            row=run_probe(model,probe,cloud,ids,xy,out,tag+'_base');row['experiment']='base';rows.append(row)
            v,c,n,total=probe.last;allf={tuple(k):(v[j].clone(),n[j].clone()) for j,k in enumerate(c.numpy())}
            p=cloud.copy();p[:,2]-=np.float32(1.73)
            localkeys=set(map(tuple,np.floor((p[cylinder(cloud,xy),:3]-base.bounds[:3])/base.size).astype('i4')))
            for name in ['local_only','outside_only']:
                frozen={k:value for k,value in allf.items() if (k not in localkeys if name=='local_only' else k in localkeys)}
                row=run_probe(model,probe,cloud,ids,xy,out,tag+'_'+name,mode='z_rank32',freeze=frozen)
                av,ac,an,_=probe.last;actual={tuple(k):(av[j],an[j]) for j,k in enumerate(ac.numpy())}
                for k,(fv,fn) in frozen.items():
                    np.testing.assert_array_equal(actual[k][0].numpy(),fv.numpy());assert actual[k][1]==fn
                selected=np.concatenate([a[:int(num)] for a,num in zip(av.numpy(),an.numpy())]);selected[:,2]+=np.float32(1.73)
                row['actual_encoded_height_bands']=height_summary(selected,xy)
                row.update(experiment=name,frozen_pillars_equal=True,local_intersecting_pillars=len(localkeys))
                rows.append(row)
            for row in rows[-3:]:row.update(sid=sid,index=fr['index'],variant=variant)
    config=dict(script_sha256=sha(Path(__file__)),shared_script_sha256=sha(ROOT/'diagnose_low_scores.py'),checkpoint_sha256=sha(UP/'epoch_160.pth'),
                scope='Approximate cylinder-intersecting pillars, not body-only GT; baseline and frozen tensors equality asserted',rows=rows)
    (out/'result.json').write_text(json.dumps(config,indent=2),encoding='utf-8');print('DONE',len(rows))


if __name__=='__main__':main(Path(sys.argv[1]))
