import datetime,hashlib,json,pathlib,subprocess
root=pathlib.Path(__file__).resolve().parents[4]
out=pathlib.Path(__file__).parent/'00_resume_before_manifest.json'
if out.exists(): raise SystemExit('Baseline exists; do not overwrite')
paths=set()
for prefix in ('src','config','webui','docs/human_fall'):
    for p in (root/prefix).rglob('*'):
        if '__pycache__' in p.parts: continue
        try:
            if p.is_file(): paths.add(p)
        except OSError:
            if p.name=='CMakeLists.txt': paths.add(p)
paths.update(root/p for p in ('AGENTS.md','CLAUDE.md'))
records={}
for p in sorted(paths):
    try: record={'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
    except OSError as e: record={'error':str(e)}
    records[p.relative_to(root).as_posix()]=record
r={'time':datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),'branch':subprocess.check_output(['git','branch','--show-current'],cwd=root,text=True).strip(),'head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(),'status':subprocess.check_output(['git','status','--porcelain=v1','-uall'],cwd=root,text=True),'files':records}
out.write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'head':r['head'],'files':len(records),'preview_sha':{k:v for k,v in records.items() if k.startswith('webui/human_fall_preview/')}},ensure_ascii=False))
