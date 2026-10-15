"""R2 rework: bound geometric perturbation, never infer identity from reference stability.

Reuse the entire frozen runner in an isolated process. Hooks only bind session/frame
for a streamed guard ledger and wrap the existing recovery decision. No legacy edits.
"""
import argparse
import json
from pathlib import Path
import numpy as np
import research_retention as base
from core import skeleton
from actions import HERE,OUT,read,sha,dump

_recover=base.recover
_load=base.load
CORE_CFG=read(OUT/'RUN_MANIFEST.json')['config']
CONTEXT={}


def guarded_recover(p,anchor,bg,cfg,nearest,coverage,past,arm):
    pool,added,evidence=_recover(p,anchor,bg,cfg,nearest,coverage,past,arm)
    reasons=[];center_shift=0.;fraction=1.;angle=None
    if len(added):
        merged=np.union1d(anchor,added)
        fraction=len(anchor)/len(merged)
        center_shift=float(np.linalg.norm(np.median(p[merged],axis=0)-np.median(p[anchor],axis=0)))
        before=skeleton(p[anchor],anchor,CORE_CFG);after=skeleton(p[merged],merged,CORE_CFG)
        if fraction<cfg['guard_anchor_fraction_min']:reasons.append('INSUFFICIENT_INDEPENDENT_ANCHOR_FRACTION')
        if center_shift>cfg['guard_center_max_m']:reasons.append('EXCESS_MEDIAN_CENTER_SHIFT')
        if 'axis' in before:
            if 'axis' not in after:reasons.append('NEW_CURRENT_AXIS_MISSING')
            else:
                angle=float(np.degrees(np.arccos(np.clip(abs(np.dot(before['axis'],after['axis'])),0,1))))
                if angle>cfg['guard_axis_change_max_deg']:reasons.append('EXCESS_CURRENT_AXIS_CHANGE')
    kept=np.empty(0,dtype=int) if reasons else added
    # Entire proposal is rejected on excessive perturbation. No cherry-picked subset.
    evidence['guard_reasons']=reasons
    if CONTEXT.get('log'):
        variants=CONTEXT['variants'];call=CONTEXT['calls'];fi=CONTEXT['frames'][call//len(variants)]
        assert arm==variants[call%len(variants)]
        CONTEXT['calls']+=1
        row={'sid':CONTEXT['sid'],'fi':fi,'variant':arm,'t_sec':past.t,'identity':'UNKNOWN',
            'before_guard_added_source_indices':added.tolist(),'after_guard_added_source_indices':kept.tolist(),
            'guard_rejected_source_indices':added.tolist() if reasons else [],'reasons':reasons,
            'anchor_fraction':fraction,'proposed_center_shift_m':center_shift,'proposed_axis_change_deg':angle,
            'no_body_or_furniture_identity_decision':True}
        CONTEXT['log'].write(json.dumps(row,ensure_ascii=False,allow_nan=False)+'\n');CONTEXT['log'].flush()
    return pool,kept,evidence


def bound_load(sid):
    meta,raw,hashes=_load(sid)
    rec=next(r for r in CONTEXT['catalog']['sessions'] if r['session_id']==sid)
    CONTEXT.update(sid=sid,frames=rec['available_frames'],calls=0)
    return meta,raw,hashes


def run(run_id,config):
    cfg=read(Path(config));assert cfg['guard_source_sha']==sha(Path(__file__))
    root=base.RESULT/run_id
    if root.exists():raise ValueError('Exclusive new guarded run required')
    # The evidence stream is separate so the unchanged runner still exclusively creates root.
    logpath=base.E/(run_id+'_GUARD_DECISIONS.jsonl')
    with logpath.open('x',encoding='utf8') as log:
        CONTEXT.update(log=log,variants=cfg['variants'],catalog=read(OUT/'catalog.json'))
        base.recover=guarded_recover;base.load=bound_load
        try:base.run(run_id,config)
        finally:base.recover=_recover;base.load=_load;CONTEXT.clear()
    dump(root/'GUARD_BINDING.json',{'code_sha':sha(Path(__file__)),'config_sha':sha(Path(config)),
        'base_code_sha':sha(HERE/'research_retention.py'),'guard_decisions':str(logpath),
        'validation':'REUSED_REGRESSION; original 80 frame results were seen before rework; no new independent test',
        'R3_auxiliary_control':'run_01 preserved, not rerun or promoted; new main/feedback only'})


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--run-id',required=True);ap.add_argument('--config',required=True);a=ap.parse_args();run(a.run_id,a.config)
