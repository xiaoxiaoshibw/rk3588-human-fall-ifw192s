"""Final hashes of source/GT/model/current inputs and old outputs; cache removals stay in global audit."""
import sys
from pathlib import Path
root=Path('D:/Code/ldiar');here=root/'sidequests/human_fusion_lab_next/pointset/r01';sys.path.insert(0,str(here))
from actions import read,dump,sha,load
e=Path(__file__).resolve().parent;b=read(e/'BASELINE_BEFORE.json');cat=read(here/'action_output/catalog.json')
prefixes=['src/','ML/','sidequests/human_fusion_lab_next/pointset/r01/action_output/','sidequests/human_fusion_lab_next/pointset/r01/action_research_r2/','sidequests/human_fusion_lab_next/pointset/r01/output/']
prefixes += ['captures/remote/'+r['session_id']+'/' for r in cat['sessions']]
checked=0;bad=[]
for name,rec in b['files'].items():
    norm=name.replace('\\','/')
    if '__pycache__/' in norm or '/.pytest_cache/' in norm:continue
    if not any(norm.startswith(p) for p in prefixes) and norm not in ['sidequests/human_fusion_lab_next/pointset/r01/'+n for n in ['core.py','actions.py','config.yaml','config_actions.yaml','experiment_actions.py','config_research_r2.json']]:continue
    p=root/name
    if not p.exists():bad.append({'path':name,'status':'MISSING'})
    elif sha(p)!=rec['sha256']:bad.append({'path':name,'status':'HASH_CHANGED'})
    checked+=1
sources={r['session_id']:load(r['session_id'])[2] for r in cat['sessions']}
assert all(sources[r['session_id']]==r['source_sha256'] for r in cat['sessions'])
dump(e/'FINAL_CORE_AUDIT.json',{'status':'PASS' if not bad else 'FAIL','hash_checked_files':checked,'violations':bad,'sources':sources,
    'scope':'production source/models/GT/current nine inputs/R1 and R2 output; excludes interpreter/test caches. Global missing assets/evidence remain separately FAIL.'})
print('CORE FINAL',checked,bad,flush=True)
assert not bad
