"""Consolidated evidence audit, adoption gate and immutable method freeze."""
import collections
import hashlib
import json
from pathlib import Path
import sys
from r0_01 import HERE, RUN, KINDS, SEEDS, write_new, digest


def stats(summary):
    stages={k:dict(status=collections.Counter(),worst_gt_normal_deg=0.,worst_gt_offset_m=0.,
                  worst_region_rms_m=0.,worst_region_p95_m=0.,costs=[],counts=collections.Counter()) for k in (1,2,3)}
    single=('clean','low_noise','high_noise','wall','density','missing')
    extra={2:[],3:[]};false_closed=[]
    for row in summary['results']:
        for k,v in zip((1,2,3),row['variants']):
            group=stages[k];group['status'][v['status']]+=1;group['counts'].update(v['refinement_counts'])
            for c in v.get('costs',[]):group['costs'].append(c)
            if row['case'].split('_')[0] in single or any(row['case'].startswith(x+'_') for x in single):
                if v['best_gt_error']:
                    group['worst_gt_normal_deg']=max(group['worst_gt_normal_deg'],v['best_gt_error']['normal_deg'])
                    group['worst_gt_offset_m']=max(group['worst_gt_offset_m'],v['best_gt_error']['offset_m'])
                for r in v['validation']:
                    group['worst_region_rms_m']=max(group['worst_region_rms_m'],r['stats']['rms_m'])
                    group['worst_region_p95_m']=max(group['worst_region_p95_m'],r['stats']['p95_m'])
            # Nonempty first two words low/high_noise included by startswith rule.
            if k>1 and row['variants'][0]['status']!='unresolved' and v['status']=='unresolved':extra[k].append(row['case'])
            if v['status']!='unresolved' and not v['scalar_full']['metrics']['NEAR']['holds']:false_closed.append(dict(case=row['case'],k=k))
    for k,group in stages.items():
        group['status']=dict(group['status']);group['counts']=dict(group['counts'])
        group['timing_max_by_stage_s']={stage:max((c[stage] for c in group['costs']),default=0.) for stage in
            ('sampling','raw','LO','refine','decision','serialization','variant_including_scalar_audit')}
        group['cost_repeat_groups']=sum(len(v.get('costs',[]))>=3 for row in summary['results'] for v in row['variants'] if v['variant_id']=='sampled_tls_K%d_v1'%k)
        del group['costs']
    return dict(stages=stages,extra_unresolved=extra,false_closed=false_closed,
                GT_scope='single-plane synthetic cases only; table/dual not asserted one physical ground',
                costs_scope='desktop; phase boundaries differ from native validated fitter')


def main():
    summary=json.loads((HERE/'r1_summary_02.json').read_text())
    report=stats(summary)
    assert not report['false_closed']
    assert len(summary['results'])==62
    for row in summary['results']:
        assert len(row['variants'])==3
        for v in row['variants']:
            groups=[r['frame_group'] for r in v['validation']]
            assert not groups or len(set(groups))==3 and 'fit' not in groups
    freeze=dict(schema=1,adoption='retain_frozen_baseline_no_adoption',final_seeds=[1707,1719,1741],
                development_seeds=list(SEEDS),final_kinds=list(KINDS),
                implementation_sha256={name:hashlib.sha256((HERE/name).read_bytes()).hexdigest() for name in
                    ('r0_01.py','refinement_05.py','holdout_03.py')},
                reason='K2/K3 introduce extra nonconvergence/unresolved; improved individual seed error is not enough for adoption gate',
                robust_weights='NOT_RUN condition not triggered',physical_verified=False,
                final_holdout_first_exposure_after_this_file=True)
    write_new(HERE/'development_metrics_01.json',report)
    write_new(HERE/'method_freeze_01.json',freeze)
    print(json.dumps(report,ensure_ascii=False))


if __name__=='__main__':main()
