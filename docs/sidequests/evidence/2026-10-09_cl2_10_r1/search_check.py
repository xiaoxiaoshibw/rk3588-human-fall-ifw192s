"""09C already verified search: one key timing each, exact known output, no redesign."""
import sys
import time
from prepare import E,C,load,save,sha
sys.path[:0]=[str(E/'candidate'),str(E/'frozen')]
import floor_sheet

reference=load(C/'04_benchmark.json')
rows=[]
for r in reference['results']:
    if r['size']!=100 or r['case']=='line':continue
    if r['case']=='failed_with_feasible':keys=[(0,4*k) for k in range(99)]+[(2,6)]
    else:keys=[(8*(k-50),0) for k in range(99)]+[(0,1)]
    data=[{'key':list(k)} for k in keys];start=time.perf_counter();result=floor_sheet._roi_metrics(data)
    seconds=time.perf_counter()-start
    assert result==r['result']
    rows.append(dict(case=r['case'],n=100,seconds=seconds,exact_reference_dict_equal=True,
                    reference_sha256=sha(C/'04_benchmark.json'),reference_median_seconds=r['median_sec']['candidate']))
save('03_search_performance.json',dict(rows=rows,runtime_sha256=sha(E/'candidate/floor_sheet.py'),
    unchanged_CL209C_source=sha(E/'candidate/floor_sheet.py')==sha(C/'candidate/floor_sheet.py'),
    complexity='Still O(n4) worst and O(n2) memory; one measured call per input, no statistical latency limit or board assertion.'))
print('CL209C_KEY_SEARCH_EXACT_AND_TIMING_PASS',rows,flush=True)
