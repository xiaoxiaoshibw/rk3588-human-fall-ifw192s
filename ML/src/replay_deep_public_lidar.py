"""Rebuild held-out sequences from raw ZIP members and compare frozen deep predictions."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile
import numpy as np
import torch
from train_deep_lidar import CausalPointNet,POINTS,batch,predict
from train_public_lidar import ordered_names,sha


def run(evidence,models):
    torch.set_num_threads(4)
    splits=json.loads((evidence/'mmfi_deep/SPLITS.json').read_text(encoding='utf-8'))
    prior=[json.loads(line) for line in (evidence/'mmfi_deep/E01_deep30_windows.jsonl').read_text(encoding='utf-8').splitlines()]
    archive=Path('data/downloads/public_lidar_20261022/E01_lidar_gt.zip');checks=[]
    with zipfile.ZipFile(archive) as z:
        for split in splits:
            model=CausalPointNet();checkpoint=models/('fold_%d.pt'%split['fold'])
            assert sha(checkpoint)==split['checkpoint_sha256']
            model.load_state_dict(torch.load(checkpoint,weights_only=True,map_location='cpu'))
            seq='E01/'+split['test_groups'][0]+'/A12'
            assert seq.split('/')[1] not in split['train_groups']
            frames=[];hashes=[]
            for name in ordered_names([n for n in z.namelist() if n.startswith(seq+'/lidar/') and n.endswith('.bin')],'mmfi'):
                raw=z.read(name);hashes.append(hashlib.sha256(raw).hexdigest())
                p=np.frombuffer(raw,dtype='<f8').reshape(-1,3)
                seed=int.from_bytes(hashlib.sha256(name.encode()).digest()[:8],'little')
                idx=np.random.default_rng(seed).choice(len(p),POINTS,replace=len(p)<POINTS)
                frames.append(p[idx].astype(np.float32))
            rows=[r for r in prior if r['sequence']==seq]
            arrays={seq:torch.from_numpy(np.asarray(frames))}
            probabilities=predict(model,arrays,rows,np.arange(len(rows)))
            expected=np.asarray([r['probabilities'] for r in rows])
            np.testing.assert_allclose(probabilities,expected,atol=1e-6,rtol=0)
            np.testing.assert_array_equal(probabilities.argmax(1)+1,[r['prediction'] for r in rows])
            checks.append({'sequence':seq,'raw_frames':len(frames),'windows':len(rows),'checkpoint_sha256':sha(checkpoint),
                           'ordered_source_member_sha256':hashes,'max_probability_error':float(np.abs(expected-probabilities).max()),
                           'classes_equal':True})
    (evidence/'RAW_DEEP_REPLAY.json').write_text(json.dumps({'input':str(archive),'archive_sha256':sha(archive),'checks':checks,
        'scope':'raw MM-Fi XYZ to deterministic sampled point windows to frozen held-out model; not IFW192S chain or board runtime',
        'deployment':'NOT_DEPLOYED'},indent=2),encoding='utf-8')
    print('raw deep replay',sum(r['raw_frames'] for r in checks),'frames',sum(r['windows'] for r in checks),'windows',flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--evidence',type=Path,required=True);p.add_argument('--models',type=Path,required=True)
    a=p.parse_args();run(a.evidence,a.models)
