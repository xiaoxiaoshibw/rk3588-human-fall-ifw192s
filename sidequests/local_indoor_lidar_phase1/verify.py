"""Full row/member check plus independent recompute; no copied clouds or GT."""
import argparse
import collections
import hashlib
import time
import numpy as np
from scipy.spatial import cKDTree
from prototype import E, PRIOR, read, sha, write, mapped, transform, paths, run_frame, check_hashes, threadpool_limits

def main(output):
    m=read(E/'RUN_MANIFEST.json'); target=E/'baseline_r1'; index=read(target/'INDEX.json')
    check_hashes(m['assets'])
    check_hashes({str(__import__('pathlib').Path(__file__).parent/'prototype.py'):m['code'][str(__import__('pathlib').Path(__file__).parent/'prototype.py')]})
    check_hashes(read(E/'DELIVERY_V4.json')['source_sha256'])
    with np.load(m['background']['path']) as d: tree=cKDTree(d['xyz'])
    totals=np.zeros(6,dtype='i8'); checked=0; parity=[]; recomputed=[]; signature=[]
    queue=read(E/'REVIEW_QUEUE.json')['tasks']; samples={(r['sid'],r['fi']) for r in queue}
    with threadpool_limits(limits=4):
        for sid,source in m['sources'].items():
            meta,raw,_=mapped(sid,source['sha256']);state=dict(last=None,seen=None,t=None)
            reg=None if sid==m['empty_sid'] else read(m['cfg']['background_experiment']+'/'+sid+'_registration.json')
            for fi in source['available']:
                row=read(target/sid/(str(fi)+'.json'));f=meta['frames'][fi]
                for ext in ['json','npz']:
                    rel=sid+'/'+str(fi)+'.'+ext
                    if sha(target/rel)!=index['artifacts'][rel]:raise ValueError('artifact drift '+rel)
                with np.load(target/sid/(str(fi)+'.npz')) as d:code,labels=d['terminal'],d['cluster']
                assert len(code)==len(labels)==f['count_points']
                assert np.array_equal(np.bincount(code,minlength=6),row['terminal_counts'])
                assert np.array_equal(labels>=0,code>=4)
                q=raw[f['offset_points']:f['offset_points']+f['count_points']];p=transform(q,reg)
                for c in row['candidates']:
                    ids=np.flatnonzero(labels==c['id'])
                    assert len(ids)==c['count'] and hashlib.sha256(ids.astype('<u4').tobytes()).hexdigest()==c['member_sha256']
                    np.testing.assert_allclose(p[ids].min(0),c['min'],atol=1e-12)
                    np.testing.assert_allclose(p[ids].max(0),c['max'],atol=1e-12)
                with np.load(PRIOR/'primary/runs/R1_legacy'/sid/(f'{fi:04d}.npz')) as prior:
                    parity.append(bool(np.array_equal(np.flatnonzero(prior['selected']),np.flatnonzero(code==5))))
                # Recompute causal prefix through last sampled frame; full chain, not isolated chosen frames.
                if sid==m['empty_sid'] or fi<=max(t['fi'] for t in queue if t['sid']==sid):
                    newcode,newlabels,candidates,_,_=run_frame(q,p,tree,m['cfg'],m['tau'],state,f['stamp_sec']+f['stamp_nanosec']*1e-9)
                    assert np.array_equal(newcode,code) and np.array_equal(newlabels,labels)
                    recomputed.append(sid+'/'+str(fi))
                totals+=np.bincount(code,minlength=6);checked+=1
            print('VERIFIED',sid,flush=True)
    baseline=read(E/'BASELINE_BEFORE.json');differences=[]
    for p,digest in baseline['assets'].items():
        if sha(p)!=digest:differences.append(p)
    write(output,dict(frames=checked,terminal_counts=totals.tolist(),candidate_members_and_bounds='ALL_CHECKED',
        independently_recomputed=len(recomputed),prior_R1_selected_parity=sum(parity),prior_R1_denominator=len(parity),
        frozen_differences=differences,training=0,human_reviews=len(list((E/'human_reviews').glob('*.json'))),
        semantic='BLOCKED',status='PASS' if not differences and all(parity) else 'FAIL'))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('output',type=lambda s:__import__('pathlib').Path(s));main(p.parse_args().output)
