"""Explicit synthetic mechanisms, never independent E1 learning validation."""
import copy
import time
import numpy as np
from experiment import read, write, HERE, EVIDENCE, stats
from temporal import Track, sequence
from test_temporal import feature


def run(out):
    cfg = read(HERE/'config.json')
    cases = {}
    for name, probs in [('flicker', [.8, .3]*30), ('furniture_false_positive', [.95]*60), ('occlusion', [.9]*10+[None]*5+[.9]*10)]:
        m = Track(cfg); os = []
        for i,p in enumerate(probs):
            os.append(m.update(i*.103, None if p is None else feature(), p))
        cases[name] = dict(source='SYNTHETIC_MECHANISM_NOT_GT', frames=len(os), outputs=os)
    for name, descent_s in [('fast_controlled_low', .5), ('slow_low', 3.0), ('initial_low', 0)]:
        m = Track(cfg); os = []
        for i in range(80):
            t=i*.1
            fraction = 1 if name == 'initial_low' else float(np.clip((t-1)/descent_s, 0, 1))
            f=feature(1.65-1.2*fraction, .95-.75*fraction)
            os.append(m.update(t,f,.95))
        cases[name] = dict(source='SYNTHETIC_NOT_REAL_FALL', candidates=sum(o['candidate'] for o in os), outputs=os)
    rows = [dict(sid='s', track_id='A' if i%2 else 'B', fi=i, time=i*.1, feature=feature(), rf=.9 if i%2 else .1) for i in range(40)]
    combined=sequence(rows,cfg); mismatches=[]
    for ident in ['A','B']:
        independent=sequence([r for r in rows if r['track_id']==ident],cfg)
        actual=[o for o in combined if o['track_id']==ident]
        for a,b in zip(actual,independent):
            for k in ['presence','posture','hsmm','mc','candidate']:
                if a[k]!=b[k]:mismatches.append([a['fi'],k])
    cases['multi_id']=dict(source='SYNTHETIC_TWO_INTERLEAVED_IDS', contamination_count=len(mismatches), mismatches=mismatches)
    latency={}
    for name in ['baseline','ema','vote','hysteresis','presence']:
        m=Track(cfg); first=None
        for i in range(60):
            t=i*.1; o=m.update(t,feature(),.1 if i<20 else .9)
            positive=o[name][0]>.5 if name=='presence' else o[name]
            if i>=20 and positive and first is None:first=t-2
        latency[name]=first
    write(out/'MECHANISMS.json',dict(cases=cases, synthetic_step_response_s=latency,
                                    semantic_metrics='UNKNOWN; synthetic response delay is NOT real detection latency'))
    print('mechanisms', {k:v.get('candidates',v.get('contamination_count')) for k,v in cases.items()}, latency)


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--out',type=__import__('pathlib').Path,default=EVIDENCE/'run_r2');run(p.parse_args().out)
