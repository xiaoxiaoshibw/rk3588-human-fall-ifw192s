"""Verify closure documents and immutable source/evidence against review baseline."""
import hashlib
import json
import subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[5]
OUT=Path(__file__).resolve().parent
baseline=json.loads((OUT/'00_baseline.json').read_text(encoding='utf-8'))
allowed={'docs/human_fall/'+name for name in (
    'GL03_ACCEPTANCE.md','returns/GL-03.md','REVIEW_LOG.md','WORKFLOW.md',
    'DISPATCH.md','CLI_RECOVERY.md','README.md','tickets/GL-03_candidates_geometry.md',
    'tickets/INDEX.md')}
changed={};unexpected=[]
for name,old in baseline['files'].items():
    h=hashlib.sha256()
    with (ROOT/name).open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    digest=h.hexdigest()
    if digest!=old:
        changed[name]={'before':old,'after':digest}
        if name not in allowed:unexpected.append(name)
head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT).decode().strip()
assert not unexpected,unexpected
external_paths=[]
if head!=baseline['head']:
    external_paths=subprocess.check_output(['git','diff','--name-only',baseline['head'],head],cwd=ROOT).decode('utf-8').splitlines()
    assert all(name.startswith(('docs/human_capture/','pc_apps/human_replay/'))
               for name in external_paths),external_paths
accept=(ROOT/'docs/human_fall/GL03_ACCEPTANCE.md').read_text(encoding='utf-8')
assert '## 当前独立结果 / R7 /' in accept
assert '| G03 | PASS |' in accept.split('## 当前独立结果 / R7 /')[1]
receipt=(ROOT/'docs/human_fall/returns/GL-03.md').read_text(encoding='utf-8')
assert '# Codex GL03 R7 独立复审 /' in receipt
for name in allowed:
    text=(ROOT/name).read_text(encoding='utf-8')
    assert '\ufffd' not in text,name
    # Historical appended records can contain old broken links; check our new section.
    if name.endswith('returns/GL-03.md'):
        text=text.split('# Codex GL03 R7 独立复审 /',1)[1]
    if name.endswith('REVIEW_LOG.md'):
        text=text.split('## Codex GL03 R7 独立复审 /',1)[1]
    import re
    for target in re.findall(r'\]\(([^)]+)\)',text):
        if '://' in target or target.startswith('#'):continue
        target=target.split('#')[0]
        assert ((ROOT/name).parent/target).exists(),(name,target)
result={'head_before':baseline['head'],'head_after':head,
        'external_head_paths':external_paths,'source_and_prior_evidence_unchanged':True,
        'allowed_status_documents_changed':changed,'unexpected':unexpected,
        'all_local_links_exist':True,'acceptance_version':'v1',
        'no_new_fail':'R8 not dispatched','GL04':'WAIT_AUTHORIZATION'}
(OUT/'16_final_verify.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print('PASS: source/old evidence preserved; status changes limited to',len(changed),'documents; external HEAD paths',external_paths)
