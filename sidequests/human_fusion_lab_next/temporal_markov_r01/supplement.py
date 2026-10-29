"""Predeclared transition-strength and duration mechanism sensitivity; no selection."""
import copy
import numpy as np
from experiment import read,write,HERE,EVIDENCE
from temporal import HMM,Track,transition
from test_temporal import feature


def main():
    run=EVIDENCE/'run_r3';cfg=read(run/'FROZEN_CONFIG.json');catalog=read(run/'catalog.json');sweep=[]
    for self_probability in [.85,.94,.98]:
        a=np.array(cfg['posture']['matrix']);off=a-np.diag(a.diagonal());off/=off.sum(1)[:,None]
        matrix=off*(1-self_probability)+np.eye(len(a))*self_probability
        switches=0;unknown=0
        for s in catalog:
            os=read(run/s['sid']/'predictions.json');model=HMM(cfg['posture']['initial'],matrix);last=None;prev=None
            for o in os:
                if o['reset']:
                    model=HMM(cfg['posture']['initial'],matrix);last=prev=None
                p=model.update(o['emission'],None if last is None else o['time']-last);state=int(np.argmax(p))
                switches+=prev is not None and state!=prev;unknown+=state==5;prev=state;last=o['time']
        sweep.append(dict(self_probability=self_probability,switches=int(switches),unknown=int(unknown),semantic_accuracy='UNKNOWN'))
    duration=[]
    for hold in [.3,.6,.9]:
        c=copy.deepcopy(cfg);c['low_hold_s']=hold;m=Track(c);events=[]
        for i in range(80):
            t=i*.1;frac=float(np.clip((t-1)/.5,0,1));o=m.update(t,feature(1.65-1.2*frac,.95-.75*frac),.95)
            if o['candidate']:events.append(t)
        duration.append(dict(low_hold_s=hold,synthetic_fast_low_candidate_times=events))
    write(run/'SENSITIVITY.json',dict(posture_transition=sweep,duration_mechanism=duration,selection='NONE; report all configurations, no GT used'))
    print(sweep,duration)


if __name__=='__main__':main()
