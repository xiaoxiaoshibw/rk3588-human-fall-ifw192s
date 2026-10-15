"""Validate a plan's concrete session/annotation/compute budgets without development."""
import json
from pathlib import Path
E=Path(__file__).resolve().parent
def read(name):return json.loads((E/name).read_text(encoding='utf-8'))
data=read('DATA_PREFLIGHT_V2.json');split=read('EXPERIMENT_SPLIT_V2.json');queue=read('ANNOTATION_QUEUE_V2.json');budget=read('EXPERIMENT_BUDGET_V2.json')
counts={r['sid']:r['frame_count'] for r in data['checks']}
assert len(data['checks'])==9 and sum(counts.values())==2206
assert sum(counts[s] for s in split['dev_sids'])==960
assert sum(counts[s] for s in split['comparison_sids'])==974
assert not set(split['dev_sids'])&set(split['comparison_sids'])
for fold in split['folds']:
    assert set(fold['train_sids'])|set(fold['validation_sids'])==set(split['dev_sids'])
    assert not set(fold['train_sids'])&set(fold['validation_sids'])
for sid,task in queue['tasks'].items():
    core,extra=task['core_review'],task['proposal_extra']
    assert len(set(core))==len(core) and len(set(extra))==len(extra)
    assert not set(core)&set(extra)
    assert all(type(fi) is int and 0<=fi<counts[sid] for fi in core+extra)
assert sum(len(t['core_review']) for t in queue['tasks'].values())==282
assert sum(len(t['proposal_extra']) for t in queue['tasks'].values())==192
assert sum(len(t['core_review'])+len(t['proposal_extra']) for t in queue['tasks'].values())==474
assert set(split['empty_fit'])|set(split['empty_cal'])|set(split['empty_report'])==set(range(272))
assert not set(split['empty_fit'])&set(split['empty_cal']) and not set(split['empty_fit'])&set(split['empty_report']) and not set(split['empty_cal'])&set(split['empty_report'])
assert 3*2*4==budget['screen_jobs']==24
assert 3*len(budget['final_seeds'])==budget['final_family_jobs']==9
assert budget['screen_jobs']+budget['final_family_jobs']+budget['training_ablation_jobs']==36
assert (24*30+12*90)/60==budget['cumulative_training_wall_hours_max']==30
print('Plan contract PASS: 18 files / 960+974 / 474 tasks with282 core / 4 sid folds / 36 jobs<=30h; implementation/training NOT_RUN')

assert sum(len(t['secondary_review']) for t in queue['tasks'].values())==66
for sid,t in queue['tasks'].items():assert set(t['secondary_review'])<=set(t['core_review'])
assert budget['screen_samples_per_epoch']==72 and budget['screen_validation_samples']==24 and budget['final_samples_per_epoch']==96
assert read('OUTPUT_BUDGET_V2.json')['total_GiB']<80
assert {119,124,140,195,232}<=set(queue['tasks']['cap_20261013_082623']['core_review'])
print('V2 PASS: OOF96 / compare96 / empty90 roles; secondary66; hard-frame core; profile+storage budgets; no implementation/training')
