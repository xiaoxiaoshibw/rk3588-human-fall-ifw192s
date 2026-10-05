import hashlib, json, pathlib, subprocess
root = pathlib.Path(__file__).resolve().parents[4]
paths = set()
for prefix in ('webui', 'src/human_fall_detection', 'src/human_follow_calibration', 'docs/human_fall'):
    paths.update(p for p in (root / prefix).rglob('*') if p.is_file() and '__pycache__' not in p.parts)
paths.update(root / p for p in ('AGENTS.md','CLAUDE.md'))
record = {'branch':subprocess.check_output(['git','branch','--show-current'],cwd=root,text=True).strip(),
          'head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(),
          'status':subprocess.check_output(['git','status','--porcelain=v1','-uall'],cwd=root,text=True),
          'files':{p.relative_to(root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(paths)}}
(pathlib.Path(__file__).parent / '96_codex_scope_before.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'branch':record['branch'],'head':record['head'],'files':len(paths)}))
