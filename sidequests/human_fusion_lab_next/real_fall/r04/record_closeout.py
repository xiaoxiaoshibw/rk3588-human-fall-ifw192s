"""Append current authorized work records; historical evidence never rewritten."""
import json
import subprocess
from pathlib import Path
from close_data_bg import ROOT,HERE,PS,sha,read

OUT=ROOT/'docs/human_fall/evidence/2026-10-14_hf_real_close_data_bg_r1'


def prepend(p, text):
    previous=p.read_text(encoding='utf8') if p.exists() else ''
    if text.splitlines()[0] in previous:raise ValueError('record already exists')
    p.write_text(text+'\n'+previous,encoding='utf8')


if __name__=='__main__':
    report=OUT/'FINAL_REPORT.md'
    text=report.read_text(encoding='utf8').replace('新3契约、原6pointset','最终4契约（增加重复/逆序时间与截断源检查）、原6pointset')
    text=text.replace('缺陷后做了一次定向返工','缺陷后做了定向返工')
    text=text.replace('当前server patch changes','当前server patch changes')
    text=text.replace('源行、低点、重复源行、长gap、非法API','源行、低点、重复/逆序源时间、重复源行、长gap、非法API')
    text=text.replace('保存端重hash实际source；读取端','保存端重hash实际source；保存回调固定提交时sid/frame/request/indices/part，仅页面绑定未变才涂色；读取端')
    report.write_text(text,encoding='utf8')
    for name in ['CURRENT_DELIVERY_INDEX.md','ACCEPTANCE_V1.md']:
        p=OUT/name;p.write_text(p.read_text(encoding='utf8').replace('browser_recheck_after_source_fix','browser_final'),encoding='utf8')
    version=read(OUT/'CURRENT_VERSION_MANIFEST.json')
    version['sha256'].update({p.relative_to(ROOT).as_posix():sha(p) for p in list(HERE.glob('*.py'))+list(HERE.glob('*.js'))+[PS/'server.py',PS/'app.js',PS/'index.html']})
    version['current_browser_evidence']='browser_final/BROWSER_CHECK.json'
    version['final_recheck']='TEST_01_FINAL_RUN.json + browser_final/BROWSER_CHECK.json; source/save race fixed and rerun, no human labels written'
    (OUT/'CURRENT_VERSION_MANIFEST.json').write_text(json.dumps(version,ensure_ascii=False,indent=2),encoding='utf8')
    log=OUT/'INDEPENDENT_REVIEW.md'
    with log.open('a',encoding='utf8') as f:f.write('''

末轮只读复核：reviewer确认UNIFIED四关联输入、报告原门槛/分母/console-r02缺口全部相符；另发现保存等待期间切帧后用可变selected给新帧涂色的同族缺口。主控捕获sid/frame/request token/indices/part，只在same()仍匹配时更新显示；reviewer已只读确认guard正确（app SHA 1d7799fc6f0ae7bb9927fa1f70c6b7a60de702e4f023d066306e79dba3d25dea）。reviewer指出首次UI回归切帧清空selection会让旧bug也通过，主控补“新帧重新选点及换HEAD后放行旧模拟POST”的根因反例；browser_final真实Edge复验PASS。模拟POST仅内存SYNTHETIC，不写任何标签。最终4契约含源时间重复/回退、截断与显示长gap过期，作者退出0；独审原3契约记录保留。独审有发现，仍未ACCEPTED。
''')
    skill='C:/Users/30680/.codex/skills/ponytail/SKILL.md'
    shared='docs/human_fall/evidence/2026-10-14_hf_real_close_data_bg_r1'
    rows={'HF-CLOSE-01':('r04收口审计与版本记录','CL01–CL03；r04原ST01–ST09逐项审计，完整入口FAIL/部分NOT_RUN/身份BLOCKED'),
          'HF-DATA-01':('源数据/ROI/标注核验与最小审阅工具','DT01–DT03软件PASS；8BOUND部分标签，S9/S8语义审核BLOCKED'),
          'HF-BG-01':('冻结背景/v2同源诊断与真实artifact重建','BG01–BG04；诊断已运行，新registration REJECTED，C静立/近地FAIL，污染/正式P等价BLOCKED')}
    for ticket,(title,status) in rows.items():
        p=ROOT/'docs/human_fall/tickets'/f'{ticket}.md'
        p.write_text(f'# {ticket}：{title}\n\n2026-10-14用户本次授权实际登记，无既有同ID执行工单；不回填历史。Codex唯一writer。\n\n当前唯一补充验收 [v1](../evidence/2026-10-14_hf_real_close_data_bg_r1/ACCEPTANCE_V1.md)，[当前报告](../evidence/2026-10-14_hf_real_close_data_bg_r1/FINAL_REPORT.md)。\n\n状态 SUBMITTED / REVIEWED_WITH_FINDINGS / STOPPED。{status}。\n\n仅离线，不改生产默认/正式loader、不启confirmed/训练/部署/采集/Git写。实际ponytail：{skill}。\n',encoding='utf8')
        r=ROOT/'docs/human_fall/returns'/f'{ticket}.md'
        with r.open('a',encoding='utf8') as f:f.write(f'''\n## 2026-10-14 本轮 / R1 / Codex

- 工单：{ticket}（{title}）；实际模型名不可得，Codex工具会话/root。唯一writer，无OpenCode实现派工。
- 唯一验收：{shared}/ACCEPTANCE_V1.md；v1；SHA {sha(OUT/'ACCEPTANCE_V1.md')}。
- 起始/结束master HEAD c21c443b0befe559e08283edb0efc2af02dcc6b8，未commit/push；22438文件含ignored/untracked基线，预存pointset未提交和README外部改动保留。
- ponytail实读：{skill}。Matplotlib技能仅用于对比图，不新增依赖。
- 状态 SUBMITTED / REVIEWED_WITH_FINDINGS / STOPPED；{status}；不ACCEPTED。

### 集中诊断与根因覆盖

当前版本/源绑定、SELF_REFERENCE空场、oracle与runtime混淆、读旧标签SHA/PROPOSED漏洞及异步保存显示漂移均有具体入口/证据；统一检查与最小修复见FINAL_REPORT与INDEPENDENT_REVIEW。原pipeline、loader、阈值、模型、GT、captures/remote未改。

### 实际变更

r04新增审计/诊断/真实重算/检查/交付工具；pointset原app/server/index最小扩展与读写绑定修复；r04 server仅限制文案修正；工单/当前入口/本轮新证据。最终SHA在SOURCE_SHA_FINAL/CURRENT_VERSION_MANIFEST，完整差异/保护核验在PRESERVATION_CHECK。新UUID配平为派生输出，首次失败产物只读保留。

### 逐条验收

{status}。完整逐ID来源、PASS/FAIL/NOT_RUN/BLOCKED见共享唯一表及FINAL_REPORT；原r04与V2表仍引用唯一历史表，不降低门、不以总测试数代替。最终4契约+6pointset+20HF06及node38/23/45/panel退出0；真Edge browser_final PASS。命令/cwd/exit/log在TEST_RUNS、TEST_01_FINAL_RUN、CURRENT_VERSION_MANIFEST、REGISTRATION_REBUILD_RUN；首次失败RUN_LOG保留。SYNTHETIC UI race不保存标签。

### 未闭合与限制

S9无可信来源绑定、S8坐标/ROI和成员/部位待人工；093958 DATA_BAD；215623/215643/233658 DATA_BLOCKED；223757缺meta；r04人体/家具/解剖GT及console正式入口未闭合；新registration REJECTED、W03资格BLOCKED，无VALID。正式完整P等价A/B受非因果动作背景约束BLOCKED。设备/物理/部署/采集NOT_RUN。

### 独立复审

非writer只读/root/readonly_review已审r04/HR-RET-V2 V2-14及本轮诊断；记录{shared}/INDEPENDENT_REVIEW.md，有发现与修复复核，不是全表PASS。r03 RS04原FAIL未关闭。当前下一步人工最小清单REVIEW_QUEUE，本轮停止，不自动进入统一核心/页面集成实施。
''')
    r=ROOT/'docs/human_fall/returns/HF-REAL-04.md'
    with r.open('a',encoding='utf8') as f:f.write(f'''\n## 2026-10-14 HF-CLOSE-01 当前收口审计附记

作者Codex /root；非writer独审/root/readonly_review。本次只收口审计，不回填原R1完成历史。唯一原表docs/human_fall/evidence/2026-10-13_hf_real_04_r1/ACCEPTANCE_V1.md保持。

当前报告：{shared}/FINAL_REPORT.md；当前SHA/原源行/过程/加载绑定CURRENT_VERSION_MANIFEST。实际ponytail {skill}。

ST01完整console入口FAIL（仍r02），ST02圈外人体BLOCKED，ST03观测事实PASS/身份BLOCKED，ST04核心软件PASS，ST05固定未验证prototype与不重复事件PASS，ST06TOP_REGION个别恶化FAIL，ST07本机浏览器节奏通过/板端NOT_RUN，ST08部分软件PASS/EXE启动NOT_RUN，ST09独审已执行有发现/语义GT BLOCKED/设备物理NOT_RUN。164/164候选不等于真实召回；f72未确认；原空场SELF_REFERENCE；RS04不关闭。

原r04 45d53b8相关已提交，HEAD当前c21c443；不改旧证据，只加新审计/修复server限制文字，保留其他编辑。相关测试/真实browser/独审已完成，详本轮共享表；SUBMITTED/REVIEWED_WITH_FINDINGS/STOPPED，未完整收口、不ACCEPTED。
''')
    entry='''## 2026-10-14 HF-REAL第一批闭环修复（本次实际授权/当前记录）

用户明确授权 **HF-CLOSE-01 / HF-DATA-01 / HF-BG-01**，复用r04和pointset r01，不创建重复原型。Codex唯一writer，非writer只读/root/readonly_review已独审，有发现/修复复核。当前[唯一补充v1](evidence/2026-10-14_hf_real_close_data_bg_r1/ACCEPTANCE_V1.md)/[交付](evidence/2026-10-14_hf_real_close_data_bg_r1/CURRENT_DELIVERY_INDEX.md)/[报告](evidence/2026-10-14_hf_real_close_data_bg_r1/FINAL_REPORT.md)。源绑定/审阅工具/同源隔离诊断/新registration真实重算已运行；S8 B55347/57045、C54069/57045，近地180/1163与4/1163失败；新artifact REJECTED，旧4个STALE，无VALID。r04未全收口、console当前仍r02，原RS04不关闭；身份/部位GT及缺原数据分别BLOCKED，S9 INVALID_BINDING、093958 DATA_BAD。SUBMITTED / REVIEWED_WITH_FINDINGS / STOPPED，非ACCEPTED；不正式启v2/confirmed、不进入统一核心集成实施、不训练/采集/部署/Git写。旧证据与生产/模型/原GT/captures只读，首尾核验有记录。实际技能ponytail；下方历史不扩大本次范围。
'''
    prepend(ROOT/'docs/human_fall/WORKFLOW.md',entry)
    prepend(ROOT/'docs/human_fall/REVIEW_LOG.md','''## 2026-10-14 HF-CLOSE/DATA/BG 当前非writer独审

一名只读/root/readonly_review，实际已审r04 ST01–ST09、HR-RET-V2 V2-14与新run。见[完整独审](evidence/2026-10-14_hf_real_close_data_bg_r1/INDEPENDENT_REVIEW.md)/[报告](evidence/2026-10-14_hf_real_close_data_bg_r1/FINAL_REPORT.md)。发现self-reference空场上界论证错误、TOP_REGION显示恶化、审阅GET来源漂移和save异步显示绑定；软件漏洞已定向修复，真Edge与契约复验。V2-14 REVIEW_COMPLETE_WITH_FINDINGS，不是全表PASS；无VALID、新registration REJECTED、低位FAIL、GT/原源BLOCKED，原RS04不关闭。r04未完整收口、console仍r02；未ACCEPTED，设备/物理/部署NOT_RUN。作者仅记录实际独审输出，不冒充审查者写文件。
''')
    prepend(ROOT/'docs/human_capture/README.md','''## 2026-10-14 HF-DATA-01 关联审阅修复（保留pointset r01）

当前HF-REAL三工单复用已完成pointset r01；8会话BOUND部分标签、S9 INVALID_BINDING、小ROI不扩展。原页增加PROPOSED最小队列/深链/当前选簇与GT上界区分，读/写实际源SHA和保存回调绑定修复。未训练/改旧GT/采集/部署/Git写。见[当前交付](../human_fall/evidence/2026-10-14_hf_real_close_data_bg_r1/CURRENT_DELIVERY_INDEX.md)与[人工队列](../human_fall/evidence/2026-10-14_hf_real_close_data_bg_r1/REVIEW_QUEUE.json)。原8941运行进程未重启，使用当前server.py --port 8942可看修复后入口；同一源码，无pointset r02。SUBMITTED/REVIEWED_WITH_FINDINGS，语义GT/生产BLOCKED，非ACCEPTED。下方既有未提交产物/入口保持。
''')
    print('current tickets/returns/entries recorded; no historical backfill')
