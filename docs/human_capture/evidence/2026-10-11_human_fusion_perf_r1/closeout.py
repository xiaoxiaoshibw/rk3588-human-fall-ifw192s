"""Report current inherited implementation; do not rewrite historical FAIL."""
import hashlib
import json
import pathlib

HERE = pathlib.Path(__file__).parent
ROOT = HERE.parents[3]
summary = json.loads((HERE / 'before_runs/summary.json').read_text(encoding='utf-8'))
engine = ROOT / 'pc_apps/human_core/engine.js'
assert hashlib.sha256(engine.read_bytes()).hexdigest() == hashlib.sha256((HERE / 'engine_before.js').read_bytes()).hexdigest()
assert all(r['gate'] == 'PASS' for r in summary['results'])
text = ['# 当前性能复验', '',
        '继承外部R3 Map实现，Codex本轮未修改engine/生产/模型。历史R2 FAIL原样保留。',
        '同机每会话全帧FUSION×v1/v2；剔除5帧预热，哈希/序列化在tick耗时之外，阶段计时包装带少量开销。', '',
        '| sid | 模型 | 帧数 | P95 ms | heap MB | 结果 |', '|---|---|---|---|---|---|']
for r in summary['results']:
    text.append(f"| {r['sid']} | v{r['model']} | {r['n_frames']} | {r['timing']['p95']:.2f} | {r['heap_mb']:.1f} | {r['gate']} |")
text += ['', '12/12门通过；S3-far v1/v2=25.83/28.47ms，不代表设备或发布性能。',
         '由于无需新增优化，优化前后对拍P03为NOT_RUN；只验证现行engine与本轮保存原文SHA一致，未冒称历史M1原实现逐帧等价。',
         '性能余量不能解决空场误报和候选模型运动回退，已转R4候选归因。']
(HERE / 'REPORT.md').write_text('\n'.join(text) + '\n', encoding='utf-8')
with (ROOT / 'docs/human_capture/returns/HUMAN-FUSION-PERF-R1.md').open('a', encoding='utf-8') as f:
    f.write('''## 2026-10-11 R1 / Codex

- SUBMITTED / 停写，未ACCEPTED；当前性能诊断完成，无新生产源码优化。
- 唯一验收：HUMAN_FUSION_PERF_R1_ACCEPTANCE.md v1。
- master/026e06303f60ed1bbe4ddc4d037836db68da6d27；before全tracked/untracked SHA及保存engine原文，结束范围见R4 SCOPE_AUDIT。
- ponytail实际路径：C:/Users/30680/.codex/skills/ponytail/SKILL.md。
- 新离线check_perf.js，全帧六会话两模型/3826帧tick；继承外部R3 Map优化，非本轮修复收益。
- P01 PASS（基线/engine未改/范围证据）；P02 PASS（逐层复验，当前旧失败不再复现）；P03 NOT_RUN（未新增优化，不冒称历史前后等价）；P04 PASS（12/12，详REPORT）；S01 PASS（R4相关core/FUSION回归）；Q01 NOT_RUN（未对本性能诊断另派独审）；G01 BLOCKED；D01 NOT_RUN。
- 实际命令node --max-old-space-size=2048 check_perf.js before，exit0，01_before.log与before_runs/summary.json含全部来源及数据SHA、heap/RSS/external。原R2/R3记录不回填。
- 无commit/push/deploy/采集/训练/模型推广，转R4候选归因软件；验收表SHA见R4最终manifest与全树after快照。
''')
print('current perf report 12/12 PASS; no new engine change')
