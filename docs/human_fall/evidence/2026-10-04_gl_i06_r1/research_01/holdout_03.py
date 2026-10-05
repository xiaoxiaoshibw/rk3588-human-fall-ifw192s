"""Once-exposed synthetic final holdout after method freeze, not real physics."""
import itertools
import json
import time
import numpy as np
from r0_01 import HERE, KINDS, scene, settings, digest, gd, g, write_new
from r1_experiment_01 import brief, compact_new, process_peak
from refinement_05 import run_variant, validate_packet


def main():
    freeze=json.loads((HERE/'method_freeze_01.json').read_text())
    assert freeze['adoption']=='retain_frozen_baseline_no_adoption'
    assert freeze['final_seeds']==[1707,1719,1741]
    results=[]
    for kind,seed in itertools.product(KINDS,freeze['final_seeds']):
        cloud,rows,regions=scene(kind,seed)
        s=settings(seed);up=np.array([0.,0.,1.]);height=(.5,2.)
        sampled,fit,iterator=gd.replay_sequence(cloud,rows,up,height,s);seq=list(iterator)
        packet=dict(schema=1,units='m',frame='research_source',source_sha=digest(cloud),fit_sha=digest(fit),
                    sampled_sha=digest(sampled),raw_sha=digest(seq),settings_sha=digest(s))
        validate_packet(cloud,fit,sampled,seq,s,packet)
        variants=[]
        for k in (1,2,3):
            v=run_variant(cloud,sampled,fit,seq,up,height,s,k)
            name='final_%s_%d_K%d_01.json'%(kind,seed,k)
            compact_new(HERE/name,dict(packet=packet,variant=v,freeze_sha=digest(freeze)))
            row=brief(v,cloud,regions,s,True);row['artifact']=name;variants.append(row)
        results.append(dict(case='final_%s_%d'%(kind,seed),variants=variants,packet=packet,
                            ground_identity='synthetic GT only',physical_verified=False))
        print(kind,seed,[v['status'] for v in variants],flush=True)
    write_new(HERE/'final_holdout_summary_01.json',dict(results=results,first_exposure=True,
        methods_frozen_before_exposure=True,no_post_exposure_method_change=True,
        final_synthetic_not_real_physical=True,real_final_holdout='NOT_RUN: existing 89 frames development only',
        freeze_sha=digest(freeze),physical_verified=False))


if __name__=='__main__':main()
