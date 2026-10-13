from pathlib import Path
import hashlib
import json

OUT = Path(__file__).parent
ROOT = OUT.parents[3]
baseline = json.loads((OUT / '00_baseline.json').read_text(encoding='utf-8'))
protected = [p for p in baseline['files'] if p.startswith('docs/human_capture/evidence/2026-10-07_hrw03_r39_closeout/')]
protected += ['pc_apps/human_replay/' + f for f in ['human_pipe_lib.js', 'human_replay_lib.js', 'registration.js', 'registration_method.js', 'human_detect.js']]
for name in protected:
    assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == baseline['files'][name]['sha256'], name
record = '''

## R41 — HTML效果对比页（2026-10-07）

- 用户授权：基于已有算法结果生成HTML效果对比。本聊天Codex唯一writer；ponytail实读 C:/Users/30680/.codex/skills/ponytail/SKILL.md（full）。
- 证据：docs/human_capture/evidence/2026-10-07_hrw03_r41_comparison_r1/；入口comparison.html。复用原Three.js/OrbitControls和153帧局部viewer数据，165帧统计独立显示。新方案是已保存R39离线S，未包含R40提出的修复。
- 页面：同步双点云、播放/逐帧、8关键案例、视角/聚焦、上下文/框/差异开关、31点审计位置叠加、全序列曲线、候选/票表及GT/研究入口。颜色是算法输出，不是GT；局部点云与全帧计数明确区分。
- baseline、数据构建、JS语法、153帧数据一致性/SHA/索引守恒检查均exit0，真实stdout/stderr/exit在同前缀日志。浏览器已查看f55/f63/f151、视角/聚焦/上下文操作，控制台warn/error为空；播放按钮已触发，完整播放结束验证NOT_RUN。一次UI自动化精确label定位失败后改用DOM已确认的combobox角色，页面本身无该错误。
- production算法零修改，R39全目录及5个关键生产源码SHA核对相同；原capture/旧evidence不写，dirty保留。本文仅追加。
- 唯一验收仍R3.7 06_test_matrix.md v1；T37/T38本轮NOT_RUN（仅UI与数据检查），既有T38-05/06 FAIL/gate DEGRADED/当前STALE不变。T39/设备/物理/部署/采集NOT_RUN；真人GT BLOCKED；W03仍REWORK_REQUIRED，不进入W04。
'''
with (OUT / '04_return_append.md').open('x', encoding='utf-8', newline='') as f:
    f.write(record)
target = ROOT / 'docs/human_capture/returns/HR-W03.md'
before = target.read_bytes()
with target.open('ab') as f:
    f.write(record.encode('utf-8'))
assert target.read_bytes() == before + record.encode('utf-8')
result = {'protected_files': len(protected), 'protected_sha_unchanged': True, 'return_append_only': True, 'production_changes': 0,
          'artifact_sha256': {f: hashlib.sha256((OUT / f).read_bytes()).hexdigest() for f in ['comparison.html', 'comparison.js', 'comparison_data.js']},
          'T37_T38': 'NOT_RUN', 'T39_device_physical_deploy_capture': 'NOT_RUN', 'W03_state': 'REWORK_REQUIRED'}
with (OUT / '04_integrity.json').open('x', encoding='utf-8') as f:
    json.dump(result, f, ensure_ascii=False, indent=2)
print(json.dumps(result, ensure_ascii=False))
