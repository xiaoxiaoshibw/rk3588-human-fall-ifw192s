"""Full previous-tree rehash; authorized UI/docs and live logs separately accounted."""
import hashlib,json,subprocess
from pathlib import Path
root=Path('D:/Code/ldiar');e=Path(__file__).resolve().parent
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(4<<20),b''):h.update(b)
    return h.hexdigest()
before=json.loads((e/'BASELINE_BEFORE.json').read_text(encoding='utf8'))
allowed={'sidequests/human_fusion_lab_next/pointset/r01/'+n for n in ['app.js','index.html','server.py','README.md']}
allowed.update(['docs/human_capture/README.md','docs/human_fall/WORKFLOW.md'])
changed=[];missing=[];errors=[];unchanged=0
for i,(name,r) in enumerate(before['files'].items()):
    p=root/name
    try:
        value=sha(p)
        if value==r['sha256']:unchanged+=1
        else:
            runtime=p.name in ['SERVER_STDERR.log','SERVER_STDOUT.log'] and '2026-10-14_hfus_pointset_actions_r2' in str(p)
            changed.append({'path':name,'before':r['sha256'],'after':value,'authorized':p.relative_to(root).as_posix() in allowed,'runtime_log':runtime})
    except FileNotFoundError:missing.append(name)
    except OSError as exc:errors.append({'path':name,'error':str(exc)})
    if i%6000==0:print('preservation',i,len(before['files']),flush=True)
head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()
status='PASS' if not missing and not errors and head==before['head'] and all(r['authorized'] or r['runtime_log'] for r in changed) else 'FAIL'
with (e/'FINAL_PRESERVATION.json').open('x',encoding='utf8') as f:
    json.dump({'status':status,'baseline_files':len(before['files']),'unchanged_files':unchanged,'changed':changed,'missing':missing,'errors':errors,'head_before':before['head'],'head_after':head,'scope':'tracked/untracked/ignored; non-atomic all-file rehash; allowed pages/docs and live old service logs explicitly separated'},f,ensure_ascii=False,indent=2)
out=root/'sidequests/human_fusion_lab_next/pointset/r01/action_research_r3'
with (e/'OUTPUT_SHA_FINAL.json').open('x',encoding='utf8') as f:json.dump({str(p.relative_to(root)):sha(p) for p in out.rglob('*') if p.is_file()},f)
binding=json.loads((e/'SOURCE_BINDINGS.json').read_text(encoding='utf8'))
prior=Path('D:/Code/radar/Plan/evidence/indoor-empty/20261014-low-pose-r01')
assert sha(prior/'background.npz')==binding['background_sha256']
assert all(sha(prior/(sid+'_registration.json'))==h for sid,h in binding['registration_sha256'].items())
print('preservation',status,'unchanged',unchanged,'changed',changed,flush=True)
assert status=='PASS'
