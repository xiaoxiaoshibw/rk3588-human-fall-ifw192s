"""Same-process actual timing; profiling is separate from uninstrumented timings."""
import builtins
from contextlib import ExitStack
import importlib.util
import math
import platform
import statistics
import sys
import time
from unittest.mock import patch
import numpy as np
from prepare import E, sha, save

sys.path[:0] = [str(E/'candidate'), str(E/'frozen')]
import floor_sheet as candidate
spec=importlib.util.spec_from_file_location('cl209b',E/'baseline/floor_sheet.py')
baseline=importlib.util.module_from_spec(spec)
spec.loader.exec_module(baseline)

def cases(size):
    return {'failed_with_feasible':[(0,4*k) for k in range(size-1)]+[(2,6)],
            'noncollinear_no_solution':[(8*(k-size//2),0) for k in range(size-1)]+[(0,1)],
            'line':[(0,4*k) for k in range(size)]}

def profile(module, keys):
    totals={k:dict(calls=0,seconds=0.) for k in ['enumeration_next','pair_hypot','spacing_min','spacing_all','svd','sorting']}
    def timed(name, func):
        def call(*args,**kwargs):
            start=time.perf_counter()
            try:
                return func(*args,**kwargs)
            finally:
                totals[name]['calls']+=1
                totals[name]['seconds']+=time.perf_counter()-start
        return call
    combinations=module.itertools.combinations
    def enumerated(items,k):
        iterator=combinations(items,k)
        while True:
            start=time.perf_counter()
            try:
                value=next(iterator)
            except StopIteration:
                return
            totals['enumeration_next']['calls']+=1
            totals['enumeration_next']['seconds']+=time.perf_counter()-start
            yield value
    start=time.perf_counter()
    with ExitStack() as stack:
        stack.enter_context(patch.object(module.itertools,'combinations',enumerated))
        stack.enter_context(patch.object(module.np,'hypot',timed('pair_hypot',module.np.hypot)))
        stack.enter_context(patch.object(module.np,'all',timed('spacing_all',module.np.all)))
        stack.enter_context(patch.object(module.np.linalg,'svd',timed('svd',module.np.linalg.svd)))
        stack.enter_context(patch.object(module,'sorted',timed('sorting',builtins.sorted),create=True))
        stack.enter_context(patch.object(module,'min',timed('spacing_min',builtins.min),create=True))
        result=module._roi_metrics([{'key':list(k)} for k in keys])
    return dict(total_instrumented_sec=time.perf_counter()-start,components=totals,result=result,
                caveat='Elapsed includes wrappers/counters. np.all combines collinearity and independence; '
                       'spacing_min is inclusive of nested hypot/enumeration in the legacy generator; '
                       'nested-loop body and scalar threshold tests remain in residual; '
                       'do not add nested call durations or compare these totals as runtime benchmarks.')

if __name__=='__main__':
    if len(sys.argv)>1 and sys.argv[1]=='profile':
        profiles={}
        for label, keys in cases(60).items():
            if label=='line':continue
            profiles[label]={}
            for name,module in [('baseline',baseline),('candidate',candidate)]:
                profiles[label][name]=profile(module,keys)
                print('PROFILE',label,name,profiles[label][name]['total_instrumented_sec'],flush=True)
            assert profiles[label]['baseline']['result']==profiles[label]['candidate']['result']
        save(sys.argv[2] if len(sys.argv)>2 else '03_profile.json',profiles)
        raise SystemExit(0)
    rows=[]
    for size in [25,60,100]:
        for label,keys in cases(size).items():
            data=[{'key':list(k)} for k in keys]
            samples={'baseline':[],'candidate':[]}
            results={}
            for repetition in range(3):
                # Alternate order so slow baseline/CPU state do not always precede candidate.
                modules=[('baseline',baseline),('candidate',candidate)]
                if repetition%2:modules.reverse()
                for name,module in modules:
                    begin=time.perf_counter(); result=module._roi_metrics(data)
                    elapsed=time.perf_counter()-begin
                    samples[name].append(elapsed);results[name]=result
                    print(size,label,repetition,name,elapsed,result['ok'],flush=True)
                assert results['baseline']==results['candidate']
            rows.append(dict(size=size,case=label,quartets=math.comb(size,4),samples_sec=samples,
                             median_sec={k:statistics.median(v) for k,v in samples.items()},
                             speedup=statistics.median(samples['baseline'])/statistics.median(samples['candidate']),
                             exact_dict_equal=True,result=results['candidate']))
    save('04_benchmark.json',dict(python=sys.version,executable=sys.executable,numpy=np.__version__,
         platform=platform.platform(),processor=platform.processor(),baseline_sha256=sha(E/'baseline/floor_sheet.py'),
         candidate_sha256=sha(E/'candidate/floor_sheet.py'),results=rows,
         method='Three uninstrumented actual calls each; first sample is first invocation for this input, '
                'not a cold OS/BLAS process. Alternate order; no production latency bound or board assertion.'))
