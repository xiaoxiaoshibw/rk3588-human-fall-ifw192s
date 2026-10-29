"""S06 review packet, immutable old item pointers, scope and seal helpers."""
import argparse
import concurrent.futures
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time

import s06 as S

EV = S.EV
REVIEW = S.ROOT/'docs/human_fall/evidence/2026-10-18_hfus_tcms_02_s06_review_r1'


def row(path):
    if path.is_symlink(): return dict(kind='symlink',target=os.readlink(path))
    if not path.exists(): return dict(kind='missing')
    return dict(sha256=S.W.sha(path),bytes=path.stat().st_size)


def scope():
    before=S.W.load(EV/'BASELINE_ALL.json'); started=time.perf_counter()
    paths=subprocess.check_output(['git','ls-files','--cached','--others','--exclude-standard','-z'],cwd=S.ROOT).decode('utf8').split('\0')
    # Concurrent independent reads avoid per-file serial filesystem latency.
    paths=sorted(set(paths)-{''})
    with concurrent.futures.ThreadPoolExecutor(max_workers=12) as pool:
        current=dict(zip(paths,pool.map(lambda p:row(S.ROOT/p),paths)))
    changes={p:dict(before=before['files'].get(p),after=current.get(p)) for p in sorted(set(before['files'])|set(current)) if before['files'].get(p)!=current.get(p)}
    allowed_prefixes=[EV.relative_to(S.ROOT).as_posix()+'/', REVIEW.relative_to(S.ROOT).as_posix()+'/', S.HERE.relative_to(S.ROOT).as_posix()+'/']
    allowed={'docs/human_fall/WORKFLOW.md','docs/human_fall/REVIEW_LOG.md','docs/human_fall/returns/HFUS-TCMS-02-REALDEV-02-S06.md'}
    external={p:v for p,v in changes.items() if p not in allowed and not any(p.startswith(prefix) for prefix in allowed_prefixes)}
    head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=S.ROOT).decode().strip()
    result=dict(files_checked=len(current),branch=before['branch'],head=head,head_unchanged=head==before['head'],
                changed_files=list(changes),outside_scope=external,source_code={p.name:S.W.sha(p) for p in S.HERE.glob('*.py')},
                seconds=time.perf_counter()-started,PASS=not external and head==before['head'],
                baseline_note='Baseline path list captured before r10 code creation; 466s read interval. Authorized workflow prepend retained old bytes; initial abort only read ignored caches.')
    S.write('SCOPE_CHECK.json',result)
    print(json.dumps({k:v for k,v in result.items() if k not in ('changed_files','outside_scope','source_code')}))


def packet():
    comp=S.W.load(EV/'COMPARISON.json')['variants']; gate=S.W.load(EV/'A_GATE.json')
    a,b=comp['main'],comp['envelope_foreground']; perf=S.W.load(EV/'ENVELOPE_RUN_R1/PERFORMANCE.json')
    initial=(EV/'ACCEPTANCE_V1.md').read_text(encoding='utf8')
    revised=initial.replace('S06 唯一实施验收 v1','S06 唯一实施验收 v2').replace('尾段21一致','尾段21无骨架按候选缺失16/关联歧义5分列并与ledger一致')
    revised+='\n## v2 变更记录\n\n唯一当前版本 v2，v1保留为运行前登记。仅纠正 S06-06 的事实前提：759–763有候选但歧义，764–779无可测候选；21不是空候选帧数。来源PLAN_ERRATA.json与逐帧原记录；A全部数值门、B复用与语义边界不变。此更正不能消除B覆盖/标定退步与继承关联缺陷。\n'
    S.write('ACCEPTANCE_V2.md',revised)
    rows=[
        ('S06-01','PASS','INPUT_CHECK.json / BASELINE_ALL.json：源双SHA、六封存、13复用源/参数；branch/HEAD与全非忽略工作树SHA'),
        ('S06-02','PASS','UNIT_R2.log 4 tests；近地包络strict边界/nearest/无资格/invalid/tau/AABB；r01 DEFAULTS零改动'),
        ('S06-03','PASS','A_GATE.json：97空场+35尾段；+0.731/+0.738pp；32/35；main 132帧ledger精确一致'),
        ('S06-04','FAIL','780帧执行与行守恒PASS；继承节点/标定门FAIL，且57/71次歧义候选仍测量；不采用变体'),
        ('S06-05','PASS','163=74 node_jump+89 other；姿态原因UNKNOWN；两未标定边逐帧支撑+实际失败谓词；无修法'),
        ('S06-06','BLOCKED','780字段/107帧计数重建PASS；107均可观测bg吸收但不能因果划分近地人体/人体静止，UNKNOWN；不冒称静止结论'),
        ('S06-07','PASS','STD_RECONCILIATION / FINAL_HANDOFF_ALL / DELIVERY_INDEX_V2；五历史Codex正式复审NOT_RUN'),
        ('S06-08','NOT_RUN','资源已测A/B/诊断；全树首尾范围核验 SCOPE_CHECK 待生成，原始失败保留'),
        ('S06-09','NOT_RUN','本文件为停写前作者自验；OpenCode review另目录，fresh probe后只读全表审核')]
    S.write('AUTHOR_RESULTS.json',dict(acceptance='ACCEPTANCE_V2.md',status='SUBMITTED',accepted=False,
                                       rows=[dict(id=i,status=s,evidence=e) for i,s,e in rows],
                                       reviewer='NOT_RUN pending',no_adoption=True))
    report=f'''# S06 作者报告 / SUBMITTED，未ACCEPTED

唯一当前验收：ACCEPTANCE_V2.md。Codex唯一writer；策略RESEARCH（规则、覆盖、根因）+ ENGINEERING（可查证据、交接）。实际技能 C:/Users/30680/.codex/skills/ponytail/SKILL.md 与 C:/Users/30680/.codex/skills/scientific-toolkit-skill/SKILL.md。

## 结果

envelope_foreground 的狭义前景门通过，但全段骨架显著退步，不采用、不调门、不改关联。下面是相同780帧与490 ACTION分母；main为封存SK02 RUN_R4，gate的132帧另以main精确重放校验，不冒称全main新跑。

| 指标 | main | envelope_foreground |
|---|---:|---:|
| ACTION 有>=30行候选 | {a['candidate_frames']}/490 | {b['candidate_frames']}/490 |
| >=6原始有效节点 / 有候选 | {a['six_node_frames']}/{a['candidate_frames']} ({a['candidate_fraction']:.4%}) | {b['six_node_frames']}/{b['candidate_frames']} ({b['candidate_fraction']:.4%}) |
| >=6原始有效节点 / 全ACTION | {a['six_node_frames']}/490 ({a['all_action_fraction']:.4%}) | {b['six_node_frames']}/490 ({b['all_action_fraction']:.4%}) |
| 745–779 有>=30行候选 | 19/35 | 32/35 |
| 759–779 有>=30行候选 | 5/21 | 20/21 |
| 759–779 有原始有效节点 | 0/21 | 16/21 |
| 745–779 有>=6原始节点 | {a['tail_six_node_frames']}/35 | {b['tail_six_node_frames']}/35 |
| 轨迹数 | {a['tracks']} | {b['tracks']} |
| ACTION关联歧义帧 | {a['association_ambiguous_frames']} | {b['association_ambiguous_frames']} |
| 曾标定边（全部track-edge） | {a['total_ever_calibrated_edge_tracks']} | {b['total_ever_calibrated_edge_tracks']} |
| DRIFT_RESET | {a['drift_events']} | {b['drift_events']} |

空场[20,28)前景比例中位数0.04025%→0.77153%（+0.73128pp）；[28,30)0.04561%→0.78381%（+0.73819pp），都<=+2pp。绝对前景与候选增加不能证明人体效果。新增前景伴随更多轨迹/歧义和覆盖下降，这是关联/标定支撑被碎片化的观测线索，不是已证因果。变体没有任何CALIBRATED边，跨窗std为null，不填0。

## 根因与限制

1. 原计划错误保留并勘误：尾段21无骨架=5帧有候选但歧义+16帧无可测候选。107=91前段+16尾段；383个ACTION的candidate_summaries确实非空。CANDIDATE_FIELDS.jsonl已逐帧补candidate_rows（全部候选成员并集）、max_candidate_rows（单候选最大值）、measurable_candidate_count。MAP_BUILDING单列，生长背景行可与候选重叠，不把bg+members当划分。
2. EMPTY_FRAME_CLASSIFICATION保留全部107原始计数、contact/bg/rejected证据和main重放一致性。按运行前保守规则107都落background_absorption_static_unknown；这不能区分静止人体/近地人体，因果分类BLOCKED，不能为了填四个格子伪造数量。
3. 163次漂移逐事件记录：74伴随相邻测量节点位移>0.10m，89其他。原记录没有姿态基；姿态类0表示未能归类，非证明不存在。无可验证的单一因果修法，本轮0个修法。
4. 两条从未标定边 UPPER_B|OUTER_B 和 UPPER_TORSO|UPPER_B 分别226/233个测量帧；n>=15分别46/219帧，这些帧全部相对std>0.05（绝对std失败2/152）。不是单纯无支撑；逐帧两端support见UNCALIBRATED_SUPPORT.jsonl，失配/无测量填null。
5. std对账：FRAME_SUMMARY 0.019528578383641446m是7条边的best stable episode原始长度std最大值；REAL_EVALUATION 0.012364802998096664m是12个有跨窗统计片段的窗口均值std最大值。两者由同一TRACKS重算一致；窗口大小15、population std，原数值不改。
6. 额外继承缺陷（ASSOCIATION_CONTRACT_FINDING）：原associate_tracks的最终matches过滤只检查track的歧义，没过滤已标为歧义的candidate。main57次/变体71次仍测量歧义候选。冻结源码未改；这使本轮B契约FAIL，也阻止把旧SK02自验当正式验收。第一版独立检查触发assert后保留日志，R2收集全部反例并继续其余检查。

## 验收

| ID | 作者状态 | 证据/限制 |
|---|---|---|
'''+''.join('|'+i+'|'+s+'|'+e+'|\n' for i,s,e in rows)+f'''

## 验证与预算

python -B -W error 全程；4条新规则测试与13条S3回归通过；合成4/4场景，47/47可测边在容差内、46/47标定；复用提取器/标定层无修改。1560帧双结果全部ledger/原始节点/边长复核，132个gate帧与全运行候选字段精确相同；歧义候选契约单独FAIL。没有display/预测补无候选帧。

A耗时{gate['seconds']:.3f}s，RSS {gate['peak_rss_bytes']}B；B耗时{perf['seconds']:.3f}s，RSS {perf['peak_rss_bytes']}B；重测C/D资源见MEASURED_DIAGNOSTICS.json。输出在3GiB门内；首次全ignored缓存哈希中止只读，正式baseline为34660个tracked+非忽略untracked路径（含旧证据、源码、工作树），ignored输入另核源双SHA。完整范围核对见SCOPE_CHECK。失败/重跑/环境问题不删。

设备/部署/采集/训练/下载/HR09/网络配置/Git写NOT_RUN；解剖/左右/物理高度/人体身份/效果/独立D UNKNOWN/BLOCKED。不进入S07。当前交付是失败与证据诊断包，非可上线算法。
'''
    S.write('REPORT.md',report)
    old_index=S.W.load(S.ROOT/'docs/human_fall/evidence/2026-10-17_hfus_tcms_02_s05_r1/DELIVERY_INDEX.json')
    index=copy.deepcopy(old_index);index['item']='HFUS-TCMS-02-REALDEV-02-S06';index['version']=2
    index['previous_index_sha256']=S.W.sha(S.ROOT/'docs/human_fall/evidence/2026-10-17_hfus_tcms_02_s05_r1/DELIVERY_INDEX.json')
    plan=S.W.load(S.PLAN/'INPUT_BASELINE.json')['inputs']
    for key,status in [('SK01','BLOCKED'),('SK02','SUBMITTED')]:
        r=plan[key];index['items'].append(dict(item=key,path=r['dir'],seal_json_sha=r['seal'],status=status,codex_formal_review='NOT_RUN',acceptance='ACCEPTANCE_V2.md' if key=='SK02' else 'ACCEPTANCE_V1.md'))
    index['items'].append(dict(item='S06',path=EV.relative_to(S.ROOT).as_posix(),status='SUBMITTED_WITH_FAIL_AND_BLOCKED',acceptance='ACCEPTANCE_V2.md',review_path=REVIEW.relative_to(S.ROOT).as_posix(),seal='FINAL_SEAL.json (outer root, index does not self-hash)'))
    index['std_reconciliation']=S.W.load(EV/'STD_RECONCILIATION.json');index['adopted']=False
    S.write('DELIVERY_INDEX_V2.json',index)
    handoff='''# S3 / S4 / S5 / SK01 / SK02 / S06 统一复审入口

S06当前唯一验收ACCEPTANCE_V2.md；作者REPORT.md和AUTHOR_RESULTS.json；原始对照COMPARISON.json；范围SCOPE_CHECK.json；封存FINAL_SEAL.sha256→FINAL_SEAL.json→MANIFEST.json。OpenCode只读审核在相邻2026-10-18_hfus_tcms_02_s06_review_r1目录，S06源码停写后派发。OpenCode不能代替五历史项Codex正式复审，全部NOT_RUN，作者不自行ACCEPTED。

依赖顺序 S3（含r2勘误）→S4→S5索引→SK01失败边界→SK02区域标定→S06前景变体失败。DELIVERY_INDEX_V2在S5索引上追加，保留全部原条目，不覆盖任何原索引/门/封存。

| 项 | 封存目录（相对仓库） | 必看三条 | Codex正式复审 |
|---|---|---|---|
'''
    for key,critical in [('S03','FINAL_SEAL.json / ACCEPTANCE_V1.md / REPORT.md；补看S03_R2勘误'),('S04','FINAL_SEAL.json / ACCEPTANCE_V1.md / TAIL_DECOMPOSITION.json'),('S05','FINAL_SEAL.json / DELIVERY_INDEX.json / FINAL_HANDOFF.md'),('SK01','FINAL_SEAL.json / ACCEPTANCE_V1.md / STATUS.md：合成门失败'),('SK02','FINAL_SEAL.json / ACCEPTANCE_V2.md / REAL_EVALUATION.json：本轮关联反例须并看')]:
        handoff+='|'+key+'|'+plan[key]['dir']+'|'+critical+'|NOT_RUN|\n'
    handoff+='\nS06必看：A_GATE（窄门PASS不能替代B）、COMPARISON+ASSOCIATION_CONTRACT_FINDING（B退步/继承契约FAIL）、PLAN_ERRATA+STD_RECONCILIATION+DRIFT_CLASSIFICATION（事实更正/统计集合/未知根因）。SOURCE_AT_RUN仅pin实际运行的s06/test，提交全源码SHA见SCOPE_CHECK与MANIFEST。\n'
    S.write('FINAL_HANDOFF_ALL.md',handoff)
    S.write('IMPLEMENTATION_NOTES.json',dict(writer='Codex',strategy='RESEARCH+ENGINEERING',
        skills=['C:/Users/30680/.codex/skills/ponytail/SKILL.md','C:/Users/30680/.codex/skills/scientific-toolkit-skill/SKILL.md'],
        failures_retained=[dict(stage='initial input binding',error='write guard still pointed to SK02; rejected before any output; fixed adapter W.EV, INPUTS_R2 exit0'),
                           dict(stage='workflow append',error='wb O_TRUNC OS EINVAL; no bytes changed. r+b binary prepend succeeded, old bytes retained'),
                           dict(stage='initial delivery verification',log='DELIVERY_VERIFICATION.log',error='ambiguous candidate invariant exposed inherited defect; R2 gathers all counterexamples, no invariant relaxed into PASS')],
        commands=dict(unit='python -B -W error -m unittest discover -s sidequests/hfus_tcms_02/realdev/r10 -p test_s06.py -v',
                      gate='python -B -W error sidequests/hfus_tcms_02/realdev/r10/s06.py gate',
                      skeleton='python -B -W error sidequests/hfus_tcms_02/realdev/r10/s06.py skeleton',
                      candidates='python -B -W error sidequests/hfus_tcms_02/realdev/r10/s06.py candidates',
                      calibration='python -B -W error sidequests/hfus_tcms_02/realdev/r10/s06.py calibration',
                      verify='python -B -W error sidequests/hfus_tcms_02/realdev/r10/verify_delivery.py',
                      measured='python -B -W error sidequests/hfus_tcms_02/realdev/r10/verify_delivery.py measure'),
        all_recorded_exit_codes=dict(inputs_r2=0,unit=0,gate=0,calibration=0,candidates=0,skeleton=0,synthetic=0,s3_regression=0,initial_input=1,initial_verifier=1,verifier_r2=0,verifier_semantic_PASS=False)))


def seal():
    files={}
    for p in sorted(EV.rglob('*')):
        if not p.is_file() or p.name in ('MANIFEST.json','FINAL_SEAL.json','FINAL_SEAL.sha256'): continue
        files[p.relative_to(EV).as_posix()]=row(p)
    S.write('MANIFEST.json',dict(item='S06',status='SUBMITTED_WITH_FAIL_AND_BLOCKED',files=files,
                                source={p.relative_to(S.ROOT).as_posix():row(p) for p in S.HERE.glob('*.py')}))
    S.write('FINAL_SEAL.json',dict(item='S06',manifest_sha256=S.W.sha(EV/'MANIFEST.json'),acceptance='ACCEPTANCE_V2.md',
                                  status='SUBMITTED',accepted=False,no_adoption=True,formal_review='NOT_RUN',
                                  review_directory=REVIEW.relative_to(S.ROOT).as_posix()))
    S.write('FINAL_SEAL.sha256',S.W.sha(EV/'FINAL_SEAL.json')+'  FINAL_SEAL.json\n')
    print('SEALED',S.W.sha(EV/'FINAL_SEAL.json'))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['packet','scope','seal']);args=p.parse_args()
    {'packet':packet,'scope':scope,'seal':seal}[args.action]()
