"""Append current return and audit scope; preserve all prior records."""
import hashlib
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(HERE))
from baseline import snapshot


def write(name, value):
    with (HERE / name).open('x', encoding='utf-8') as f:
        json.dump(value, f, ensure_ascii=False, indent=1)


q_status = sys.argv[1]
assert q_status in ('PASS', 'FAIL', 'BLOCKED')
commands = [
    ('check_perf.js before', 0, '../2026-10-11_human_fusion_perf_r1/01_before.log'),
    ('snapshot_gt.py', 0, 'GT_SNAPSHOT_02.json'),
    ('audit_fusion_candidates.js runs_01', 0, '01_runs.log'),
    ('audit_fusion_candidates.js runs_02', 0, '06_runs.log'),
    ('audit_fusion_candidates.js runs_03', 0, '08_runs.log'),
    ('run_all_tests.js', 0, '02_core_tests.log'),
    ('test_fusion_specific.js', 0, '03_fusion_tests.log'),
    ('test_fusion_gt.js', 0, '04_gt_contract_tests.log'),
    ('test_candidate_audit.js final', 0, '07_candidate_tests.log'),
    ('summarize.py', 0, 'REPORT.md'),
]
write('COMMAND_RESULTS.json', [{'command': c, 'exit': e, 'log': log} for c, e, log in commands])
acceptance = ROOT / 'docs/human_capture/HUMAN_R4_CANDIDATE_AUDIT_ACCEPTANCE.md'
acceptance_sha = hashlib.sha256(acceptance.read_bytes()).hexdigest()
return_path = ROOT / 'docs/human_capture/returns/HUMAN-R4-CANDIDATE-AUDIT.md'
text = f'''## 2026-10-11 R1 / Codex

- 用户授权：“继续啊下一个阶段的开发计划制定并且执行”；按最近人体融合线推进本地离线阶段。
- 唯一验收：HUMAN_R4_CANDIDATE_AUDIT_ACCEPTANCE.md v1，SHA {acceptance_sha}。
- 状态：SUBMITTED / 停写，未ACCEPTED。仅离线归因工具/检查/文档。
- 起始master/026e06303f60ed1bbe4ddc4d037836db68da6d27，D:/Code/ldiar；全树基线before.json，结束after.json及SCOPE_AUDIT.json。
- ponytail实际读取路径：C:/Users/30680/.codex/skills/ponytail/SKILL.md。

### 集中诊断与变更

复用frozen_gt审计、engine和GT解码。不重复外部R3 Map优化；本轮性能复验12/12通过。新增pc_apps/human_core/audit_fusion_candidates.js及test_candidate_audit.js，模块README增入口。生产、engine、模型、GT、captures及历史证据不改。

根因覆盖：GT compact索引映射raw；A+B公开索引未同步联合评分点集，工具只读重建真正评分联合索引；无交叠不自动负标，未标167个S6帧保持UNKNOWN。生成/接受/强分类/当前确认轨迹分别统计。新结果见REPORT.md、FINDINGS.md及OBSERVATIONS.json，模型/实现/输入/GT来源SHA保存在runs_03/SUMMARY.json及逐会话文件。

### 逐条自验

| ID | 结果 | 证据 |
|---|---|---|
| A01 | PASS | before/after、SCOPE_AUDIT，源码/历史输入冻结核对 |
| A02 | PASS | GT_SNAPSHOT_02：S1 V3、S3-near V1、S6 V1当前绑定再审；仅本三会话 |
| A03 | PASS | runs_03 9完整运行/2400帧tick，源码/模型/输入/GT SHA守卫 |
| A04 | PASS | compact→raw、评分联合点集重建、逐帧交叠及完整ROI概率/51维；边界检查 |
| A05 | PASS | 空场v1/v2/v3当前确认观测600/327/581；非人数/对象recall；分类与跟踪分开 |
| S01 | PASS | core7/7套、FUSION16、GT契约、新映射/去重/联合点集检查；命令exit0 |
| Q01 | {q_status} | review_probe_01_status/opencode_review_01_status及OPENCODE_INDEPENDENT_REVIEW.md |
| G01 | BLOCKED | 同场景传播样本、UNKNOWN、模型运动回退；不声称唯一根因或泛化/推广 |
| D01 | NOT_RUN | 本轮无设备/物理/采集/部署/生产；无commit/push |

### 未闭合与后续

R3“RF无关/51维本质不可分”的强结论证据不足；当前近场完整ROI v2=1.0与实际PERSON交叠簇概率中位0.355支持分布差异排查。A+B公开点集契约仍需另工单修复；本工具已避免错误归因。随后导出实际候选级覆盖/污染/51维并人工复核；独立演员/场景采集与新训练需新协议，本轮未执行。保留v1，不生产推广。

### 复审入口

当前计划HUMAN_FUSION_NEXT_STAGE_PLAN.md；唯一验收及本目录原始日志、REPORT/FINDINGS、源码SHA/manifest与独审stdout可供复核。runs_01为初版诊断，runs_02补全冻结/无人协议守卫，runs_03补联合评分点集，前两版保留不作为最终提交源码证据。
'''
with return_path.open('a', encoding='utf-8') as f:
    f.write(text)

snapshot('after')
before = json.loads((HERE / 'before.json').read_text(encoding='utf-8'))
after = json.loads((HERE / 'after.json').read_text(encoding='utf-8'))
allowed = {'docs/human_capture/README.md', 'pc_apps/human_core/README.md',
           'docs/human_capture/HUMAN_FUSION_NEXT_STAGE_PLAN.md',
           'docs/human_capture/HUMAN_FUSION_PERF_R1_ACCEPTANCE.md',
           'docs/human_capture/HUMAN_R4_CANDIDATE_AUDIT_ACCEPTANCE.md',
           'pc_apps/human_core/audit_fusion_candidates.js', 'pc_apps/human_core/test_candidate_audit.js',
           'docs/human_capture/returns/HUMAN-R4-CANDIDATE-AUDIT.md',
           'docs/human_capture/returns/HUMAN-FUSION-PERF-R1.md'}
changed = [p for p in before['files'] if after['files'].get(p) != before['files'][p]]
new = [p for p in after['files'] if p not in before['files']]
unexpected = [p for p in changed + new if p not in allowed and
              not p.startswith('docs/human_capture/evidence/2026-10-11_human_fusion_perf_r1/')]
scope = {'branch_same': before['branch'] == after['branch'], 'head_same': before['head'] == after['head'],
         'changed': changed, 'new': new, 'unexpected': unexpected,
         'result': 'PASS' if not unexpected and before['head'] == after['head'] else 'BLOCKED'}
write('SCOPE_AUDIT.json', scope)
files = list(HERE.rglob('*')) + [ROOT / 'pc_apps/human_core/audit_fusion_candidates.js',
                                ROOT / 'pc_apps/human_core/test_candidate_audit.js', acceptance]
write('ARTIFACT_MANIFEST.json', {str(p.relative_to(ROOT)).replace('\\', '/'):
    hashlib.sha256(p.read_bytes()).hexdigest() for p in files if p.is_file()})
print('scope', scope['result'], 'unexpected', unexpected)
assert scope['result'] == 'PASS', 'external differences preserve and report; do not revert'
