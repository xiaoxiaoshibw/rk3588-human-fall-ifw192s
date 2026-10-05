"""Focused independent fixtures for source/header identity and conversion limits."""
import copy
import importlib.util
import json
from pathlib import Path
import numpy as np

OUT=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('audit',str(OUT/'04_local_chain_audit.py'))
audit=importlib.util.module_from_spec(spec);spec.loader.exec_module(audit)

base=dict(seq=12,stamp_sec=123,stamp_nanosec=456,offset_points=0,count_points=5,
          dropped_points=0,bag_time_sec=1790930182.123456)
original=dict(base,ordinal=0,bag_time_sec=1790930182.1234562)
adapted=dict(base,ordinal=0)
assert audit.compare_frames([base],[original],[adapted])
records=[]
for name,field,value in [('foreign_seq','seq',13),('wrong_nsec','stamp_nanosec',457),
    ('wrong_offset','offset_points',1),('wrong_count','count_points',4),
    ('lost_point','dropped_points',1),('wrong_bag_time','bag_time_sec',1790930183.123456),
    ('ordinal_alias','ordinal',1)]:
    bad=dict(original,**{field:value})
    try:audit.compare_frames([base],[bad],[adapted])
    except ValueError:records.append(dict(name=name,rejected=True))
    else:raise AssertionError(name+' accepted')
try:audit.compare_frames([base],[],[adapted])
except ValueError:records.append(dict(name='frame_count',rejected=True))
else:raise AssertionError('different frame count accepted')
a=np.array([[1.,2.,3.],[4.,5.,6.]],dtype='<f4');b=a.copy();b[1,2]+=1
assert a.shape==b.shape and audit.sha_bytes(a.tobytes())!=audit.sha_bytes(b.tobytes())
records.append(dict(name='same_count_different_content_hash',different=True))
stamp=np.float64(183460.007811)
loss=abs(float(stamp)-float(np.float32(stamp)))
assert loss>0.001
records.append(dict(name='float32_timestamp_loss_counterexample',numeric_error=loss,
                    units_verified=False,no_microsecond_precision_claim=True))
result=dict(kind='chain_negative_checks',checks=records,all_pass=True)
with (OUT/'06_chain_negative_checks.json').open('x',encoding='utf8') as f:json.dump(result,f,indent=2)
print(json.dumps(dict(checks=len(records),all_pass=True,timestamp_numeric_error=loss)))
