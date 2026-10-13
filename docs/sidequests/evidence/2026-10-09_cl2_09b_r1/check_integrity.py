"""Frozen inputs guarded, main concurrent state recorded as context only."""
from prepare import E,R,I,load,save,sha,inventory,H
import subprocess
baseline=load(E/'01_baseline.json')
def check(path,digest):
    actual=sha(path);assert actual==digest,path
    return dict(path=str(path),expected=digest,actual=actual,match=True)
checks=[]
for x in baseline['source_bindings']:
    checks.extend([check(x['origin'],x['sha256']),check(x['frozen'],x['sha256'])])
for file in ['extra_fixture_bindings.json','validation_fixture_binding.json']:
    x=load(E/file)
    items=x['bindings'] if 'bindings' in x else [x]
    for item in items:
        checks.append(check(item['origin'],item['sha256']))
        name=__import__('pathlib').Path(item['origin']).name
        checks.append(check(E/'frozen'/name,item['sha256']))
for path,digest in {**baseline['historical_files'],**baseline['input_files']}.items():checks.append(check(path,digest))
assert inventory(I)==baseline['isolated_all_files']
candidate={str(p.relative_to(E/'candidate')):sha(p) for p in (E/'candidate').rglob('*') if p.is_file()}
frozen={str(p.relative_to(E/'frozen')):sha(p) for p in (E/'frozen').rglob('*') if p.is_file()}
assert set(candidate)==set(frozen)
different=[k for k in candidate if candidate[k]!=frozen[k]]
assert different==['floor_sheet.py'],different
assert sha(R/'pc_apps/human_replay/floor_sheet.py')==baseline['main_floor_sheet_sha256']
now=inventory(R);before=baseline['main_all_files']
changes=[dict(path=k,before=before.get(k),after=now.get(k)) for k in sorted(set(before)|set(now)) if before.get(k)!=now.get(k)]
ret=H.parent/'returns/CLUSTER-01.md';old=(E/'return_before.bin').read_bytes();assert ret.read_bytes().startswith(old)
save('09_integrity.json',dict(PASS=True,checks=checks,isolated_full_tree_unchanged=True,
    candidate_only_changed_files=different,candidate_files=candidate,frozen_files=frozen,
    current_main_floor_sheet_unchanged=True,main_context_changes=changes,
    main_HEAD_after=subprocess.check_output(['git','rev-parse','HEAD'],cwd=R,text=True).strip(),
    return_append_only=ret.read_bytes().startswith(old),scope='Main all-file changes recorded; only immutable isolated inputs authorize this run, not whole live main freeze.'))
print('FROZEN_INPUT_AND_ONLY_SELECTOR_CHANGED_PASS',len(checks),'main context changes',len(changes))
