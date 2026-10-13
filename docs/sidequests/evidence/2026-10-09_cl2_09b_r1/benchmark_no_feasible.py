"""Non-collinear but infeasible complete fallback; instrumentation disclosed."""
import sys,time,math
from unittest.mock import patch
from prepare import E,save
sys.path[:0]=[str(E/'candidate'),str(E/'frozen')]
import floor_sheet as module
rows=[]
svd=module.np.linalg.svd;combinations=module.itertools.combinations
for n in [25,60,100]:
    # Grid integer range [-400,392], inside bounded production work domain.
    keys=[(8*(k-n//2),0) for k in range(n-1)]+[(0,1)]
    stats={'svd_calls':0,'quartets_visited':0}
    def counted_svd(*a,**kw):
        stats['svd_calls']+=1;return svd(*a,**kw)
    def counted_combinations(items,k):
        for combo in combinations(items,k):
            if k==4:stats['quartets_visited']+=1
            yield combo
    begin=time.perf_counter()
    with patch.object(module.np.linalg,'svd',side_effect=counted_svd),patch.object(module.itertools,'combinations',side_effect=counted_combinations):
        result=module._roi_metrics([{'key':list(k)} for k in keys])
    elapsed=time.perf_counter()-begin
    assert not result['ok'] and stats['quartets_visited']==math.comb(n,4)
    rows.append(dict(n=n,elapsed_sec_instrumented=elapsed,**stats,result=result))
    print(n,elapsed,stats,flush=True)
save('04_benchmark_no_feasible.json',dict(results=rows,
    scope='Integer non-collinear scene with y=1 cell and 8-cell base spacing; no feasible quartet. Full fallback measured incl mock counter overhead. Board NOT_RUN; no unconditional worst-time upper bound claimed.'))
