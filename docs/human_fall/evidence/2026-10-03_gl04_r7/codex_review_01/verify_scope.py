import datetime,hashlib,json,pathlib,subprocess
out=pathlib.Path(__file__).parent; root=out.parents[4]
b=json.loads((out.parent/'00_resume_before_manifest.json').read_text(encoding='utf-8'))
allowed={'webui/human_fall_preview/human_fall.js','webui/human_fall_preview/human_fall_lib.js','webui/human_fall_preview/human_fall_lib.test.js','webui/human_fall_preview/index.html','docs/human_fall/AI_PROMPT_GL04_OPENCODE_R6.md','docs/human_fall/WORKFLOW.md','docs/human_fall/DISPATCH.md','docs/human_fall/CLI_RECOVERY.md','docs/human_fall/returns/GL-04.md'}
allowed.update({'docs/human_fall/REVIEW_LOG.md','docs/human_fall/GL04_ACCEPTANCE.md','docs/human_fall/tickets/GL-04_webui_level_view.md'})
changed=[]; unexpected=[]; errors=[]; source={}
for rel, rec in b['files'].items():
    p=root/rel
    try: live=hashlib.sha256(p.read_bytes()).hexdigest()
    except OSError as e:
        if 'error' in rec: errors.append({'path':rel,'expected':True,'error':str(e)});continue
        unexpected.append(rel+' missing/unreadable');continue
    if rel.startswith('webui/human_fall_preview/'):source[rel]=live
    if live!=rec.get('sha256'):
        changed.append(rel)
        if rel not in allowed and not rel.startswith('docs/human_fall/evidence/2026-10-03_gl04_r6/'):
            unexpected.append(rel)
test=(root/'webui/human_fall_preview/human_fall_lib.test.js').read_bytes()
marker=b'test("sourcePositionQualified gates only explicit non-actual provenance'
match=False
if marker in test:
    pre=test[:test.index(marker)].rstrip(b'\r\n');tail=test[test.rfind(b'console.log('):].rstrip(b'\r\n')
    match=any(hashlib.sha256(pre+nl*n+tail+nl*m).hexdigest()==b['files']['webui/human_fall_preview/human_fall_lib.test.js']['sha256'] for nl in (b'\n',b'\r\n') for n in range(1,5) for m in range(1,3))
r={'time':datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),'head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(),'baseline_files':len(b['files']),'changed':changed,'unexpected':unexpected,'expected_unhashable':errors,'source_sha256':source,'original_54_reconstructed_r6_sha_match':match}
(out/'94_scope_verify.json').write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(r,ensure_ascii=False,indent=2));raise SystemExit(1 if unexpected or not match else 0)
