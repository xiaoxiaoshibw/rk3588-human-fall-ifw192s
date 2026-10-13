"""Follow-up to slower single timings: contemporaneous unchanged-09C control."""
import importlib.util
import statistics
import sys
import time
from prepare import E,C,load,save,sha
sys.path[:0]=[str(E/'candidate'),str(E/'frozen')]
import floor_sheet as local
spec=importlib.util.spec_from_file_location('control_09c',C/'candidate/floor_sheet.py')
control=importlib.util.module_from_spec(spec);spec.loader.exec_module(control)
assert sha(E/'candidate/floor_sheet.py')==sha(C/'candidate/floor_sheet.py')
reference=load(C/'04_benchmark.json');rows=[]
for ref in reference['results']:
    if ref['size']!=100 or ref['case']=='line':continue
    keys=([(0,4*k) for k in range(99)]+[(2,6)] if ref['case']=='failed_with_feasible'
          else [(8*(k-50),0) for k in range(99)]+[(0,1)])
    data=[{'key':list(k)} for k in keys]
    samples={'control_09c':[],'local_10':[]}
    for trial in range(3):
        order=[('control_09c',control),('local_10',local)]
        if trial%2:order.reverse()
        for label,module in order:
            begin=time.perf_counter();result=module._roi_metrics(data);elapsed=time.perf_counter()-begin
            assert result==ref['result'];samples[label].append(elapsed)
            print(ref['case'],trial,label,elapsed,flush=True)
    rows.append(dict(case=ref['case'],samples_sec=samples,median_sec={k:statistics.median(v) for k,v in samples.items()},
                     exact_reference_equal=True))
save('03_search_paired.json',dict(rows=rows,source_bytes_identical=True,source_sha256=sha(E/'candidate/floor_sheet.py'),
    reason='Initial single timings higher than old medians; pair with unchanged original 09C in current process. '
           'No performance development or claim about thermal/frequency causes; no production latency limit exists.'))
