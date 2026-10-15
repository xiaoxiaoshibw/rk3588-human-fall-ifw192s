import sys
import subprocess
from pathlib import Path
H=Path('D:/Code/ldiar/sidequests/human_fusion_lab_next/pointset/r01');sys.path.insert(0,str(H))
from research_actions import E, ROOT, RESULT, read, dump, sha

before=read(E/'BASELINE_BEFORE.json');changed=[];missing=[];errors=[];unchanged=0
allowed={'sidequests/human_fusion_lab_next/pointset/r01/'+n for n in ['app.js','index.html','server.py','README.md']}
allowed.update(['docs/human_capture/README.md','docs/human_fall/WORKFLOW.md','docs/human_capture/returns/HFUS-POINTSET-ACTIONS-01.md'])
for i,(name,record) in enumerate(before['files'].items()):
    path=ROOT/name
    try:
        value=sha(path)
        if value!=record['sha256']:
            changed.append({'path':name,'before':record['sha256'],'after':value,'in_authorized_scope':path.relative_to(ROOT).as_posix() in allowed})
        else:unchanged+=1
    except FileNotFoundError:missing.append(name)
    except OSError as e:errors.append({'path':name,'error':str(e)})
    if i%3000==0:print('PRESERVATION',i,len(before['files']),flush=True)
head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
dump(E/'FINAL_PRESERVATION.json',{'baseline_files':len(before['files']),'unchanged_files':unchanged,'changed':changed,
     'missing':missing,'errors':errors,'head_before':before['head'],'head_after':head,'head_unchanged':head==before['head'],
     'all_changes_authorized':all(r['in_authorized_scope'] for r in changed),
     'note':'Non-atomic all-file rehash, includes ignored/untracked. No reset or unrelated restoration.'})
assert not missing and not errors and head==before['head']
assert all(r['in_authorized_scope'] for r in changed)
outputs={str(p.relative_to(ROOT)):sha(p) for p in RESULT.rglob('*') if p.is_file()}
dump(E/'OUTPUT_SHA_FINAL.json',outputs)
external=read(E/'DIAGNOSTIC_MANIFEST.json');prior=Path(read(H/'action_output/RUN_MANIFEST.json')['config']['background_experiment'])
assert sha(prior/'background.npz')==external['background_sha256']
for sid,value in external['registrations'].items():assert sha(prior/(sid+'_registration.json'))==value
dump(E/'EXTERNAL_BACKGROUND_PRESERVATION.json',{'status':'PASS','background_sha256':external['background_sha256'],
     'registrations':external['registrations'],'physical_validity':'UNVERIFIED','different_empty_models_not_interchanged':True})
print('PRESERVED',unchanged,'unchanged;',len(changed),'authorized changes;',len(outputs),'new output hashes',flush=True)
