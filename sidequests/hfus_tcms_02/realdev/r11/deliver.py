"""Append delivery records and seal new evidence; never edit historical bytes."""
import hashlib
import json
import shutil
import subprocess
from register import ROOT, EV, HERE, sha, put, inventory

ITEM='HFUS-TCMS-02-REALDEV-02-S07'
PREFIX='docs/human_fall/evidence/2026-10-18_hfus_tcms_02_s07_r1/'

def scope(name='SCOPE_CHECK.json'):
    baseline=json.loads((EV/'BASELINE_ALL.json').read_text(encoding='utf8'))
    before=baseline['files'];after=inventory(False)
    changed={}
    for p in set(before)|set(after):
        b=before.get(p);a=after.get(p)
        if b is not None and a is not None and (b['bytes'],b['mtime_ns'])==(a['bytes'],a['mtime_ns']):continue
        actual=None if a is None else sha(ROOT/p)
        if b is None or actual!=b['sha256']:changed[p]=dict(before=None if b is None else b['sha256'],after=actual)
    allowed=['sidequests/hfus_tcms_02/realdev/r11/',PREFIX]
    docs=['docs/human_fall/WORKFLOW.md','docs/human_fall/REVIEW_LOG.md','docs/human_fall/returns/'+ITEM+'.md']
    outside={p:r for p,r in changed.items() if p not in docs and not any(p.startswith(a) for a in allowed)}
    inputs=json.loads((EV/'INPUTS.json').read_text(encoding='utf8'))
    actualinputs={sid:{n:dict(sha256=sha(ROOT/'data/sessions'/sid/n),bytes=(ROOT/'data/sessions'/sid/n).stat().st_size) for n in values} for sid,values in inputs.items()}
    bindings=json.loads((EV/'EXECUTION_BINDINGS.json').read_text(encoding='utf8'))['files']
    reused={p:dict(before=v,after=sha(ROOT/p)) for p,v in bindings.items()}
    head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    put(EV/name,dict(changes=changed,outside_authorized_paths=outside,head_unchanged=head==baseline['head'],inputs_unchanged=inputs==actualinputs,inputs_after=actualinputs,reused=reused,reused_unchanged=all(r['before']==r['after'] for r in reused.values()),method='Initial full SHA over all non-data non-Git non-reparse files incl untracked and ignored; final full path size/mtime scan, changed entries rehashed; all bound inputs/reused code full rehash. Not a second all-file SHA scan.'))

def main():
    author=json.loads((EV/'RESULTS_AUTHOR.json').read_text(encoding='utf8'))
    review=json.loads((EV/'OPENCODE_REVIEW_STATUS.json').read_text(encoding='utf8'))
    transport=json.loads((EV/'OPENCODE_REVIEW_TRANSPORT_AUDIT_R3.json').read_text(encoding='utf8'))
    supplement=json.loads((EV/'OPENCODE_TRANSPORT_STATUS.json').read_text(encoding='utf8'))
    review['actual_models']=transport['actual_models']
    gate=json.loads((EV/'EFFECT_GATE.json').read_text(encoding='utf8'))
    success=(review['exit_code']==0 and review['actual_models']==['opencode-go/deepseek-v4.1-flash'] and review['source_unchanged'] and review['text_chars']>0
             and transport['request_read_observed'] and transport['ponytail_read_observed'] and transport['read_only_tools']
             and supplement['exit_code']==0 and supplement['actual_models']==review['actual_models'] and supplement['source_unchanged'] and supplement['request_read_observed'])
    # Review findings remain authoritative as raw text; caller supplies disposition.
    disposition=json.loads((EV/'REVIEW_DISPOSITION.json').read_text(encoding='utf8'))
    author['results']['S07-07']='PASS' if success and disposition['blocking_findings_open']==0 else 'FAIL'
    author['review']=dict(dispatch_success=success,independent_execution='NOT_RUN',disposition=disposition,metadata_audit='OPENCODE_REVIEW_TRANSPORT_AUDIT_R3.json',ascii_supplement='OPENCODE_TRANSPORT.md')
    put(EV/'RESULTS_FINAL.json',author)
    result='PASS（仅复用开发数据门）' if gate['PASS'] else 'FAIL；停止推广'
    text=f'''\n\n## 2026-10-18 S07 开发、自验及OpenCode审核交付\n\n- 工单{ITEM}，Codex唯一writer，SUBMITTED，非ACCEPTED。关联ENGINEERING；前景/区域/效果RESEARCH。\n- 实际技能C:/Users/30680/.codex/skills/ponytail/SKILL.md；C:/Users/30680/.codex/skills/scientific-toolkit-skill/SKILL.md；matplotlib参考。\n- 唯一验收[ACCEPTANCE_V1](../evidence/2026-10-18_hfus_tcms_02_s07_r1/ACCEPTANCE_V1.md)，SHA {sha(EV/'ACCEPTANCE_V1.md')}。\n- 逐ID：{json.dumps(author['results'],ensure_ascii=False)}。S07-06效果{result}；无GT关节精度/人体效果BLOCKED，纯度/召回UNKNOWN。\n- 根因/调用者/生命周期与全部真实变更、实验、环境、命令、失败、源码SHA、全窗口结果：[作者报告](../evidence/2026-10-18_hfus_tcms_02_s07_r1/AUTHOR_REPORT.md)。代码仅r11，复用旧关联门/候选账本/提取/标定，新增歧义封堵及LOST状态；前景冻结背景与唯一主平面区域变体。旧317/490不改，非法更新不保数。\n- OpenCode实际{review['actual_models']}，exit{review['exit_code']}，{review['seconds']:.3f}s，仅静态，独立执行NOT_RUN；前后源码SHA相同{review['source_unchanged']}。完整请求/输出/退出/处置见本轮OPENCODE_REVIEW*与REVIEW_DISPOSITION。\n- 输入两段均已用开发诊断，不是独立测试。仅离线区域骨架，不冒称解剖关节；无Git写/数据删除/部署/采集/驱动网络修改/训练/模型下载/HR09。设备/物理NOT_RUN。\n- 可复现与证据索引见HANDOFF.md；范围核验SCOPE_CHECK.json，源码快照EXECUTED_SOURCE，MANIFEST和FINAL_SEAL；历史文档追加/前置，历史原字节保留。\n'''
    ret=ROOT/'docs/human_fall/returns'/f'{ITEM}.md'
    before=ret.read_bytes() if ret.exists() else b''
    with ret.open('ab') as f:f.write(text.encode('utf8'))
    log=ROOT/'docs/human_fall/REVIEW_LOG.md';logbefore=log.read_bytes()
    with log.open('ab') as f:f.write(('\n\n## 2026-10-18 '+ITEM+' OpenCode只读审核\n\n实际模型'+str(review['actual_models'])+'；exit '+str(review['exit_code'])+'；独立执行NOT_RUN。完整[审核](evidence/2026-10-18_hfus_tcms_02_s07_r1/OPENCODE_REVIEW.md)、[处置](evidence/2026-10-18_hfus_tcms_02_s07_r1/REVIEW_DISPOSITION.json)、[逐ID](evidence/2026-10-18_hfus_tcms_02_s07_r1/RESULTS_FINAL.json)。作者效果'+result+'，非ACCEPTED。\n').encode('utf8'))
    workflow=ROOT/'docs/human_fall/WORKFLOW.md';old=workflow.read_bytes()
    workflow.write_bytes(('## 2026-10-18 '+ITEM+' 开发与OpenCode只读审核交付（SUBMITTED；效果'+result+'）\n\n当前唯一[验收v1](evidence/2026-10-18_hfus_tcms_02_s07_r1/ACCEPTANCE_V1.md)、[最终逐ID](evidence/2026-10-18_hfus_tcms_02_s07_r1/RESULTS_FINAL.json)、[交付](evidence/2026-10-18_hfus_tcms_02_s07_r1/HANDOFF.md)、[报告](evidence/2026-10-18_hfus_tcms_02_s07_r1/AUTHOR_REPORT.md)、[OpenCode审核](evidence/2026-10-18_hfus_tcms_02_s07_r1/OPENCODE_REVIEW.md)、[回传](returns/'+ITEM+'.md)。关联ENGINEERING；前景/区域RESEARCH；Codex唯一writer。两段录制REUSED_DEVELOPMENT，区域骨架非解剖关节，人体效果/关节精度BLOCKED。效果未过门即停止推广；独审仅静态，独立执行NOT_RUN。data/冻结旧源码/配置/证据/模型只读，无Git写/部署/采集/驱动网络/训练/下载/HR09。以下历史原字节保留。\n\n').encode('utf8')+old)
    put(EV/'DOCUMENT_APPEND.json',dict(return_old_sha=hashlib.sha256(before).hexdigest(),return_prefix_preserved=ret.read_bytes().startswith(before),review_log_old_sha=hashlib.sha256(logbefore).hexdigest(),review_log_prefix_preserved=log.read_bytes().startswith(logbefore),workflow_old_sha=hashlib.sha256(old).hexdigest(),workflow_suffix_preserved=workflow.read_bytes().endswith(old)))
    put(EV/'HANDOFF.md',f'''# S07 可复现交付\n\n唯一验收ACCEPTANCE_V1.md；协议PROTOCOL_V1.json、REGION_PROTOCOL_V1.json；逐ID RESULTS_FINAL.json；作者报告AUTHOR_REPORT.md；完整审核OPENCODE_REVIEW.md/JSONL/STATUS/EXPORT和REVIEW_DISPOSITION。\n\n代码D:/Code/ldiar/sidequests/hfus_tcms_02/realdev/r11，快照EXECUTED_SOURCE。命令顺序及环境/源码SHA/退出/耗时见每个*_RUN.json。重跑应在新证据轮次、重新绑定EV后运行，既有证据排他创建，不能覆盖；数据始终只读。顺序：register→bindings→reproduce（预期失败）→test_s07→replay→experiment ledger→raw_old→fg_old→mechanism→登记唯一REGION_PROTOCOL→test_regions→raw_new→fg_new→test_statistics→conclude→plots→report→review→deliver。\n\n效果{result}，关节/人体/精度BLOCKED，纯度/召回UNKNOWN；静态独审不是独立执行。所有四组所有窗口保留，跳变案例JUMP_CASES，源行FOREGROUND_LEDGER，每组FRAMES和VERIFY；旧数据逐帧ASSOCIATION_DIFF。未部署/采集/训练/下载/Git写。\n''')
    snapshots=EV/'EXECUTED_SOURCE';snapshots.mkdir()
    for p in HERE.glob('*.py'):shutil.copyfile(p,snapshots/p.name)
    scope()
    files={p.relative_to(EV).as_posix():dict(bytes=p.stat().st_size,sha256=sha(p)) for p in EV.rglob('*') if p.is_file() and p.name not in ('MANIFEST.json','FINAL_SEAL.json','FINAL_SEAL.sha256')}
    put(EV/'MANIFEST.json',dict(files=files))
    put(EV/'FINAL_SEAL.json',dict(item=ITEM,manifest_sha=sha(EV/'MANIFEST.json'),source={p.name:sha(p) for p in HERE.glob('*.py')},status='SUBMITTED'))
    put(EV/'FINAL_SEAL.sha256',sha(EV/'FINAL_SEAL.json')+'  FINAL_SEAL.json\n')
    print('delivered',EV,flush=True)

if __name__=='__main__':
    import sys
    if len(sys.argv)>1 and sys.argv[1]=='scope':scope('SCOPE_PRE_REVIEW.json')
    else:main()
