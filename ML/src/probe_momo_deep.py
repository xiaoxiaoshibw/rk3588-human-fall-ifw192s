"""Exercise the variable-length path on the real 20-frame MoMo sample. No cross-dataset semantics."""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
import torch
from audit_momo import decode
from train_deep_lidar import CausalPointNet,batch,last_step,predict


def sample(frames,points):
    rows=[]
    for i,frame in enumerate(frames):
        p=np.asarray(frame,dtype=np.float64)
        if p.ndim!=2 or p.shape[1]!=3 or not np.isfinite(p).all():raise ValueError('invalid MoMo frame')
        seed=int.from_bytes(hashlib.sha256(('momo-frame/%d'%i).encode()).digest()[:8],'little')
        idx=np.random.default_rng(seed).choice(len(p),points,replace=len(p)<points)
        rows.append(p[idx].astype(np.float32))
    return np.asarray(rows)


def run(pkl,models,out,points=256):
    frames=decode(pkl.read_bytes());x=sample(frames,points)
    arrays={'momo':torch.from_numpy(x)}
    row={'sequence':'momo','subject':'momo','truth':1,'begin_index':0,'end_index_exclusive':len(x)}
    path=models/'fold_0.pt'
    model=CausalPointNet();model.load_state_dict(torch.load(path,map_location='cpu',weights_only=True));model.eval()
    p=predict(model,arrays,[row],[0])[0]
    # Same sample padded beside a 30-frame item must keep the 20-frame prediction unchanged.
    other={'sequence':'pad','subject':'pad','truth':1,'begin_index':0,'end_index_exclusive':30}
    arrays['pad']=torch.zeros(30,points,3)
    with torch.no_grad():
        xpad,_,lengths=batch(arrays,[row,other],[0,1])
        padded=last_step(model(xpad),lengths)[0].softmax(-1).numpy()
        single=model(arrays['momo'][None])[0,-1].softmax(-1).numpy()
    out.mkdir(parents=True,exist_ok=True)
    record={'source':str(pkl),'source_sha256':hashlib.sha256(pkl.read_bytes()).hexdigest(),
            'checkpoint':str(path),'frames':len(x),'points_per_frame':points,
            'short_sequence_windows':1,'padding_matches_single':bool(np.allclose(padded,single,atol=1e-6)),
            'max_probability_difference':float(np.abs(padded-single).max()),
            'top5_numeric_action_ids':[{'id':int(i)+1,'probability':float(v)} for i,v in
                sorted(enumerate(p),key=lambda kv:-kv[1])[:5]],
            'semantics':'UNKNOWN; MM-Fi 27-way head applied to MoMo XYZ only to test the variable-length plumbing',
            'cross_dataset_label_mapping':'NOT_ASSUMED','accuracy':'NOT_CLAIMED'}
    (out/'MOMO_VARIABLE_LENGTH.json').write_text(json.dumps(record,indent=2,ensure_ascii=False),encoding='utf-8')
    print(json.dumps({k:v for k,v in record.items() if k!='top5_numeric_action_ids'}),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--pkl',type=Path,required=True);p.add_argument('--models',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--points',type=int,default=256);a=p.parse_args()
    run(a.pkl,a.models,a.output,a.points)