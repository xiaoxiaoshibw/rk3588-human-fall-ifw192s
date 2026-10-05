import datetime, hashlib, json, pathlib, subprocess
root = pathlib.Path(__file__).resolve().parents[4]
out = pathlib.Path(__file__).parent
accept = root / 'docs/human_fall/GL04_ACCEPTANCE.md'
statuses = dict(V01='PASS',V02='FAIL',V03='FAIL',V04='NOT_RUN',V05='FAIL',V06='FAIL',V07='FAIL',V08='FAIL',V09='FAIL',V10='BLOCKED',D01='NOT_RUN',
                M01='FAIL',M02='PASS',M03='NOT_RUN',M04='FAIL',M05='NOT_RUN',M06='FAIL',M07='FAIL',M08='FAIL',M09='FAIL',M10='PASS',M11='NOT_RUN')
text = accept.read_text(encoding='utf-8')
lines = text.splitlines()
for i, line in enumerate(lines):
    for key, value in statuses.items():
        if line.startswith('| ' + key + ' |'):
            parts = line.rsplit('|', 2)
            lines[i] = parts[0] + '| ' + value + ' |'
            break
conclusion = '''

## R5独立结果与R6服务阻塞 / 2026-10-03

固定判据v1不变，仅更新现行结果列。R5 **REWORK**：原R4的5+2FAIL已闭合，四源码SHA匹配交接/回传，因此原Codex90/92/91独立证据仍适用；95/97及真实browser补查揭示source physical fall/失效track、坐标token/单位及fixture缺绑定。全V/C/M结果和六图见[R5正式复审](evidence/2026-10-03_gl04_r5/CODEX_REVIEW.md)。V04真实DPR变化/确定camera退化NOT_RUN，M05 pending真实browser未跑；V10/D01分层保留。

后续唯一[R6集中提示词](AI_PROMPT_GL04_OPENCODE_R6.md)/[设计矩阵](evidence/2026-10-03_gl04_r6/PLAN_REVIEW.md)已准备，指定model/default DB无工具probe55.313秒超时、exit1，[服务BLOCKED](evidence/2026-10-03_gl04_r6/CODEX_BLOCKED.md)。R6尚未启动生产写入者，不计算法失败轮次。当前正式源码未获审不并入，GL05/部署/采集/板端网络未授权；外部Q/E/帮助/HR/重组及旧证据保持。
'''
if '## R5独立结果与R6服务阻塞' not in text:
    accept.write_text('\n'.join(lines) + '\n' + conclusion,encoding='utf-8')

baseline = json.loads((out / '96_codex_scope_before.json').read_text(encoding='utf-8'))
allowed_docs = {
    'docs/human_fall/WORKFLOW.md','docs/human_fall/DISPATCH.md','docs/human_fall/REVIEW_LOG.md',
    'docs/human_fall/GL04_ACCEPTANCE.md','docs/human_fall/returns/GL-04.md',
    'docs/human_fall/tickets/GL-04_webui_level_view.md','docs/human_fall/CLI_RECOVERY.md'
}
changed, unexpected, missing = [], [], []
for rel, before in baseline['files'].items():
    p = root / rel
    if not p.exists(): missing.append(rel); continue
    now = hashlib.sha256(p.read_bytes()).hexdigest()
    if now != before:
        changed.append(rel)
        if rel not in allowed_docs and not rel.startswith('docs/human_fall/evidence/2026-10-03_gl04_r5/browser_01/'):
            unexpected.append(rel)
source = {rel:hashlib.sha256((root / rel).read_bytes()).hexdigest() for rel in baseline['files'] if rel.startswith(('webui/','src/'))}
submission = json.loads((out / '00_before_manifest.json').read_text(encoding='utf-8'))
frozen_submit_changes = []
frozen_submit_checked = 0
expected_unreadable = []
for entry in submission['files']:
    rel = entry['path']
    if rel.startswith(('src/','config/','webui/human_fall/','webui/dist/')):
        frozen_submit_checked += 1
        p = root / rel
        try:
            live_sha = hashlib.sha256(p.read_bytes()).hexdigest()
        except OSError as error:
            if 'error' in entry:
                expected_unreadable.append({'path':rel,'baseline_error':entry['error'],'live_error':str(error)})
            else:
                frozen_submit_changes.append(rel)
        else:
            if live_sha != entry.get('sha256'):
                frozen_submit_changes.append(rel)
test_bytes = (root / 'webui/human_fall_preview/human_fall_lib.test.js').read_bytes()
prefix = test_bytes[:test_bytes.index(b'/* ---- GL-04 R5 additions')].rstrip(b'\r\n')
tail = test_bytes[test_bytes.rfind(b'console.log('):].rstrip(b'\r\n')
r4_test_sha = '50865c9ad4184606ba5518877657270c2dd0215a651bb38bdd1abeae4cb339a1'
original_44_preserved = any(hashlib.sha256(prefix+nl*n+tail+nl*m).hexdigest()==r4_test_sha for nl in (b'\n',b'\r\n') for n in range(1,5) for m in range(1,3))
result = {'time':datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),
          'head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(),
          'baseline_files':len(baseline['files']),'checked_source_files':len(source),'changed':changed,
          'unexpected_changes':unexpected,'missing':missing,'source_sha256':source,
          'pre_r5_frozen_files_checked':frozen_submit_checked,'pre_r5_frozen_changes':frozen_submit_changes,
          'expected_unhashable_windows_symlinks':expected_unreadable,
          'original_44_reconstructed_r4_sha_match':original_44_preserved,'acceptance_statuses':statuses}
(out / '98_codex_final_verify.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in result.items() if k!='source_sha256'},ensure_ascii=False,indent=2))
raise SystemExit(1 if unexpected or missing or frozen_submit_changes or not original_44_preserved else 0)
