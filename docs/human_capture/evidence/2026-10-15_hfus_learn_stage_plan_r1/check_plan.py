"""Validate a plan's concrete session/annotation/compute budgets without development."""
import json
from pathlib import Path
E=Path(__file__).resolve().parent
def read(name):return json.loads((E/name).read_text(encoding='utf-8'))
data=read('DATA_PREFLIGHT.json');split=read('EXPERIMENT_SPLIT.json');queue=read('ANNOTATION_QUEUE.json');budget=read('EXPERIMENT_BUDGET.json')
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
