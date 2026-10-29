"""Source-backed post-outcome diagnosis, no algorithm or gate changes."""
import numpy as np
from common import EV, save, jsonlines, read
from experiment import source

records=jsonlines(EV/'FG_NEW_FRAMES.jsonl');previous=read(EV/'CANDIDATE_FAILURE_DIAGNOSIS.json')
src=source();cases=[]
try:
    for fi in (188,189,190,191,192,340,341):
        r=records[fi];f=src.frame(fi);n=r['nodes']['OUTER_A'];rows=np.asarray(n['support_rows'],dtype='i8')
        p=f['xyz'][rows-f['offset']]
        projection=p@np.asarray(r['axis'])
        order=np.sort(projection);gap=np.diff(order)
        split=int(np.argmax(gap))+1 if len(gap) else None
        cases.append(dict(fi=fi,raw_xyz=n['xyz'],support_n=len(p),source_rows=rows.tolist(),raw_min=p.min(0).tolist(),raw_max=p.max(0).tolist(),raw_quantiles=np.quantile(p,[0,.25,.5,.75,1],axis=0).tolist(),body_axis_quantiles=np.quantile(projection,[0,.25,.5,.75,1]).tolist(),largest_support_gap_along_axis_m=None if split is None else float(gap[split-1]),points_below_largest_gap=split,points_above_largest_gap=None if split is None else len(p)-split,span_local=r['diagnostics']['partitions']['OUTER_A']['span_local_m'],coordinate_recompute_error=float(np.max(np.abs(np.median(p,0)-n['xyz'])))))
finally:src.close()
save('CANDIDATE_FAILURE_DIAGNOSIS_R2.json',dict(cases=cases,hold_exceedances=previous['hold_outer_steps_over_100mm'],consecutive_lateral_dot_min=min(r['lateral_dot'] for r in previous['cases']),correction='All measured >100mm hold jumps retain lateral dot>0.996; axis sign flipping is not supported as the cause here. The initial diagnostic mentioned a possible sign-anchor failure, not an observed cause. Current source supports instead span separated longitudinal populations, with distal-quantile membership/median changing across frames. No spatial continuity/unique-component condition exists in this one failed variant. This diagnosis does not establish anatomical identity or point purity, and does not introduce a repair or second variant.',source_row_verification='RAW componentwise median reproduced from bound rows, no history/prediction'))
