"""Post-outcome diagnosis only; no candidate rerun or parameter changes."""
import numpy as np
from common import EV, jsonlines, save

records=jsonlines(EV/'FG_NEW_FRAMES.jsonl');cases=[]
for a,b in zip(records,records[1:]):
    if not (183<=a['fi']<333):continue
    na,nb=a['nodes']['OUTER_A'],b['nodes']['OUTER_A']
    if not (na['valid'] and nb['valid']):continue
    step=float(np.linalg.norm(np.asarray(nb['xyz'])-na['xyz'])*1000)
    axis_dot=None if a['axis'] is None or b['axis'] is None else float(np.dot(a['axis'],b['axis']))
    lateral_dot=None if a['basis_lateral'] is None or b['basis_lateral'] is None else float(np.dot(a['basis_lateral'],b['basis_lateral']))
    if step>100:
        cases.append(dict(from_frame=a['fi'],to_frame=b['fi'],step_mm=step,axis_dot=axis_dot,lateral_dot=lateral_dot,from_lateral=a['basis_lateral'],to_lateral=b['basis_lateral'],from_xyz=na['xyz'],to_xyz=nb['xyz'],from_support_rows=na['support_rows'],to_support_rows=nb['support_rows'],from_partition=a['diagnostics']['partitions']['OUTER_A'],to_partition=b['diagnostics']['partitions']['OUTER_A']))
save('CANDIDATE_FAILURE_DIAGNOSIS.json',dict(mode='DIAGNOSIS_ONLY_NO_VARIANT_OR_RERUN',hold_outer_steps_over_100mm=len(cases),cases=cases,interpretation='Inspect transverse sign dot and source support membership. Largest-component sign anchoring may flip when the dominant component changes; other step changes can arise from current quantile support. This remains a failed candidate; no fix or promotion in S07.'))
print([(r['from_frame'],r['to_frame'],round(r['step_mm'],2),r['lateral_dot']) for r in cases],flush=True)
