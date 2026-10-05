import datetime, hashlib, json, pathlib, subprocess
p=pathlib.Path(__file__).resolve().parent
root=p.parents[3]
files=[]
for raw in subprocess.check_output(['git','ls-files','-z','--cached','--others','--exclude-standard'],cwd=root).split(b'\0'):
    if not raw: continue
    name=raw.decode('utf-8')
    try: files.append({'path':name,'sha256':hashlib.sha256((root/name).read_bytes()).hexdigest()})
    except OSError as e: files.append({'path':name,'error':str(e)})
obj={'time':datetime.datetime.now().astimezone().isoformat(),
     'head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(),
     'branch':subprocess.check_output(['git','branch','--show-current'],cwd=root,text=True).strip(),
     'status':subprocess.check_output(['git','status','--short'],cwd=root,text=True,encoding='utf-8'), 'files':files}
out=p/'00_before_manifest.json'
if out.exists(): raise RuntimeError('Preserve existing baseline evidence')
out.write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'head':obj['head'],'files':len(files),'unreadable':[r['path'] for r in files if 'error' in r]},ensure_ascii=False))
