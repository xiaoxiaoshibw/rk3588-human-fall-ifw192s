"""Separate protected research inputs/code from unexplained unrelated capture removals."""
import sys,json
from pathlib import Path
root=Path('D:/Code/ldiar');here=root/'sidequests/human_fusion_lab_next/pointset/r01';sys.path.insert(0,str(here))
from actions import sha,read,dump,load
e=Path(__file__).resolve().parent;b=read(e/'BASELINE_BEFORE.json');full=read(e/'FINAL_PRESERVATION.json');cat=read(here/'action_output/catalog.json')
assert not full['errors'] and full['head_before']==full['head_after']
prefixes=['src/','ML/','pc_apps/console/','sidequests/human_fusion_lab_next/pointset/r01/action_output/',
          'sidequests/human_fusion_lab_next/pointset/r01/action_research_r2/','sidequests/human_fusion_lab_next/pointset/r01/output/']
prefixes += ['captures/remote/'+r['session_id']+'/' for r in cat['sessions']]
allowed={'sidequests/human_fusion_lab_next/pointset/r01/'+n for n in ['app.js','index.html','server.py','README.md']}
protected=[]
for name in b['files']:
    norm=name.replace('\\','/')
    if any(norm.startswith(p) for p in prefixes) or norm in ['sidequests/human_fusion_lab_next/pointset/r01/'+n for n in ['core.py','actions.py','config.yaml','config_actions.yaml','experiment_actions.py','config_research_r2.json']]: protected.append(name)
missing=set(full['missing']);changed={r['path']:r for r in full['changed']}
assert not missing & set(protected)
assert not any(n in changed and not changed[n]['authorized'] for n in protected)
sources={}
for r in cat['sessions']:
    hashes=load(r['session_id'])[2];assert hashes==r['source_sha256'];sources[r['session_id']]=hashes
frozen=read(e/'FROZEN_EXPERIMENT.json');assert all(sha(here/n)==h for n,h in frozen.items())
dump(e/'SCOPED_PRESERVATION.json',{'status':'PASS','protected_previous_files':len(protected),'sources':sources,
    'old_outputs_production_and_gt_unchanged':True,'full_tree_status':full['status'],'unexplained_missing_files':len(full['missing']),
    'missing_remote':sum(n.replace('\\','/').startswith('captures/remote/') for n in missing),
    'missing_leveled':sum(n.replace('\\','/').startswith('captures/leveled/') for n in missing),
    'note':'Missing unrelated capture artifacts remain reported; attribution UNKNOWN pending user context. No restoration/deletion performed.'})
(e/'PRESERVATION_ATTEMPT_01.json').write_bytes((e/'FINAL_PRESERVATION.json').read_bytes())
print('scope PASS',len(protected),'unexplained global missing',len(missing),flush=True)
