"""Build small, source-bound preview data; no fitting or source-data writes."""
import argparse
import base64
import hashlib
import json
from pathlib import Path
import subprocess
import zipfile
import numpy as np

ROOT=Path(__file__).resolve().parents[2]
PRIOR=ROOT/'docs/evidence/2026-10-22_causal_lidar'
SAMPLES=['E01/S01/A12','E01/S02/A12','E02/S11/A12','E02/S15/A12']
ARCHIVES={'E01':ROOT/'data/downloads/public_lidar_20261022/E01_lidar_gt.zip',
          'E02':ROOT/'data/downloads/causal_lidar_20261022/E02_lidar_gt.zip'}


def digest(raw):return hashlib.sha256(raw).hexdigest()


def build(out):
    out.mkdir(parents=True,exist_ok=False)
    snapshots={str(p):digest(p.read_bytes()) for p in [ROOT/'docs/PROJECT_STATE.md',ROOT/'docs/PROGRESS.md',
               Path(__file__)]}
    baseline={'branch':subprocess.check_output(['git','branch','--show-current'],cwd=ROOT,text=True).strip(),
              'head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
              'scope':'preview-only changed-file snapshot; prior complete visible-tree baseline retained',
              'files':snapshots}
    (out/'BASELINE.json').write_text(json.dumps(baseline,indent=2),encoding='utf-8')
    samples=[];audit=[]
    for env in ['E01','E02']:
        stem='E01_w30_window_train' if env=='E01' else 'E02_w30'
        seq_path=PRIOR/(stem+'_sequences.json');window_path=PRIOR/(stem+'_windows.jsonl')
        seqs={r['sequence']:r for r in json.loads(seq_path.read_text(encoding='utf-8'))}
        windows={seq:[] for seq in SAMPLES if seq.startswith(env)}
        for line in window_path.read_text(encoding='utf-8').splitlines():
            row=json.loads(line)
            if row['sequence'] in windows:
                windows[row['sequence']].append({k:row[k] for k in ['begin_index','end_index_exclusive','truth','prediction','probabilities']})
        source=json.loads((PRIOR/(env+'_cache/INPUT.json')).read_text(encoding='utf-8'))
        expected={r['sequence']:r for r in source['sequences']}
        with zipfile.ZipFile(ARCHIVES[env]) as z:
            for seq in windows:
                rec=seqs[seq];members={m['path']:m['sha256'] for m in expected[seq]['members']}
                names=sorted(members,key=lambda n:int(n.rsplit('frame',1)[1][:-4]))
                indexes=sorted(set(range(0,len(names),10))|{len(names)-1})
                frames=[];checks=[];bounds=[]
                for index in indexes:
                    raw=z.read(names[index]);actual=digest(raw)
                    assert actual==members[names[index]]
                    p=np.frombuffer(raw,dtype='<f8').reshape(-1,3)
                    assert np.isfinite(p).all()
                    chosen=np.linspace(0,len(p)-1,min(600,len(p)),dtype=int)
                    q=np.rint(p[chosen]*1000)
                    if np.abs(q).max()>32767:raise ValueError('Coordinates exceed int16 preview range')
                    packed=q.astype('<i2')
                    np.testing.assert_allclose(packed.astype(float)/1000,p[chosen],atol=.000501,rtol=0)
                    frames.append({'index':index,'source_frame':int(names[index].rsplit('frame',1)[1][:-4]),
                                   'original_points':len(p),'visible_points':len(chosen),
                                   'xyz':base64.b64encode(packed.tobytes()).decode('ascii')})
                    bounds.append([p.min(0).tolist(),p.max(0).tolist()])
                    checks.append({'index':index,'member':names[index],'sha256':actual,'point_rows':chosen.tolist()})
                lower=np.min(np.asarray(bounds)[:,0],axis=0);upper=np.max(np.asarray(bounds)[:,1],axis=0)
                item={'sequence':seq,'truth':rec['truth'],'aggregate_prediction':rec['prediction'],
                      'aggregate_probabilities':rec['probabilities'],'frames_total':len(names),
                      'frames':frames,'windows':windows[seq],'lower':lower.tolist(),'upper':upper.tolist(),
                      'validation':'E01 held-out subject' if env=='E01' else 'E01 frozen model to independent E02'}
                samples.append(item)
                audit.append({'sequence':seq,'archive':str(ARCHIVES[env]),'archive_sha256':source['sha256'],
                              'sequence_record_sha256':digest(seq_path.read_bytes()),
                              'window_ledger_sha256':digest(window_path.read_bytes()),'frames':checks,
                              'aggregate_prediction':rec['prediction'],'truth':rec['truth']})
    payload={'samples':samples,'quantization_scale':.001,'sample_every_frames':10,
             'max_visible_points':600,'playback_sampled_frames_per_second':5,
             'selection':'fixed A12 squat, first lexicographic correct/wrong sequence in each environment; illustrative, not prevalence',
             'label_kind':'inherited_sequence_action; not verified frame action GT'}
    text=json.dumps(payload,separators=(',',':'),ensure_ascii=False)
    (out/'preview_data.json').write_text(text,encoding='utf-8')
    (out/'SOURCE_AUDIT.json').write_text(json.dumps(audit,indent=2),encoding='utf-8')
    assert len(samples)==4
    assert [s['aggregate_prediction']==s['truth'] for s in samples]==[True,False,True,False]
    assert all(len(s['frames'])==31 and len(s['windows'])==27 for s in samples)
    print('verified',sum(len(s['frames']) for s in samples),'raw frames; 108 frozen window predictions; payload bytes',len(text.encode()),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();build(a.output)
