"""Pre-audit closure and compact source-linked facts. Not a final seal."""
from prepare import E,C,load,save,sha

b=load(E/'00_baseline.json');changed={p:dict(before=d,after=sha(p)) for p,d in b['guards'].items() if sha(p)!=d}
assert not changed,changed
runtime={}
for folder in ['candidate','frozen','baseline']:
    for p in (E/folder).rglob('*.py'):
        rel=p.relative_to(E);assert sha(p)==sha(C/rel),str(rel);runtime[rel.as_posix()]=sha(p)
save('04_source_summary.json',dict(protected_assets_verified=len(b['guards']),protected_assets_changed=changed,
     immutable_runtime_bindings=runtime,production_integrated=False,new_repair=False,
     main_git={k:v for k,v in b['main_git'].items() if k!='status'},
     branch_git={k:v for k,v in b['branch_git'].items() if k!='status'},
     isolated_git={k:v for k,v in b['isolated_git'].items() if k!='status'},
     manifests=b['verified_manifests'],baseline_sha256=sha(E/'00_baseline.json'),
     plan_sha256=sha(E/'00_EXPERIMENT_PLAN.md'),scope_sha256=sha(E/'00_SCOPE_AND_ACCEPTANCE.md')))
ab=load(E/'02_shadow_ab_results.json');summary={}
for sid,r in ab['sessions'].items():
    summary[sid]=dict(original_TLS_valid=r['original_TLS_valid'],original_recommended=r['original_recommended'],
       all_fit_rows=r['baseline']['full']['count'],fixed_holdout_ordinals=[h['ordinal'] for h in r['baseline']['holdouts']],
       baseline_holdout_P95_mm={str(h['ordinal']):{i:s['p95_m']*1000 for i,s in h['regions'].items()} for h in r['baseline']['holdouts']},
       variants={k:dict(eligibility=v['eligibility'],
           full_FIT_RMS_mm=v.get('full',{}).get('rms_m',0)*1000 if 'full' in v else None,
           holdout_P95_mm={str(h['ordinal']):{i:s['p95_m']*1000 for i,s in h['regions'].items()} for h in v['holdouts']},
           holdout_failed_regions=[(h['ordinal'],i) for h in v['holdouts'] for i,s in h['regions'].items() if s['status']!='PASS'],
           all_rows_retained=v['all_fit_rows_retained'],holdout_in_fit=v['holdout_in_fit']) for k,v in r['variants'].items()},
       independent_SVD_difference_m=r['independent_SVD_max_FIT_residual_difference_m'])
save('04_audit_summary.json',dict(sessions=summary,target=ab['target'],outcome='BLOCKED',
     reason='Physical root cause not uniquely identified, no admissible correction; numeric/model mechanism != physical cause',
     physical_GT_available=False,local_original_bag_available=False,new_repair=False,
     original_profile=ab['safety_profile'],target_effective_TLS='BLOCKED',
     regression_command=load(E/'03_regression_command.json'),search_control=load(E/'03_search_paired.json')))
pair=load(E/'03_search_paired.json')
note='\n\n## 性能对照完成补记（独审前）\n\n'
note+='初次单样本时延较旧中位数高，已按同进程当前原09C源码与本轮副本配对三次交替复验；源码逐SHA完全相同，完整结果精确相同。\n\n'
note+='| 路径 | 当前原09C中位秒 | CL2-10复用副本中位秒 |\n|---|---:|---:|\n'
for r in pair['rows']:note+=f"| {r['case']} | {r['median_sec']['control_09c']:.4f} | {r['median_sec']['local_10']:.4f} |\n"
note+='\n原单样本4.038/7.183秒保留，不删除较慢结果。当前同环境对照未显示新增算法复杂度或实现退化；这不证明时钟/热/调度原因，原因未测，不提供生产时延保证。最坏仍O(n⁴)、内存O(n²)，板端NOT_RUN。详见03_search_paired.json/原始日志。\n'
with (E/'01_root_cause.md').open('a',encoding='utf8') as stream:stream.write(note)
with (E/'03_regression_results.txt').open('a',encoding='utf8') as stream:
    stream.write('\nContemporaneous original-09C vs local copy paired search controls:\n'+(E/'03_search_paired.json').read_text(encoding='utf8'))
print('PRE_AUDIT_GUARD_PASS',len(b['guards']),len(runtime))
