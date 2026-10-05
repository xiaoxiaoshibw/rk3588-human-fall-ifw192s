"""Independent child-process peak, and active-entry repeat timings."""
import json
import sys
import time
import numpy as np
from r0_01 import HERE, scene, settings, gd, write_new, digest
from r1_experiment_01 import process_peak
from refinement_04 import run_variant


def main():
    phase=sys.argv[1];k=int(sys.argv[2]);s=settings(7);up=np.array([0.,0.,1.]);height=(.5,2.)
    cloud,rows,_=scene('high_noise',7)
    before=process_peak()
    costs=[];signature=None
    for i in range(1 if phase=='memory' else 3):
        tick=time.perf_counter();sample,fit,iterator=gd.replay_sequence(cloud,rows,up,height,s)
        sampling=time.perf_counter()-tick
        tick=time.perf_counter();seq=list(iterator);raw=time.perf_counter()-tick
        tick=time.perf_counter();v=run_variant(cloud,sample,fit,seq,up,height,s,k);total=time.perf_counter()-tick
        tick=time.perf_counter();encoded=json.dumps(v,allow_nan=False,separators=(',',':')).encode();serialization=time.perf_counter()-tick
        key=digest(dict(W=v['W'],counts=v['refinement_counts'],metrics=v['report']['metrics'],status=v['report']['status']))
        if signature is None:signature=key
        else:assert signature==key
        costs.append(dict(repeat=i,sampling=sampling,raw=raw,LO=v['lo_elapsed_s'],refine=v['report']['stage_elapsed_s']['refine'],
                          decision=v['report']['stage_elapsed_s']['decision'],serialization=serialization,
                          includes_scalar_audit_total=total,serialized_bytes=len(encoded)))
    result=dict(phase=phase,k=k,before=before,after=process_peak(),costs=costs,semantic_sha=signature,
                status=v['report']['status'],runtime_scope='desktop process includes imports; no RK3588 claim',physical_verified=False)
    write_new(HERE/('active_%s_K%d_01.json'%(phase,k)),result)
    print(json.dumps({key:result[key] for key in ('phase','k','before','after','status')}))


if __name__=='__main__':main()
