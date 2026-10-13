"""Audit supplement: distinguish estimator identity from numerical tolerance gates."""
import math
import numpy as np
from pathlib import Path
from prepare import E,load,save
from diagnostics import Q,svd

ab=load(E/'02_shadow_ab_results.json');catalog=load(E/'00_input_catalog.json');rows={}
for record in catalog['sessions']:
    r=ab['sessions'][record['sid']];report=load(Path(record['local'])/'report.json')
    with np.load(Path(record['local'])/'domain.npz',allow_pickle=False) as d:p=d['source_points'].copy()
    anchor=Q.rotation(report['config']['pitch_deg'],report['config']['roll_deg'])[2]
    n,offset=svd(p,anchor);variants={}
    for name,value in r['variants'].items():
        if 'normal_source' not in value:continue
        angle=math.degrees(math.acos(float(np.clip(np.array(value['normal_source'])@n,-1,1))))
        gap=abs(value['offset_source_m']-offset)
        variants[name]=dict(angle_to_unweighted_svd_deg=angle,offset_gap_m=gap,
             numeric_gap_gate_pass=angle<=Q.PROFILE['tls_svd_gap_max_deg'] and gap<=Q.PROFILE['tls_svd_offset_max_m'],
             current_raw_TLS_estimator_identity=False,
             holdout_failed_regions=[(h['ordinal'],i) for h in value['holdouts'] for i,s in h['regions'].items() if s['status']!='PASS'])
    rows[record['sid']]=variants
save('01_weighted_numeric_check.json',dict(sessions=rows,
    nuance='A weighted experiment is not the current equal-point TLS estimator. This does NOT imply every weighted variant fails the numerical gap tolerance.'))
target=rows[ab['target']]
note='\n\n## 数值一致门表述收窄补记（独审期间）\n\n'
note+='上文“两个正权重实验不满足raw TLS/SVD数值一致契约”须区分算法身份与数值门：二者都不是现行等点权TLS，但不能推断二者都超数值容差。独立SVD参数直接复算：\n\n'
note+='| 目标实验 | 对raw SVD角差 ° | offset差 m | 原数值差门 | 固定holdout问题 |\n|---|---:|---:|---|---|\n'
for key,v in target.items():
    note+=f"| {key} | {v['angle_to_unweighted_svd_deg']:.9f} | {v['offset_gap_m']:.12g} | {'PASS' if v['numeric_gap_gate_pass'] else 'FAIL'} | {v['holdout_failed_regions']} |\n"
note+='\n帧等权通过原数值差门，仍因72/ROI2原P95失败而不构成修复；ROI等权数值差门失败且144/ROI2失败。原结论BLOCKED不变。本补记纠正过宽措辞，不修改原AB结果、门控、输入或任何算法。\n'
with (E/'01_root_cause.md').open('a',encoding='utf8') as stream:stream.write(note)
print('WEIGHTED_NUMERIC_GATE_SUPPLEMENT',target)
