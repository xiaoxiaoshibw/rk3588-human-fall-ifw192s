"""Versioned full-W publication from immutable numerical ledgers; no new TLS."""
import copy
import itertools
import json
import time
import numpy as np
from r0_01 import HERE, scalar_oracle, write_new, settings, scene, gd
from r1_experiment_01 import brief, compact_new
from refinement_03 import run_variant
from oracle_analysis import oracle


def full_publish(v,s):
    out=copy.deepcopy(v)
    r=out['report']; w=out['W']; costs=[]
    for _ in range(3):
        tick=time.perf_counter();full=oracle(w,s,gaps=r['gaps_input']);costs.append(time.perf_counter()-tick)
    expected=scalar_oracle(w,s,gaps=r['gaps_input'])
    assert full['status']==expected['status']==r['status']
    for metric in ('ALL','NEAR','BEST_ONLY'):
        assert full['metrics'][metric]['distinct_pairs']==expected['metrics'][metric]['distinct_pairs']
    r['stored_subset_diagnostics']={k:copy.deepcopy(r[k]) for k in ('best_support','near_pool_indices','top_tie_indices','metrics','witness_count')}
    for k in ('best_support','near_pool_indices','top_tie_indices','metrics','witness_count'):r[k]=full[k]
    r['metric_domain']='full per-event W in variant.W; witnesses field is bounded exact storage subset'
    r['stage_elapsed_s']['decision']+=costs[0]
    assert r['best_support']==max((p['support_count'] for p in w),default=None)
    return out,costs


def main():
    summary=json.loads((HERE/'r1_summary_01.json').read_text())
    for case in summary['results']:
        s=json.loads((HERE/('r1_case_%s_K1_01.json'%case['case'])).read_text())['packet']
        # settings values come from original same-sequence R0, not guessed from name.
        setting=json.loads((HERE/('r0_case_'+case['case']+'_01.json')).read_text())['settings']
        for k,row in zip((1,2,3),case['variants']):
            original=HERE/('r1_case_%s_K%d_01.json'%(case['case'],k))
            item=json.loads(original.read_text())
            item['variant'],extra=full_publish(item['variant'],setting)
            item.update(numerical_origin=original.name,
                        publication='same TLS/W; full vector relationships independently scalar checked',
                        full_domain_decision_repeats_s=extra)
            for i,cost in enumerate(item['costs']):
                cost['additional_full_domain_decision_s']=extra[i%3]
                cost['decision']+=extra[i%3]
                cost['phase_measurement_note']='full-domain decision measured separately; earlier TLS timings retained'
            compact_new(HERE/('r1_case_%s_K%d_02.json'%(case['case'],k)),item)
            row.update(best_support=item['variant']['report']['best_support'],full_domain_decision_repeats_s=extra,
                       costs=item['costs'],full_metric_domain='variant.W multiset',
                       bounded_storage_best_support=item['variant']['report']['stored_subset_diagnostics']['best_support'])
    # Actual new entry parity including bounded late-best case, no saved-W-only proof.
    cloud,rows,_=scene('high_noise',7);s=settings(7)
    sample,fit,it=gd.replay_sequence(cloud,rows,np.array([0.,0.,1.]),(.5,2.),s);seq=list(it)
    probes=[]
    for k in (1,2,3):
        expected=json.loads((HERE/('r1_case_high_noise_7_False_K%d_02.json'%k)).read_text())['variant']
        actual=run_variant(cloud,sample,fit,seq,np.array([0.,0.,1.]),(.5,2.),s,k)
        assert actual['W']==expected['W']
        assert actual['report']['metrics']==expected['report']['metrics']
        assert actual['refinement_counts']==expected['refinement_counts']
        tight=run_variant(cloud,sample,fit,seq,np.array([0.,0.,1.]),(.5,2.),s,k,candidate_budget=0)
        assert tight['report']['status']=='unresolved'
        assert tight['report']['best_support']==max(p['support_count'] for p in tight['W'])
        assert tight['report']['stored_subset_diagnostics']['best_support'] is None
        probes.append(dict(k=k,W_count=len(actual['W']),tight_best=tight['report']['best_support'],
                           tight_status=tight['report']['status'],exact_numerical_parity=True))
    write_new(HERE/'publication_probes_02.json',dict(probes=probes,physical_verified=False))
    summary['active_implementation']='refinement_03.py; _01/02 historical numerical reporting domain'
    summary['active_ledger_suffix']='r1_case_*_02.json; 01 immutable numerical origin'
    write_new(HERE/'r1_summary_02.json',summary)
    print('full-W publication PASS',len(summary['results']))


if __name__=='__main__':main()
