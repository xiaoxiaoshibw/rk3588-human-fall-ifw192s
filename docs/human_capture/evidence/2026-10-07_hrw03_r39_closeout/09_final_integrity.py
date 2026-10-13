"""Separate this writer's authorized delta from observed concurrent workspace changes."""
import hashlib
import json
from pathlib import Path

OUT = Path(__file__).parent
ROOT = OUT.parents[3]
def read(name):
    return json.loads((OUT / name).read_text(encoding='utf-8'))
def sha(p):
    h = hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()

baseline = read('00_baseline.json')['files']
scope = read('09_scope_check.json')
bindings = read('09_input_source_sha.json')
allowed = {'pc_apps/human_replay/human_pipe_lib.js', 'docs/human_capture/HUMAN_RECOGNITION_NEXT_STAGE_PLAN.md',
           'docs/human_capture/README.md', 'docs/human_capture/returns/HR-W03.md', 'docs/human_capture/tickets/HR-W03-R39-CLOSEOUT.md'}
changed = {p:v for p,v in scope['changed'].items() if p not in allowed}
added = {p:v for p,v in scope['added'].items() if p not in allowed}
protected = {p:v for p,v in baseline.items() if p.startswith('docs/human_capture/evidence/') or
             p.startswith('captures/registration/') or p in [v['path'] for v in bindings['input_files']] or
             p in ['pc_apps/human_replay/human_replay_lib.js', 'pc_apps/human_replay/registration.js', 'pc_apps/human_replay/registration_method.js',
                   'docs/human_capture/evidence/2026-10-07_hrw03_r37_productionization/06_test_matrix.md', 'docs/human_capture/W03_R3_ACCEPTANCE.md']}
errors = []
for p,v in protected.items():
    target = ROOT / p
    if not target.is_file() or sha(target) != v.get('sha256'):
        errors.append(p)
assert not errors, errors
actual_source_sha = sha(ROOT / 'pc_apps/human_replay/human_pipe_lib.js')
assert actual_source_sha == bindings['current_code']['files']['pc_apps/human_replay/human_pipe_lib.js']
before = (OUT / 'baseline_code/pc_apps/human_replay/human_pipe_lib.js').read_bytes()
after = (ROOT / 'pc_apps/human_replay/human_pipe_lib.js').read_bytes()
expected = before.replace(b'clusters_after - clusters_before;', b'clusters_after.length - clusters_before.length;')
expected = expected.replace(b'clusters_before_cleanup: clusters_before,', b'clusters_before_cleanup: clusters_before.length,')
expected = expected.replace(b'clusters_after_cleanup: clusters_after,', b'clusters_after_cleanup: clusters_after.length,')
assert after == expected, 'production must be the exact three-expression change, including newline preservation'
result = {'result':'PASS', 'protected_original_files':len(protected), 'protected_mismatch':errors,
          'production_exact_three_expression_delta':True, 'current_source_sha':actual_source_sha,
          'observed_changes_outside_this_writer_scope':changed, 'observed_additions_outside_this_writer_scope':added,
          'outside_scope_policy':'preserved; authorship not inferred; no reset/restore/delete/rebuild of these files',
          'GT_schema_regression':read('05_gt_schema_regression.json'),
          'browser_QA':'three canvases and local point cloud displayed; 31 point rows and 257 confirmation rows; no captured browser errors/warnings at initial load; no human semantic labels supplied'}
with (OUT / '09_final_integrity.json').open('x', encoding='utf-8') as f:
    json.dump(result, f, ensure_ascii=False, indent=2)
md = f'''# 收尾完整性与观察到的并发变化

**PASS：{len(protected)} 个受保护原文件逐SHA相同**，包括本实验两会话meta/bin、绑定leveling文件、registration四文件及既有历史证据/冻结数学/验收表。PL仍精确只有三个诊断表达式的改动，包含原换行保持，SHA={actual_source_sha}。

**全仓并非只发生本轮授权变化。** `09_scope_check.json` 观察到另有 {len(changed)} 个范围外原文件变更/消失，以及 {len(added)} 个范围外新增文件。这些路径从未由本轮脚本/命令写入，不能把全仓变化冒称本writer所为或冒称全仓SHA未变；也不推测操作者身份。已保留现状，没有恢复或删除。

范围外路径包含其他三份旧会话 `cap_20261002_163621` / `cap_20261002_165321` / `cap_20261002_233210` 的文件消失、新会话 `cap_20261007_154545`、Console构建/发布、PC capture/fetch、HC和WebUI文件。精确前后SHA/删除状态见 `09_final_integrity.json` / `09_scope_check.json`。本轮绑定的 `223757` 与 `203349` 未受这些变化影响，已单独重核。

新增GT格式回归6项PASS：UNKNOWN31保持未闭合；错source、artifact、seq、重复point、自动ground标签均拒绝（预期exit1）。测试夹具仅在临时目录、标记SYNTHETIC_SCHEMA_TEST_ONLY，不是人工GT，不能据此放行。

viewer初始浏览器渲染已查看，三窗点云/31点表/257变化行可见，初载无console warning/error。未生成实际人工语义标签；实体脚腿/地面仍UNKNOWN。最终状态仍REWORK_REQUIRED。
'''
with (OUT / '09_final_integrity.md').open('x', encoding='utf-8') as f:
    f.write(md)
for target in [OUT / '08_final_closeout.md', ROOT / 'docs/human_capture/returns/HR-W03.md']:
    with target.open('a', encoding='utf-8', newline='\n') as f:
        f.write('\n\n### 收尾补记（只追加，保留原提交正文）\n\n'
                f'`09_final_integrity.json/md`：受保护原文件{len(protected)}项SHA一致、PL精确三行改动；另观测到范围外{len(changed)}个原文件变化/消失及{len(added)}个新增，包含其他会话和Console/HC文件，均保留，不能声称全仓未变。本实验绑定输入与历史证据不受影响。GT格式回归6项PASS但仅synthetic，真人GT仍BLOCKED。\n')
print(json.dumps({'result':'PASS','protected_original_files':len(protected),'outside_changed':len(changed),'outside_added':len(added)}))
