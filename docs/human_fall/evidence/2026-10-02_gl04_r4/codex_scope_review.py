import hashlib, json, pathlib, subprocess
p = pathlib.Path(__file__).resolve().parent
root = p.parents[3]
before = json.loads((p/'00_before_manifest.json').read_text(encoding='utf-8-sig'))
changed, errors = [], []
for record in before['files']:
    file = root / record['path']
    if 'sha256' not in record:
        errors.append(record)
        continue
    try:
        sha = hashlib.sha256(file.read_bytes()).hexdigest()
        if sha != record['sha256']:
            changed.append({'path': record['path'], 'before': record['sha256'], 'after': sha})
    except Exception as e:
        errors.append({'path': record['path'], 'error': str(e)})
scope = ['index.html','human_fall.js','human_fall_lib.js','human_fall_lib.test.js']
sources = {str(pathlib.PurePosixPath('webui')/folder/file):hashlib.sha256((root/'webui'/folder/file).read_bytes()).hexdigest()
           for folder in ['human_fall_preview','human_fall'] for file in scope}
old_test = subprocess.run(['git','show','HEAD:webui/human_fall_preview/human_fall_lib.test.js'],cwd=root,capture_output=True,check=True).stdout.decode()
current_test=(root/'webui/human_fall_preview/human_fall_lib.test.js').read_text()
# The original final summary line may move; every prior test block remains a contiguous exact prefix.
original_prefix=old_test[:old_test.rfind('console.log(')].replace('\r\n','\n')
out={'head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(),
     'changed_existing':changed,'baseline_unreadable':errors,'sources':sources,
     'old_assertions_prefix_unchanged':current_test.replace('\r\n','\n').startswith(original_prefix)}
(p/'94_scope_sha.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'head':out['head'],'changed':[x['path'] for x in changed],
                  'old_assertions_unchanged':out['old_assertions_prefix_unchanged'], 'unreadable_count':len(errors)},ensure_ascii=False))


