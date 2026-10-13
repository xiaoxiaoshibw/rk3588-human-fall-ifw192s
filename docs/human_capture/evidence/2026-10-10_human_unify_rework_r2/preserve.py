from pathlib import Path
import hashlib,json
root=Path.cwd();base=root/'docs/human_capture/evidence/2026-10-10_human_unify_rework_r2'
old=json.loads((base/'all_sha_before.json').read_text(encoding='utf-8-sig'))
allowed=['pc_apps/human_core/','docs/human_capture/evidence/2026-10-10_human_unify_rework_r2/']
allowed_files=['docs/human_capture/README.md','docs/human_capture/returns/HUMAN-UNIFY-R1.md']
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for block in iter(lambda:f.read(4*1024*1024),b''):h.update(block)
 return h.hexdigest()
result={'checked':0,'allowed_changes':[],'outside_changes':[],'symlinks_not_followed':[]}
for item in old:
 p=Path(item['path']);relative=p.relative_to(root).as_posix()
 if not item.get('sha256'):
  result['symlinks_not_followed'].append(relative);continue
 result['checked']+=1
 actual=sha(p) if p.is_file() else None
 if actual!=item['sha256'].lower():
  entry={'path':relative,'before':item['sha256'].lower(),'after':actual}
  dest='allowed_changes' if relative in allowed_files or any(relative.startswith(x) for x in allowed) else 'outside_changes'
  result[dest].append(entry)
result['submitted_core_changes']=[]
submitted=json.loads((base/'submitted_source_sha.json').read_text(encoding='utf-8-sig'))
for p,h in submitted.items():
 if sha(root/p)!=h:result['submitted_core_changes'].append(p)
result['status']='PASS' if not result['outside_changes'] and not result['submitted_core_changes'] else 'BLOCKED'
(base/'preservation_01.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print('preservation',result['status'],'checked',result['checked'],'allowed',len(result['allowed_changes']),'outside',len(result['outside_changes']),'submitted',result['submitted_core_changes'])
