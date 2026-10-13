import importlib.util,sys,time
import numpy as np
from prepare import E,save
sys.path[:0]=[str(E/'candidate'),str(E/'frozen')]
import floor_sheet
rows=[]
for size in [5,25,60,100]:
    cases={'line':[(0,4*k) for k in range(size)],
           'failed_with_feasible':[(0,4*k) for k in range(size-1)]+[(2,6)]}
    for label,keys in cases.items():
        begin=time.perf_counter();r=floor_sheet._roi_metrics([{'key':list(k)} for k in keys]);duration=time.perf_counter()-begin
        rows.append(dict(size=size,case=label,seconds=duration,result=r))
        print(size,label,duration,r['ok'],flush=True)
save('04_benchmark.json',dict(platform='Windows local Python3.12 NumPy1.26; board NOT_RUN',results=rows,
    scope='Only measured sizes/shapes; complete fallback worst O(n4), no runtime/board latency assertion.'))
