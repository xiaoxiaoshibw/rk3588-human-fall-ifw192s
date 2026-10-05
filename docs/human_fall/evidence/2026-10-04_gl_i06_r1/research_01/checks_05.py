"""GLI06 contract probes with known geometry and independent scalar oracle."""
import copy
import itertools
import json
import math
from pathlib import Path
import numpy as np
from r0_01 import HERE, digest, scene, settings, scalar_oracle, write_new, gd, g, search_events
from refinement_05 import bounded_refine, validate_packet, run_variant


def p(deg=0., support=500, offset=1.4):
    a = math.radians(deg)
    return dict(normal=[math.sin(a),0.,math.cos(a)],offset_m=offset,support_count=support,eigenvalue_ratio=1.)


def events(pool):
    return [dict(x, iteration=i, stage='qualified') for i,x in enumerate(pool)]


def reject(fn):
    try:
        fn()
    except (ValueError,TypeError):
        return
    raise AssertionError('invalid input accepted')


def main():
    s = settings(7)
    results=[]
    for name,pool,expected in [
        ('all_similar',[p(0),p(4),p(8)],'seen_pairwise_closed'),
        ('chain_middle_best',[p(0,450),p(6,500),p(12,450)],'unresolved'),
        ('ties',[p(0),p(6),p(12)],'unresolved'),
        ('weak_distinct',[p(0),p(0,399,1.54)],'seen_dominant_pool_closed'),
        ('near_boundary',[p(0),p(0,400,1.54)],'unresolved'),
        ('late_best',[p(0,200),p(0,200,1.54),p(0,900)],'seen_dominant_pool_closed'),
        ('late_distinct',[p(0),p(0),p(12)],'unresolved'),
        ('exact_merge',[p(0),p(0),p(0)],'seen_pairwise_closed')]:
        for perm in itertools.permutations(pool):
            report=search_events(events(perm),lambda e:(e,'refined'),s,candidate_budget=512)
            scalar=scalar_oracle(list(perm),s)
            assert scalar['status']==expected==report['status'],name
            assert scalar['best_support']==report['best_support']
            for metric in ('ALL','NEAR','BEST_ONLY'):
                assert scalar['metrics'][metric]['holds']==report['metrics'][metric]['holds']
            if name=='chain_middle_best':
                assert scalar['metrics']['BEST_ONLY']['holds']
            # budgets exact boundary and one short; duplicates can merge for free.
            for key in ('candidate_budget','refine_budget','trace_budget','iteration_budget'):
                for limit in (0,1,2,3):
                    tight=search_events(events(perm),lambda e:(e,'refined'),s,**{key:limit})
                    if tight['gaps_input']:
                        assert tight['status']=='unresolved'
                    else:
                        assert tight['status']==expected
            results.append(dict(case=name,expected=expected,permutation=list(perm)))
    pts,rows,_=scene('clean',7)
    sampled,fit,iterator=gd.replay_sequence(pts,rows,np.array([0.,0.,1.]),(.5,2.),s)
    seq=list(iterator)
    packet=dict(schema=1,units='m',frame='research_source',source_sha=digest(pts),fit_sha=digest(fit),
                sampled_sha=digest(sampled),raw_sha=digest(seq),settings_sha=digest(s))
    validate_packet(pts,fit,sampled,seq,s,packet)
    changed=pts.copy();changed[0,2]-=.01
    reject(lambda:validate_packet(changed,fit,sampled,seq,s,packet))
    bad=pts.copy();bad[0,0]=float('nan')
    reject(lambda:validate_packet(bad,fit,sampled,seq,s,packet))
    for key,value in [('units','cm'),('frame','foreign'),('schema',2),('schema',True),('source_sha','bad')]:
        reject(lambda:validate_packet(pts,fit,sampled,seq,s,dict(packet,**{key:value})))
    reject(lambda:validate_packet(pts,fit,sampled,seq,dict(s,seed=19),packet))
    reject(lambda:validate_packet(pts,fit,sampled,seq,dict(s,inlier_threshold_m=0.),packet))
    reject(lambda:g._unit_vector([0.,0.,0.],'up'))
    reject(lambda:g._height_interval([float('nan'),2.]))
    for key in ('max_angle_rad','distinct_normal_deg','distinct_offset_m','support_close_ratio'):
        reject(lambda:g.resolve_constrained_settings(dict(s,**{key:float('nan')})))
    target=HERE/'check_exclusive_target_05.json'
    write_new(target,packet)
    reject(lambda:write_new(target,{}))
    reject(lambda:write_new(HERE.parent/'outside_01.json',{}))
    assert json.loads(target.read_text())==packet
    # Reject invalid budgets/K even when no draw can call the numerical solver.
    for bad in (-1, True, 1.5, 6001):
        reject(lambda: run_variant(pts, sampled, fit, [], np.array([0.,0.,1.]), (.5,2.), s, 1, lo_budget=bad))
    for bad in (0, True, 1.5, 4):
        reject(lambda: run_variant(pts, sampled, fit, [], np.array([0.,0.,1.]), (.5,2.), s, bad))
    # Genuine numerical rounds for clean, degenerate, high noise and resource boundaries.
    for kind in ('clean','high_noise','collinear','narrow_band'):
        cloud,rows,_=scene(kind,7)
        sample,fit,iterator=gd.replay_sequence(cloud,rows,np.array([0.,0.,1.]),(.5,2.),s)
        seq=list(iterator)
        for k in (1,2,3):
            for budget in (0,1,k-1,k,6000):
                r=run_variant(cloud,sample,fit,seq,np.array([0.,0.,1.]),(.5,2.),s,k,lo_budget=budget)
                if any(d['resource_gap'] for d in r['details']):
                    assert r['report']['status']=='unresolved'
                if any(d['nonconverged'] for d in r['details']):
                    assert r['report']['status']=='unresolved'
                results.append(dict(case='numeric_%s_K%d_LO%d'%(kind,k,budget),
                                    status=r['report']['status'],counts=r['refinement_counts']))
    # Solver-injected state transitions, not claimed observed TLS cycles.
    xy=np.random.RandomState(7).uniform(-3,3,(250,2))
    two=np.vstack([np.column_stack([xy,np.full(250,-1.4)]),np.column_stack([xy,np.full(250,-1.54)])])
    ids=np.arange(500)
    a,b=p(0,250),p(0,250,1.54)
    def injected(models):
        iterator=iter(models)
        return lambda *args:(next(iterator),'injected_solver_state')
    for name,models,k in [('two_cycle',[b,a,b],3),('nonconverged',[b,a],2),
                          ('later_height',[a,p(0,250,3.)],2),('later_angle',[a,p(25,250)],2),
                          ('later_support',[a,p(0,99)],2),('later_degenerate',[a,dict(a,eigenvalue_ratio=0.)],2)]:
        last,d=bounded_refine(two,ids,ids,a,np.array([0.,0.,1.]),(.5,2.),s,k,dict(remaining=6000),injected(models))
        assert d['quality_gap'],name
        if name=='two_cycle':assert d['cycle'] and d['full_k']
        if name.startswith('later_'):assert d['violation'] and last==a
        results.append(dict(case=name,domain='injected_solver_state_not_empirical_TLS',detail=d))
    # Small J must not change best anchor or hide a distinct NEAR witness.
    pool=[dict(p(0,500),J=10.),dict(p(12,450),J=0.)]
    report=search_events(events(pool),lambda e:(e,'refined'),s)
    assert report['best_support']==500 and report['status']=='unresolved'
    sorted_pool=sorted([dict(p(0,500),J=.002),dict(p(4,500),J=.001)],key=lambda x:x['J'])
    assert scalar_oracle(sorted_pool,s)['best_support']==500
    results.append(dict(case='J_diagnostic_only',passed=True))
    write_new(HERE/'checks_result_05.json',dict(results=results,required_ids=['A01','A03','A04','A05','Q01','Q02','Q03','Q04'],
                  robust_weights='NOT_RUN: condition not triggered; zero residual scale therefore no weight calculation',physical_verified=False))
    print('contract probes PASS',len(results))


if __name__=='__main__':main()
