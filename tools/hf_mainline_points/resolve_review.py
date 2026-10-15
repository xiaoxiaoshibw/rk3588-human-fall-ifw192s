"""Read-only artifact checks and versioned responses to the independent review."""
import hashlib,json,sys,time
from datetime import datetime,timezone
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[2];PS=R/'sidequests/human_fusion_lab_next/pointset/r01'
E=R/'docs/human_fall/evidence/2026-10-14_hf_mainline_points_r1';OUT=PS/'action_research_retention'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
read=lambda p:json.loads(p.read_text(encoding='utf8'))
def write(p,x):
 with p.open('x',encoding='utf8') as f:f.write(x if isinstance(x,str) else json.dumps(x,ensure_ascii=False,indent=2))
def main():
 frames=read(OUT/'run_02/FRAME_METRICS.json')['frames'];n=0;anchors=0;members=0
 for r in frames:
  if r['variant']!='combined':continue
  sid=r['sid'];fi=r['fi'];name=f'{fi:04d}_members.npz'
  with np.load(OUT/'run_02/combined'/sid/name) as a,np.load(OUT/'run_02/feedback'/sid/name) as b,np.load(OUT/'baseline_02'/sid/f'{fi:04d}.npz') as c:
   anchors+=int(not np.array_equal(np.setdiff1d(b['target'],b['added']),c['baseline_target']))
   members+=int(not np.array_equal(a['target'],b['target']))
  n+=1
 assert n==1966
 write(E/'FEEDBACK_DIVERGENCE.json',{'frames':n,'feedback_anchor_vs_R1_differing_frames':anchors,'feedback_vs_combined_member_differing_frames':members,'status':'DEGENERATE_COINCIDENT_ARM' if not members else 'DIVERGENT','meaning':'separately executed causal tracker, no independent empirical information in this dataset; not independent foreground evidence'})
 sys.path.insert(0,str(PS));from core import decode_indices
 gtpath=R/'pc_apps/human_replay/gt_store/cap_20261010_180557/GT_V1.json';gt=read(gtpath)
 before=read(E/'BASELINE_BEFORE.json')['files'];assert sha(gtpath)==before[gtpath.relative_to(R).as_posix()]
 manifest=read(E/'js_02/cap_20261010_180557/MANIFEST.json')
 assert gt['review_status']=='reviewed' and gt['session_sha256']=={'meta':manifest['source']['meta_sha256'],'points':manifest['source']['bin_sha256']}
 rows=[];den=0;labeled=0
 for fi in range(523):
  p=PS/'output/cap_20261010_180557'/f'{fi:04d}.json';h=sha(p);assert h==before[p.relative_to(R).as_posix()]
  refs=read(p)['reference'];ids=sorted({i for o in refs for i in o['source_indices']})
  for o in refs:
   g=gt['objects'][o['id']];assert g['class_name']=='PERSON' and g['frame_idx']==fi and len(decode_indices(g['raw_point_indices']))==len(o['source_indices'])
  den+=len(ids);labeled+=bool(ids)
  rows.append({'fi':fi,'derived_output_sha256':h,'reference_source_indices_sha256':hashlib.sha256(np.array(ids,dtype='<u4').tobytes()).hexdigest(),'count':len(ids),'reviewed_object_ids':[o['id'] for o in refs]})
 assert den==57045 and labeled==53
 archive=PS/'output/cap_20261010_180557/human_reference.npz'
 assert sha(archive)==before[archive.relative_to(R).as_posix()]
 write(E/'S8_HUMAN_REFERENCE_BINDING.json',{'reviewed_GT_sha256':sha(gtpath),'GT_source_sha256':gt['session_sha256'],'GT_review_status':gt['review_status'],'frames':rows,'labeled_frames':labeled,'denominator':den,'human_reference_archive_sha256':sha(archive),'derivation_code':{'path':str(PS/'run.py'),'sha256':sha(PS/'run.py'),'functions':'gt_document,objects; original valid_raw ordinal mapping then PERSON only'},'current_mapping_recheck':'BLOCKED: original raw missing; existing mapping artifacts match initial snapshot SHA, object IDs/classes/decoded counts checked; no new raw-to-compact mapping claimed'})
 missing=read(E/'FINAL_SOURCE_AVAILABILITY.json')['time_unix'];timing=[]
 for run in ['run_01','run_02']:
  p=OUT/run/'ALL_FRAME_VERIFICATION.json';t=p.stat().st_mtime
  timing.append({'path':str(p),'sha256':sha(p),'observed_mtime_utc':datetime.fromtimestamp(t,timezone.utc).isoformat(),'observed_mtime_before_missing_check':t<missing,'meaning':'historical retained PASS; not currently rerunnable; filesystem timestamp is observed metadata, not independent trusted timestamp'})
 write(E/'VERIFICATION_TIMELINE.json',{'missing_check_utc':datetime.fromtimestamp(missing,timezone.utc).isoformat(),'evidence':timing,'current_rerun':'BLOCKED','PR05_PR07a':'historical saved evidence predates FINAL_SOURCE_AVAILABILITY; cannot regenerate from current missing inputs'})
 response='''# 独审发现回应 v2

原OPENCODE_REVIEW_02.md/jsonl原样保留，结论REVIEW_WITH_FINDINGS；本文件是作者回应，不代写审者结论。

- P2-1：FEEDBACK_DIVERGENCE逐1966帧完整NPZ集合核对，feedback原FG锚点相对R1分歧0，最终成员相对combined分歧0。单独tracker执行属实，但该数据上是零分歧退化臂，没有独立效果信息；不能称独立前景证据。
- P2-2：护栏是读取首轮完整回归（含80历史帧）后选择的拟合式后处理过滤器。0.85/0.12m/30°来自旧R3/R2常数，非本轮诊断统计推导。PR04/05明确后验护栏内及REUSED_REGRESSION，不能作为独立泛化证据，不再借PASS淡化选择偏倚。
- P2-3：VERIFICATION_TIMELINE将保留产物SHA、观察到的mtime、缺源检测时间绑定；PR05/07a是历史保存证据，早于FINAL_SOURCE_AVAILABILITY，当前不可复跑。mtime不是独立可信时间戳，限制保留。
- P3-1：S8_HUMAN_REFERENCE_BINDING绑定已审GT SHA/源SHA、523个既有输出SHA和逐帧reference源行集合SHA、53帧57045分母、GT对象PERSON身份/帧/压缩索引数量与既有human_reference.npz SHA。所有派生输出匹配初始快照。原始文件当前缺失，不能重新证明valid_raw紧凑索引到原始记录的映射；该限制显式保留，未伪造原始映射重放。
- P3-2：BROWSER_FINAL_SOURCE.json为空，原因是读取折叠区域innerText；OPENCODE_REVIEW_01.md为空是CLI启动参数失败。均保留为失败工件，不再用作成功证据。实际浏览器点击源行见BROWSER_FINAL_SOURCE_V2/BROWSER_FINAL_ADDITIONAL、截图BROWSER_FINAL_RECOVERED；真实审核原文见02。

最终FINAL_INPUT_BINDING_CHECK：原始快照captures/remote下1778文件全部当前缺失（其中主链18），跨仓11个依赖SHA仍相等。当前复跑BLOCKED，不归因、不替代原录制；冻结输出和原始验证证据保留。算法和冻结配置未改，本轮仅追加溯源统计和限定交付表述。
'''
 write(E/'REVIEW_RESPONSE_V2.md',response)
 table=(E/'ACCEPTANCE_V1.md').read_text(encoding='utf8').replace('验收表 v1','验收表 v2')
 table=table.replace('|PR04|PASS|','|PR04|PASS（后验拟合式护栏；REUSED_REGRESSION）|').replace('|PR05|PASS (首轮6×1966＋护栏2×1966独立前缀)|','|PR05|PASS（历史保留验证；后验护栏内/复用回归；当前复跑BLOCKED）|').replace('|PR07a|PASS|','|PR07a|PASS（历史保留几何证据；当前复跑BLOCKED）|').replace('|PR09|PASS (退化完整披露，非几何改善全称)|','|PR09|PASS（分开运行但feedback零分歧退化臂；非独立效果信息）|')
 table+='\n补充证据：REVIEW_RESPONSE_V2、FEEDBACK_DIVERGENCE、S8_HUMAN_REFERENCE_BINDING、VERIFICATION_TIMELINE、FINAL_INPUT_BINDING_CHECK。v1保留为历史，当前唯一表为v2；审核02原文不改。\n'
 write(E/'ACCEPTANCE_V2.md',table)
 report=(E/'FINAL_REPORT.md').read_text(encoding='utf8').replace('唯一验收见ACCEPTANCE_V1.md','唯一验收见ACCEPTANCE_V2.md')
 report=report.replace('独立feedback','单独运行feedback（本数据零分歧退化臂）').replace('独立tracker反馈','单独运行tracker反馈（本数据零分歧退化臂）')
 report+='\n\n## 独审后限定及溯源补充 v2\n\n'+response+'\n当前唯一表ACCEPTANCE_V2.md；历史FINAL_REPORT.md/ACCEPTANCE_V1.md保留，不再作为当前版本。OpenCode实际审核02为REVIEW_WITH_FINDINGS，正在针对本次补充申请03复核，尚不预填复核结论。\n'
 write(E/'FINAL_REPORT_V2.md',report)
 old=(E/'CURRENT_DELIVERY_INDEX.md').read_text(encoding='utf8');write(E/'DELIVERY_INDEX_V1.md',old)
 current=old.replace('(FINAL_REPORT.md)','(FINAL_REPORT_V2.md)').replace('唯一验收v1](ACCEPTANCE_V1.md)','唯一验收v2](ACCEPTANCE_V2.md)').replace('OpenCode原审核另存OPENCODE_REVIEW_01.md/jsonl；复核如有以下一编号保存，不覆盖','OpenCode实际审核[02原文](OPENCODE_REVIEW_02.md)：REVIEW_WITH_FINDINGS；[作者回应](REVIEW_RESPONSE_V2.md)，03只读复核结论另存；01为空是启动失败，原日志保留')
 current+='\n- 当前补充：FEEDBACK_DIVERGENCE、S8_HUMAN_REFERENCE_BINDING、VERIFICATION_TIMELINE、FINAL_INPUT_BINDING_CHECK；1778个原始路径缺失，当前复跑BLOCKED。\n- 实际点击源行：BROWSER_FINAL_SOURCE_V2/BROWSER_FINAL_ADDITIONAL；空BROWSER_FINAL_SOURCE与空审核01为失败工件，不作成功证据。\n'
 (E/'CURRENT_DELIVERY_INDEX.md').write_text(current,encoding='utf8')
 for p in [R/'docs/human_fall/WORKFLOW.md',R/'docs/human_capture/README.md']:
  s=p.read_text(encoding='utf8').replace('2026-10-14_hf_mainline_points_r1/ACCEPTANCE_V1.md','2026-10-14_hf_mainline_points_r1/ACCEPTANCE_V2.md',1).replace('2026-10-14_hf_mainline_points_r1/FINAL_REPORT.md','2026-10-14_hf_mainline_points_r1/FINAL_REPORT_V2.md',1).replace('当前[唯一验收v1]','当前[唯一验收v2]',1)
  p.write_text(s,encoding='utf8')
 with (R/'docs/human_fall/returns/HF-MAINLINE-POINTS-01.md').open('a',encoding='utf8') as f:f.write('\n## 2026-10-14 独审后补充 v2\n\n当前唯一ACCEPTANCE_V2.md，SHA256 '+sha(E/'ACCEPTANCE_V2.md')+'；FINAL_REPORT_V2及REVIEW_RESPONSE_V2逐项回应审核02，原REVIEW_WITH_FINDINGS全文保留。feedback相对R1锚点和combined成员1966帧分歧均0，明确零分歧退化臂；护栏是后验拟合式过滤、复用80帧回归；历史验证与缺源检测显式时序绑定，当前不可重跑。S8逐帧reference/已审GT/初始快照SHA补绑，原始映射当前重放仍BLOCKED；空失败工件不作成功证据。算法与冻结配置不变，申请只读03复核。\n')
 with (R/'docs/human_fall/REVIEW_LOG.md').open('a',encoding='utf8') as f:f.write('\n## 2026-10-14 HF-MAINLINE-POINTS-01 实施独审02\n\nOpenCode CLI请求opencode-go/deepseek-v4.1-flash、plan只读；会话ses_ec59b559cffezHsGe4yHKhqimZ，退出0。原结论REVIEW_WITH_FINDINGS见evidence/2026-10-14_hf_mainline_points_r1/OPENCODE_REVIEW_02.md，调用工具仅read/grep，无写/执行/代理。01因--file数组吞末尾消息启动失败，原空结论及stderr保留。作者REVIEW_RESPONSE_V2/唯一ACCEPTANCE_V2逐项回应，申请03复核，不代审者关闭结论。原始源当前缺失，复跑BLOCKED。\n')
 write(E/'REVIEW_PROMPT_03.md','''# HF-MAINLINE-POINTS-01 独审发现修复后的定向复核

按本用户原明确授权，以opencode-go/deepseek-v4.1-flash、plan只读复核。禁止写文件/执行命令/运行测试/启动服务/读取points.bin/调用其他代理。读取AGENTS、WORKFLOW当前入口、ponytail实际路径；原审核02全文原样保留，不覆盖。

本次算法/冻结配置没有改动，仅补证和限制表述。先读docs/human_fall/evidence/2026-10-14_hf_mainline_points_r1下OPENCODE_REVIEW_02.md、REVIEW_RESPONSE_V2.md、当前唯一ACCEPTANCE_V2.md、FINAL_REPORT_V2.md和CURRENT_DELIVERY_INDEX.md；再读FEEDBACK_DIVERGENCE.json、S8_HUMAN_REFERENCE_BINDING.json（头部和末尾即可，523帧逐帧摘要）、VERIFICATION_TIMELINE.json、FINAL_INPUT_BINDING_CHECK.json、BROWSER_FINAL_SOURCE_V2.json、BROWSER_FINAL_ADDITIONAL.json、tools/hf_mainline_points/resolve_review.py。确认P2-1/2/3及P3-1/2的必要修复和未消除限制；无需重复完整大数组或旧未改算法全轮审核。

feedback逐1966完整NPZ集合核对锚点分歧0、成员分歧0，明确退化臂而非独立效果证据。后验护栏拟合式过滤/REUSED_REGRESSION已入唯一表；PR05/07a明确历史保存、当前复跑BLOCKED，并以观察到的mtime/SHA/缺源检测绑定（mtime不称可信独立时间戳）。S8把参考派生输出初始快照SHA、来源GT已审SHA/原源SHA、逐帧集合SHA、对象ID/PERSON/帧/解压数量补绑；原始raw已丢，无法新重放valid_raw映射，明确BLOCKED，不要求猜测补原录制。空BROWSER_FINAL_SOURCE与空审核01标失败工件不删；实际浏览器源点击改引用V2/ADDITIONAL。最终1778个原始capture快照路径均缺失，跨仓11项SHA仍相等，作者不归因不替代。R1默认、不晋级、不声称人体收益。

请输出实际读取和技能路径、总体REVIEW_PASS/REVIEW_WITH_FINDINGS/REVIEW_BLOCKED（非ACCEPTED），对原五项逐条给出CLOSED_AS_DOCUMENTED/OPEN及理由；必要新缺陷精确定位。无身份GT/物理/原始源恢复等不可消除限制单列，不代作者写结论。最终直接输出，由调用者原样保存。
''')
 print('REVIEW RESPONSES SAVED',n,anchors,members,den,flush=True)
if __name__=='__main__':main()
