from pathlib import Path
import hashlib
import json
import runpy

OUT = Path(__file__).parent
ROOT = OUT.parents[3]
ns = runpy.run_path(str(OUT / '00_baseline.py'))
rows = ns['inventory']()
baseline = json.loads((OUT / '00_baseline.json').read_text(encoding='utf-8'))['files']
changed = {p: {'before': baseline[p], 'after': rows.get(p)} for p in baseline if baseline[p] != rows.get(p)}
added = {p: rows[p] for p in rows if p not in baseline}
required = [p for p in baseline if p.startswith('docs/human_capture/evidence/2026-10-07_hrw03_r39_closeout/')]
required += [f'pc_apps/human_replay/{f}' for f in ['human_pipe_lib.js', 'human_replay_lib.js', 'registration.js', 'registration_method.js', 'human_detect.js', 'leveling.py', 'replay.js']]
required += ['docs/human_capture/evidence/2026-10-07_hrw03_r37_productionization/06_test_matrix.md', 'docs/human_capture/evidence/2026-10-07_hrw03_r37_productionization/01_coordinate_contract.md', 'docs/human_capture/evidence/2026-10-07_hrw03_r37_productionization/03_confidence_gate_design.md']
for prefix in ['captures/remote/cap_20261002_223757/', 'captures/remote/cap_20261004_203349/', 'captures/leveled/6bc5aabf8f0041ffa961758b4e84da94/', 'captures/leveled/c9712acad48c4fb7a78cb119c08d4cdb/', 'captures/registration/cap_20261002_223757__to__cap_20261004_203349/']:
    required += [p for p in baseline if p.startswith(prefix)]
required = sorted(set(required))
drift = {p: changed.get(p, {'reason': 'absent baseline'}) for p in required if p not in baseline or p in changed}
target = ROOT / 'docs/human_capture/returns/HR-W03.md'
before = (OUT / '05_return_before.txt').read_bytes()
append = (OUT / '05_return_append.md').read_bytes()
prefix_ok = target.read_bytes() == before + append and hashlib.sha256(before).hexdigest() == baseline['docs/human_capture/returns/HR-W03.md']['sha256']
outside = {p: v for p, v in changed.items() if p != 'docs/human_capture/returns/HR-W03.md'}
result = {'result': 'PASS' if not drift and prefix_ok else 'FAIL', 'protected_files': len(required), 'protected_drift': drift, 'return_append_only': prefix_ok,
          'changed_all': changed, 'added_outside_evidence': added, 'outside_observed_changes': outside,
          'production_writer_changes': 0, 'source_sha256': {p: rows[p] for p in required if p.startswith('pc_apps/human_replay/')},
          'limitations': 'No attribution of outside concurrent edits; they are retained. No device/physical conclusions.'}
with (OUT / '09_integrity.json').open('x', encoding='utf-8') as f:
    json.dump(result, f, ensure_ascii=False, indent=2)
md = f'''# 本轮完整性与范围

结果 **{result['result']}**：{len(required)}个受保护原文件（R39全目录、绑定session/leveling/registration、现行验收与坐标/gate契约、7个直接/关联源码）逐SHA相同；生产源码本轮零修改。HR-W03回传原字节前缀保留，仅追加本轮记录。

全树包括untracked/ignored可读文件已与00_baseline逐SHA对照；范围外原文件变化{len(outside)}项、新增{len(added)}项，详见09_integrity.json，保持原状，不推测操作者。整个本轮evidence独占目录不纳入原文件漂移判断。

原artifact四文件、输入、历史诊断与当前PL三行旧修改均保留；未reset/checkout/clean/commit/push/部署/采集/网络变更。stdout/stderr/真实exit见06_integrity同前缀日志。诊断当前state仍REWORK_REQUIRED，人工GT BLOCKED；回归/设备未跑项均NOT_RUN。
'''
with (OUT / '09_integrity.md').open('x', encoding='utf-8') as f:
    f.write(md)
print(json.dumps({'result': result['result'], 'protected': len(required), 'drift': list(drift), 'return_append_only': prefix_ok, 'outside_changes': list(outside), 'outside_added': list(added)}, ensure_ascii=False))
assert not drift and prefix_ok
