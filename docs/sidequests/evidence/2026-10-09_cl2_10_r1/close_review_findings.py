"""Close reviewer provenance/cohort gaps and qualify a numeric-gate statement."""
from pathlib import Path
from prepare import E,I,H,load,save,sha,copy_once

bindings=load(H/'docs/sidequests/evidence/2026-10-09_cl2_08_r1/input_bindings.json')['bindings']
paths=[I/'docs/sidequests/evidence/2026-10-09_cl2_07_r1/03_normal_comparison.json',
       I/'docs/sidequests/evidence/2026-10-09_cluster01_r1/01_leveling_index.json']
local=E/'inputs/cohort';local.mkdir()
bound=[]
for origin in paths:
    expected=next(row['sha256'] for row in bindings if Path(row['frozen'])==origin)
    assert sha(origin)==expected,str(origin)
    copy_once(origin,local/origin.name)
    bound.append(dict(origin=str(origin),copy=str(local/origin.name),sha256=expected,CL208_binding_verified=True))
norm=load(local/'03_normal_comparison.json');index=load(local/'01_leveling_index.json')
normal_valid={row['sid'] for row in norm if row['valid']}
completed=index['completed_sessions'];index_valid={row['sid'] for row in completed if row['estimators']['tls']['valid']}
catalog=load(E/'00_input_catalog.json');actual={row['sid'] for row in catalog['sessions']}
assert normal_valid==index_valid
assert actual=={row['sid'] for row in completed}==normal_valid|{catalog['target']}
assert len(normal_valid)==10
report=load(E/'inputs'/catalog['target']/'report.json')
save('04_cohort_integrity.json',dict(bindings=bound,candidate_capture_universe=sorted(actual),
    historical_valid_cases=sorted(normal_valid),executed_valid_cases=sorted(row['sid'] for row in catalog['sessions'] if row['original_TLS_valid']),
    cohort_membership_matches_original_cluster_index=True,cohort_membership_not_based_on_AB_outcomes=True,
    excluded=dict(template_job=index['template_job'],reason='Empty-scene reference/template is outside original CL2-07 normal-person comparison cohort, not dropped for new quality results.',
                  unrelated_captures='Older/other captures outside the fixed eleven CLUSTER-01 person sessions are not claimed as tested.'),
    report_selector_sha256=report['code_hashes']['floor_sheet.py'],
    copied_09C_selector_sha256=sha(E/'candidate/floor_sheet.py'),
    provenance='Historical report created with frozen selector; diagnostic TLS path uses original frozen ROI/domain, does not call floor_sheet. 09C selector only used by search/regression checks.'))
note='''

## 独审动作项关闭补记

四ROI的历史 `ground_identification=algorithm_candidate`、`ground_confirmed=false`，不是表面身份GT。局部平面贴合不构成地面身份或物理几何真值。

原报告的 selector SHA 是 dd1b58…（本轮 frozen/）；candidate/ 的 d0b3e3… 是09C，baseline/ 的066a81…是09B。原报告未用09C重新生成。本轮TLS诊断入口只调用 quality/estimators 和原冻结四ROI/源行，三版这些核心TLS/quality字节相同，**不调用 selector**；09C selector仅用于搜索回归/对照。执行源包复用09C不意味着报告生成器已升级或生产已集成。

T108的“全部10个既有TLS-valid”限定为 STEP0冻结的CL2-07正常人体会话比较集合，并非全部captures中的任意旧作业。新增 inputs/cohort 中的原03_normal_comparison与原01_leveling_index来自CL2-08既存binding，逐SHA复算后复制：原11人体会话集合=本轮11集合，原10个TLS-valid集合=本轮10个成功集合，无遗漏。空场模板/其他旧capture不在原预注册cohort内，不是按本轮结果剔除，不能冒称它们已做本轮试验。具体清单/排除范围及SHA在04_cohort_integrity.json。

帧等权是否过数值差门已由01_weighted_numeric_check.json和上个补记精确区分；非现行raw TLS算法身份并不蕴含必超数值容差。此项不影响72留出继续失败与BLOCKED。
'''
with (E/'01_root_cause.md').open('a',encoding='utf8') as stream:stream.write(note)
save('04_review_response.json',dict(provenance_clarified=True,ROI_identity_is_algorithm_candidate=True,
    fixed_cohort_full_membership_closed=True,weighted_numeric_statement_qualified=True,
    original_AB_sha256=sha(E/'02_shadow_ab_results.json'),runtime_sha256=sha(E/'candidate/floor_sheet.py'),
    new_algorithm_code=False,original_gates_or_inputs_changed=False))
print('REVIEW_ACTIONS_CLOSED',len(actual),len(normal_valid))
