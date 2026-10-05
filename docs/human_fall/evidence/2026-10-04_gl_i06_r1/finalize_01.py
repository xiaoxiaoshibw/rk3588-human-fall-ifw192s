"""Close author records, complete manifest and append-only return; no Git commit."""
import ast
import datetime
import hashlib
import json
from pathlib import Path
import sys

RUN=Path(__file__).resolve().parent
ROOT=RUN.parents[3]
HERE=RUN/'research_01'
sys.path.insert(0,str(HERE))
from audit_03 import stats


def read(path):return json.loads(path.read_text(encoding='utf-8'))
def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(1<<20),b''):h.update(block)
    return h.hexdigest()
def new(path,value):
    with path.open('x',encoding='utf-8') as f:json.dump(value,f,ensure_ascii=False,allow_nan=False,indent=2)


def main():
    before=read(RUN/'01_before_baseline.json');after=read(RUN/'16_submission_baseline_01.json')
    prefix=RUN.relative_to(ROOT).as_posix()+'/'
    changed=[k for k,v in before['files'].items() if not k.startswith(prefix) and after['files'].get(k)!=v]
    added=[k for k in after['files'] if k not in before['files'] and not k.startswith(prefix)]
    assert not changed and not added,(changed,added)
    assert before['head']==after['head'] and before['branch']==after['branch']
    logs=sorted(RUN.glob('*exit*.txt'))
    exits={p.name:int(p.read_text(encoding='utf-8').strip()) for p in logs}
    assert exits and all(v==0 for v in exits.values()),exits
    scripts=list(RUN.rglob('*.py'))
    for p in scripts:ast.parse(p.read_text(encoding='utf-8'),feature_version=(3,8))
    freeze=read(HERE/'method_freeze_01.json')
    assert all(sha(HERE/name)==value for name,value in freeze['implementation_sha256'].items())
    dev=read(HERE/'development_metrics_01.json')
    final=read(HERE/'final_holdout_summary_01.json')
    assert len(final['results'])==30 and final['first_exposure']
    final_stats=stats(dict(results=[dict(row,case=row['case'][6:]) for row in final['results']]))
    assert not dev['false_closed'] and not final_stats['false_closed']
    stable=read(HERE/'fixed_source_summary_01.json')
    timing={str(k):read(HERE/('active_timing_K%d_01.json'%k)) for k in (1,2,3)}
    memory={str(k):read(HERE/('active_memory_K%d_01.json'%k)) for k in (1,2,3)}
    assert all(len(v['costs'])==3 for v in timing.values())
    # Verify active numeric entry parity on real WHAT_IF after once-per-call conversion.
    from r0_01 import real_inputs,gd,g
    from refinement_05 import run_variant
    cloud,rows,regions,draft,s=real_inputs()
    up=g._unit_vector([-draft['up_axis'][0],0.,draft['up_axis'][2]],'up')
    sampled,fit,iterator=gd.replay_sequence(cloud,rows,up,draft['sensor_height_interval_m'],s)
    active=run_variant(cloud,sampled,fit,list(iterator),up,draft['sensor_height_interval_m'],s,1)
    original=read(HERE/'r1_case_real_historical_WHAT_IF_negative_X_K1_02.json')['variant']
    assert active['W']==original['W'] and active['report']['metrics']==original['report']['metrics']
    ids=['A01','A02','A03','A04','A05','A06','A07','S01','B01','D01','Q01','Q02','Q03','Q04','Q05','Q06']
    statuses={k:'PASS' for k in ids};statuses.update(S01='NOT_RUN',B01='BLOCKED',D01='NOT_RUN',Q06='NOT_RUN')
    audit=dict(status='SUBMITTED',self_check=statuses,required_table='docs/human_fall/GLI06_ACCEPTANCE.md v1',
        development=dev,final_holdout=final_stats,seed_stability=stable['stability'],
        active_costs=timing,independent_memory_peaks=memory,commands_exit=exits,
        python38_AST_scripts=len(scripts),scope_changed=changed,scope_added_outside_run=added,
        head=after['head'],branch=after['branch'],real_active_K1_exact_W_and_metric_parity=True,
        robust_weights='NOT_RUN condition branch; symmetric noise bias studied by bounded TLS; wall contamination sub-mm best validation, no material quality-gate failure requiring weights',
        robust_limits='small wall effects are not claimed zero; no robust improvement claimed; independent review must confirm non-applicability',
        physical_verified=False,ground_valid=False,
        adoption='retain_frozen_baseline_no_adoption',independent_review='NOT_RUN pending fresh probe and specified model',
        stage_cost_scope='Active per-call dtype conversion measured separately; historical 01 real timings not labeled active05 performance',
        regression_reuse='GL-I05 R1 423/2 logs; src/human_fall_detection SHA matches GL-I05R2 baseline; no production/config change')
    new(RUN/'17_evidence_audit_01.json',audit)
    lines=['# GL-I06 R1 / SUBMITTED / 作者代码停写','',
           '唯一验收GLI06_ACCEPTANCE.md v1；Codex唯一研究writer。实际pony­tail路径 C:/Users/30680/.codex/skills/ponytail/SKILL.md。',
           'branch '+after['branch']+' / HEAD '+after['head']+'；首尾完整tracked/untracked及显式ignored输入SHA见01/16基线，范围外变化0。',
           '', '采用结论：保留冻结单次TLS，不采用K2/K3。开发62case、额外固定source12case、最终封存种子30case、107项集中契约探针。测试数仅台账，逐ID结果如下。',
           'K2/K3单假设偏差可减少，但分别新增10/6个开发未决；完整W与不同精炼W域明确，误闭合0。最终holdout为合成，不是当前89帧的真实物理留出。',
           '', '| ID | 自验 | 证据 / 限制 |','|---|---|---|']
    entries={
        'A01':'R0 62cases source/FIT/settings/raw/sample SHA；K1与旧W全等；active05真实WHAT_IF一次转换后W/metrics全等。',
        'A02':'raw per draw拒绝、旧代表动作、refine/成员/merge/资源detail完整；report counts是旧callback adapter计数，非收敛计数。',
        'A03':'math scalar独立oracle+合成GT；full W指标和stored subset分域；ties/chain/late/weak与每预算边界。',
        'A04':'R0已证0.827°截取偏差→K2/K3同sampled域；每轮重查，正常不收敛/注入cycle/later越界/LO gap单列；均不伪closed。',
        'A05':'full W support最大、全FIT J/覆盖分列；schema/caller/source/units/NaN/zero/line/旧out；IRLS条件实验NOT_RUN，未声称鲁棒收益。',
        'A06':'10类×3seed×置换，固定source另3RANSAC seed；三独立validation groups及空间bounds；未筛holdout；freeze后1707/1719/1741首次最终合成holdout30case。',
        'A07':'3次active计时每K、12case三重复，分阶段/序列化；另进程Windows memory peak；GT/最差区域/稳定/误闭合/额外未决；不称板端或端到端加速。',
        'S01':'pony­tail/先diag/单writer/不可覆盖/首尾SHA完成；指定Go Flash/defaultDB实际独审待执行，故当前NOT_RUN。',
        'B01':'真实up、point-origin高度、地面身份未核；physical=false、ground_valid=false。',
        'D01':'不生产接入/设备运行/部署/采集；RK3588性能NOT_RUN。',
        'Q01':'checks_05身份/输入/不可覆盖/无缓存；schema bool及空序列非法K/LO拒绝。',
        'Q02':'scalar全相似/链/中best/ties/weak/late×四预算0/边界/不足。',
        'Q03':'数值非收敛与资源独立；注入solver-state cycle不是实际TLS振荡证据。',
        'Q04':'同支持J仅诊断，小J distinct不吞；鲁棒权重/零尺度权重计算NOT_RUN，条件适用由独审确认。',
        'Q05':'硬场景/seed/置换/固定source/真实WHAT_IF/validation独立；真实最终留出NOT_RUN。',
        'Q06':'成本/否定/冻结/停写已完成，实际probe/独审当前NOT_RUN。'}
    for k in ids:lines.append('| '+k+' | '+statuses[k]+' | '+entries[k]+' |')
    lines+=['','开发最差单平面GT/独立区域：']
    for k,v in dev['stages'].items():lines.append('K%s：法向 %.9f°，offset %.9fm，区域RMS %.9fm / P95 %.9fm。'%(k,v['worst_gt_normal_deg'],v['worst_gt_offset_m'],v['worst_region_rms_m'],v['worst_region_p95_m']))
    lines+=['','独立memory（整进程含imports，不是算法增量）：']
    for k,v in memory.items():lines.append('K%s PeakWorkingSet %d bytes / PeakPrivateCommit %d bytes。'%(k,v['after']['peak_working_set_bytes'],v['after']['peak_private_commit_bytes']))
    lines+=['','活动源码：refinement_05.py；入口checks_05/publish_04/fixed_source_02/holdout_03/cost_memory_03。01–04历史修订均保留；只有_01/02首次数值源码运行及_04/_05完整发布/最终入口实际使用，未执行修订不是试验结果。',
            '活动R1台账r1_case_*_02.json来自不可变_01数值记录；_02追加full-W vector/scalar复核、J/覆盖和额外决策计时。active05真实K1及合成完整入口复核相同W。',
            '所有最终holdout数值源码SHA与method_freeze_01.json相同；无曝光后调参。冻结源码与生产423/2旧回归仍匹配，不重跑代替独审。',
            '日志已关闭；19_manifest_01.json为全部作者本轮文件+冻结依赖SHA（排除manifest自身），接着追加return后停止代码写入。独审新检查只在opencode_review_01，独审失败不自动返工/切模型。']
    submission=RUN/'18_SUBMISSION_01.md'
    with submission.open('x',encoding='utf-8') as f:f.write('\n'.join(lines).replace('pony­tail','ponytail')+'\n')
    deps={k:v for k,v in after['files'].items() if not k.startswith(prefix)}
    files={p.relative_to(ROOT).as_posix():dict(sha256=sha(p),size=p.stat().st_size) for p in sorted(RUN.rglob('*')) if p.is_file()}
    manifest=dict(schema=1,status='SUBMITTED',time=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),
                  files=files,frozen_dependencies=deps,exclude='manifest itself; subsequent probe/review evidence not author submission',
                  acceptance_sha256=sha(ROOT/'docs/human_fall/GLI06_ACCEPTANCE.md'),
                  physical_verified=False,ground_valid=False,head=after['head'],branch=after['branch'])
    new(RUN/'19_manifest_01.json',manifest)
    ret=ROOT/'docs/human_fall/returns/GL-I06.md'
    header='## GL-I06 R1 / 2026-10-04 / SUBMITTED'
    if ret.exists() and header in ret.read_text(encoding='utf-8'):raise ValueError('return round already appended')
    text='\n\n'+header+'\n\n'+ '\n'.join(lines[2:])+ '\n\nManifest SHA256: '+sha(RUN/'19_manifest_01.json')+'\n验收表SHA256: '+manifest['acceptance_sha256']+'\n实际执行者Codex；指定OpenCode独审尚未执行，未填会话/模型成功。全部原始命令退出码见17_evidence_audit_01.json；本次所有记录退出0。\n'
    with ret.open('a',encoding='utf-8') as f:f.write(text)
    print(json.dumps(dict(status='SUBMITTED',author_files=len(files),frozen_dependencies=len(deps),self_check=statuses,scope_changed=changed)))


if __name__=='__main__':main()
