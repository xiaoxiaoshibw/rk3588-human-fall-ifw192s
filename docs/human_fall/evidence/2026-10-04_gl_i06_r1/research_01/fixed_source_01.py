"""RNG stability on exactly fixed source, separate from noise-realization sweep."""
import itertools
import json
import numpy as np
from r0_01 import HERE, SEEDS, scene, settings, digest, gd, g, write_new
from r1_experiment_01 import compact_new, brief
from refinement_04 import run_variant


def main():
    results=[];stability=[]
    for kind in ('clean','low_noise','high_noise','wall'):
        cloud,rows,regions=scene(kind,7)
        for seed in SEEDS:
            s=settings(seed);up=np.array([0.,0.,1.]);height=(.5,2.)
            sample,fit,it=gd.replay_sequence(cloud,rows,up,height,s);seq=list(it)
            packet=dict(source_sha=digest(cloud),fit_sha=digest(rows),sampled_sha=digest(sample),raw_sha=digest(seq),settings_sha=digest(s),seed=seed)
            variants=[]
            for k in (1,2,3):
                v=run_variant(cloud,sample,fit,seq,up,height,s,k)
                file='fixed_source_%s_seed%d_K%d_01.json'%(kind,seed,k)
                compact_new(HERE/file,dict(packet=packet,variant=v))
                variants.append(dict(brief(v,cloud,regions,s,True),artifact=file))
            results.append(dict(kind=kind,seed=seed,packet=packet,variants=variants))
            print(kind,seed,flush=True)
        for k in (1,2,3):
            group=[r for r in results if r['kind']==kind]
            assert len({r['packet']['source_sha'] for r in group})==1
            planes=[r['variants'][k-1]['best_plane'] for r in group]
            stability.append(dict(kind=kind,k=k,scope='same source+FIT+validation; only RANSAC seed changes',
                             max_normal_pair_deg=max(g._angle_deg(a['normal'],b['normal']) for a,b in itertools.combinations(planes,2)),
                             max_offset_pair_m=max(abs(a['offset_m']-b['offset_m']) for a,b in itertools.combinations(planes,2)),
                             offset_std_m=float(np.std([p['offset_m'] for p in planes])),
                             normal_components_std=np.std([p['normal'] for p in planes],axis=0).tolist()))
    write_new(HERE/'fixed_source_summary_01.json',dict(results=results,stability=stability,physical_verified=False))


if __name__=='__main__':main()
