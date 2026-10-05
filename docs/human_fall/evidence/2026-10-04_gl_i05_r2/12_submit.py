"""Close the R2 research submission, hashing only closed logs and outputs."""
import ast
import hashlib
import json
from pathlib import Path
import statistics

OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[3]
R=OUT/'research_01'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
ledger=json.loads((R/'experiment_results_identity_verified.json').read_text(encoding='utf8'))
cases=ledger['synthetic']+ledger['real_WHAT_IF']
assert len(cases)==38 and all(e['oracle_match'] and e['closure_safe'] for e in cases)
assert all(e['sequence_sha256']==e['old_sequence_sha256']==e['prototype_sequence_sha256'] for e in cases)
assert all(len(e['cost_repeats'])==3 and e['peak_tracemalloc_bytes']>0 for e in cases)
for p in R.glob('*.py'):ast.parse(p.read_text(encoding='utf8'),feature_version=(3,8))
for name,digest in ledger['implementation_sha256'].items():
    assert sha(ROOT/name)==digest,(name,'ledger implementation drift')
summary=dict(kind='gli05_r2_summary',status='SUBMITTED',physical_verified=False,
    acceptance='GLI05_ACCEPTANCE.md v1',cases=38,oracle_match_all=True,closure_safe_all=True,
    sequence_digest_match_all=True,weak_dominant_positive_cases=sum(
        e['case'].startswith('weak') and e['prototype']['status']=='seen_dominant_pool_closed' for e in cases),
    stages_s={key:statistics.median(t[key] for e in cases for t in e['cost_repeats'])
              for key in ('sampling','raw','refine','decision','serialization')},
    real_cost={e['case']:dict(search_median_s=statistics.median(t['search_total'] for t in e['cost_repeats']),
        peak_tracemalloc_bytes=e['peak_tracemalloc_bytes'],status=e['prototype']['status'])
              for e in ledger['real_WHAT_IF']},
    decision='retain research only, no refine cache; corrected diagnostics and evidence; independent second review pending',
    metric_domains='oracle: full refined multiset W; prototype pair indices/counts: exact-signature representatives. Full multiplicity remains in produced/merged_exact and trace; holds/status invariant, pair counts are not claimed equal.',
    costs_boundary=ledger['cost_comparison_boundary'],B01='BLOCKED',B02='BLOCKED',D01='NOT_RUN',D02='NOT_RUN')
with (R/'22_final_research_summary.json').open('x',encoding='utf8') as f:json.dump(summary,f,indent=2)
software=('C01','C02','C03','C04','C05','C06','E01','E02')
with (ROOT/'docs/human_fall/returns/GL-I05.md').open('a',encoding='utf8') as f:
    f.write('\n\n## GL-I05 R2 / Codex / 2026-10-04 / SUBMITTED，停写\n\n'
        'ponytail实际路径：C:/Users/30680/.codex/skills/ponytail/SKILL.md。'
        '仅新evidence/2026-10-04_gl_i05_r2，生产/输入/旧研究冻结。'
        '唯一GLI05_ACCEPTANCE.md v1；基线00_before_baseline.json。\n\n'
        '| ID | 自验结果 | 证据 |\n|---|---|---|\n')
    mapping={'C01':'09_research_tests + 独立scalar', 'C02':'同序列三个digest + oracle非法参数',
             'C03':'reason/计数/trace快照', 'C04':'38 case + weak六正例 + 全排列',
             'C05':'四预算/晚best/source-ceiling/拒绝', 'C06':'每case三重复五阶段及独立内存峰值',
             'E01':'spatial_02 + 05_page_consumer_check + source负例',
             'E02':'08_assets_audit有界metadata/窗口/提取时间/SHA/未知链'}
    for key in software:f.write('| '+key+' | PASS（自验） | '+mapping[key]+' |\n')
    f.write('| S01 | BLOCKED（仅待独立二审） | 首尾scope/SHA、Py3.8 AST、stdlib+NumPy；复用R1仍有效423/2回归 |\n')
    for key in ('B01','B02'):f.write('| '+key+' | BLOCKED | 原bag/录制配置与物理身份缺口 |\n')
    for key in ('D01','D02'):f.write('| '+key+' | NOT_RUN | 设备/真实DPR未启动 |\n')
    for key in range(1,10):f.write('| Q%02d | PASS（自验） | 00_diag矩阵及上述软件证据 |\n'%key)
    f.write('| Q10 | BLOCKED（待二审） | 完整manifest/日志已关闭/停写；新probe后只读二审 |\n\n'
        '原始命令/真实exit：09_research_tests_exit=0（17研究自检）；10_experiment_exit=0（38case）；'
        '05_page_consumer_check_exit=0；08_assets_audit_exit=0；原失败03日志exit1保留。'
        '最终实验14_experiment_exit=0；有效实验只experiment_results_identity_verified.json；空间只spatial_02/source_review.html。'
        '成本/资源与界限见22_summary和11_IMPLEMENTATION_LOG；不沿用无制品46秒。'
        '真实approved仍无合格候选，negative-X仍WHAT_IF unresolved。未ACCEPTED；指定模型二审后再收口。\n')
entry=('2026-10-04 GL-I05 R2 **SUBMITTED待指定独立二审**：[唯一v1](GLI05_ACCEPTANCE.md)/'
       '[提交](evidence/2026-10-04_gl_i05_r2/research_01/11_submission_manifest.json)/'
       '[R1复盘](evidence/2026-10-04_gl_i05_r1/09_CLOSEOUT.md)。Codex研究writer已停写；'
       '38case自验同序列匹配、17研究自检通过；fresh probe后Go Flash/defaultDB只读二审。'
       'B01/B02 BLOCKED，D01/D02 NOT_RUN，未ACCEPTED。')
for name in ('README.md','DISPATCH.md','WORKFLOW.md'):
    path=ROOT/'docs/human_fall'/name
    text=path.read_text(encoding='utf8');first,rest=text.split('\n',1)
    path.write_text(first+'\n\n'+entry+'\n'+rest,encoding='utf8')
paths=[p for p in OUT.rglob('*') if p.is_file()]
paths += [ROOT/'docs/human_fall'/name for name in ('GLI05_ACCEPTANCE.md','GLI05_TASK.md','returns/GL-I05.md')]
inputs=json.loads((ROOT/'docs/human_fall/evidence/2026-10-03_gl_i05_r1/research_01/11_submission_manifest.json').read_text(encoding='utf8'))
paths += [ROOT/p for p in inputs['files'] if not p.endswith('CLI_RECOVERY.md') and not p.endswith('returns/GL-I05.md')]
paths += [ROOT/'src/human_fall_detection/config/geometry_constrained_gli03_r1.yaml']
baseline=json.loads((OUT/'00_before_baseline.json').read_text(encoding='utf8'))
manifest=dict(kind='gli05_submission_manifest',status='SUBMITTED',writer='Codex',
    branch=baseline['branch'],head=baseline['head'],run_root=str(OUT.relative_to(ROOT)).replace('\\','/'),
    research_root=str(R.relative_to(ROOT)).replace('\\','/'),acceptance_version=1,
    ponytail_skill_path='C:/Users/30680/.codex/skills/ponytail/SKILL.md',
    active_ledger='experiment_results_identity_verified.json',active_spatial='spatial_02/source_review.html',
    files={p.relative_to(ROOT).as_posix():sha(p) for p in sorted(set(paths))},
    old_new_implementation_sha={p.relative_to(ROOT).as_posix():sha(p) for p in
        [R/'search_prototype.py',ROOT/'docs/human_fall/evidence/2026-10-03_gl_i04_r1/research_01/search_prototype.py']},
    self_checks=summary,review='pending fresh probe, Go Flash/defaultDB; no production integration')
with (R/'11_submission_manifest.json').open('x',encoding='utf8') as f:json.dump(manifest,f,indent=2,ensure_ascii=False)
print(json.dumps(dict(status='SUBMITTED',files=len(manifest['files']),cases=38,real_cost=summary['real_cost'])))
