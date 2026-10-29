"""Audit numeric MoMo point sequences with a restricted NumPy-only pickle reader."""
from collections import Counter
import argparse
import codecs
import hashlib
import io
import json
from pathlib import Path
import pickle
import re
import tarfile
import numpy as np


class NumericUnpickler(pickle.Unpickler):
    def find_class(self,module,name):
        allowed={('numpy','ndarray'):np.ndarray,('numpy','dtype'):np.dtype,
                 ('numpy.core.multiarray','_reconstruct'):np.core.multiarray._reconstruct,
                 ('numpy._core.multiarray','_reconstruct'):np.core.multiarray._reconstruct,
                 ('numpy.core.multiarray','scalar'):np.core.multiarray.scalar,
                 ('numpy._core.multiarray','scalar'):np.core.multiarray.scalar,
                 ('numpy.core.numeric','_frombuffer'):np.core.numeric._frombuffer,
                 ('numpy._core.numeric','_frombuffer'):np.core.numeric._frombuffer,
                 ('_codecs','encode'):codecs.encode}
        if (module,name) not in allowed:raise pickle.UnpicklingError('Unsupported global: %s.%s'%(module,name))
        return allowed[module,name]


def decode(raw):
    value=NumericUnpickler(io.BytesIO(raw)).load()
    if not isinstance(value,(list,tuple,np.ndarray)) or len(value)==0:raise ValueError('Expected nonempty point sequence')
    return value


def run(archive,out,expected):
    if not archive.name.endswith('.tar.gz'):
        raise ValueError('Use dedicated MoMo point-cloud tar.gz; mixed momo.zip workspace is rejected')
    out.mkdir(parents=True,exist_ok=False)
    with archive.open('rb') as f:actual=hashlib.file_digest(f,'sha256').hexdigest()
    if actual!=expected:raise ValueError('Archive SHA mismatch')
    records=[];others=[];people=Counter();actions=Counter();scenes=Counter();cache={}
    with tarfile.open(archive,'r|gz') as z:
        for m in z:
            if not m.isfile():continue
            name=m.name
            match=re.fullmatch(r'P(\d{3})S(\d{3})A(\d{3})R(\d{3})\.pkl',Path(name).name)
            handle=z.extractfile(m)
            if handle is None:raise ValueError('Missing tar payload')
            with handle:raw=handle.read()
            h=hashlib.sha256(raw).hexdigest()
            if not match or 'momo_spike_pc' not in Path(name).parts:
                others.append({'path':name,'bytes':len(raw),'sha256':h});continue
            person,scene,action,take=map(int,match.groups())
            frames=decode(raw);counts=[];bad=[];sampled=[];columns=Counter()
            for fi,frame in enumerate(frames):
                p=np.asarray(frame)
                if p.ndim!=2 or p.shape[1]!=3 or not np.isfinite(p).all():
                    bad.append({'frame':fi,'shape':list(p.shape),'reason':'invalid XYZ'});continue
                counts.append(len(p));columns[p.shape[1]]+=1
                if len(records)<8 and len(p):
                    idx=np.linspace(0,len(p)-1,64,dtype=int);sampled.append(p[idx].astype(np.float32))
            rec={'path':name,'subject':person,'scene':scene,'action_id':action,'take':take,'sha256':h,
                 'tar_header_checksum':m.chksum,'bytes':len(raw),'frames':len(frames),'point_min':min(counts) if counts else 0,
                 'point_max':max(counts) if counts else 0,'point_sum':sum(counts),'empty_frames':sum(c==0 for c in counts),
                 'invalid_frames':bad,'candidate_30frame_eligible':len(frames)>=30 and not bad and counts and min(counts)>=10}
            records.append(rec);people[person]+=1;actions[action]+=1;scenes[scene]+=1
            if len(sampled)==len(frames):cache[match.group(0)]=np.asarray(sampled)
            if len(records)%2000==0:print('MoMo sequences audited',len(records),flush=True)
    identities=[re.search(r'P\d{3}S\d{3}A\d{3}R\d{3}',r['path']).group(0) for r in records]
    summary={'archive':str(archive),'archive_sha256':actual,'author_sha_match':True,
             'integrity':'full author SHA256 and tar header checks; not a ZIP/member-CRC claim',
             'point_sequence_files':len(records),'unique_recording_ids':len(set(identities)),
             'subjects':dict(sorted(people.items())),'action_ids':dict(sorted(actions.items())),'scenes':dict(sorted(scenes.items())),
             'frames':sum(r['frames'] for r in records),'points':sum(r['point_sum'] for r in records),
             'empty_frames':sum(r['empty_frames'] for r in records),'invalid_frames':sum(len(r['invalid_frames']) for r in records),
             'eligible_30frame_sequences':sum(bool(r['candidate_30frame_eligible']) for r in records),
             'nonpoint_members':others,'source_time_and_action_intervals':'UNKNOWN; filename sequence labels only',
             'loader':'restricted NumPy array pickle, no arbitrary globals','cross_dataset_ID_mapping':'NOT_ASSUMED',
             'label_names_and_sensor_contract':'must verify author metadata; numeric action IDs not silently mapped to MM-Fi',
             'records':records}
    (out/'AUDIT.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    np.savez_compressed(out/'numeric_samples64.npz',**cache)
    print(json.dumps({k:v for k,v in summary.items() if k not in ['records','nonpoint_members','subjects','action_ids','scenes']}),flush=True)
    print('subjects',len(people),'actions',len(actions),'scenes',len(scenes),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--archive',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--sha256',required=True);a=p.parse_args();run(a.archive,a.output,a.sha256)
