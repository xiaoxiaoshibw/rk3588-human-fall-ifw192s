"""Append the completed independent review and correct record wording, not scores."""
import hashlib
import json
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[4]
OUT = ROOT / 'docs/human_capture/evidence/2026-10-12_hfus_d05_r4'
status = json.loads((OUT / 'OPENCODE_FINAL_02_STATUS.json').read_text(encoding='utf-8'))
assert status['exit_code'] == status['export_exit'] == 0
assert status['dispatch_status'] == 'PASS' and status['carrier_verified']
assert status['actual_models'] == ['opencode-go/deepseek-v4.1-flash']
assert status['skill_read'] and status['instruction_read'] and status['complete_text']
review = (OUT / 'OPENCODE_FINAL_02.md').read_text(encoding='utf-8')
assert 'REVIEW_COMPLETE' in review
report = (OUT / 'FINAL_REPORT.md').read_text(encoding='utf-8')
assert '实际9×2605完整新账' in report
report = report.replace('实际9×2605完整新账', '实际9会话合计2605帧完整新账')
report = report.replace('最终补审另附', '最终补审02已实际完成')
report = report.replace('剩余补审记录另附', '补审02已完成并附真实进程状态')
report = report.replace('缺陷处理另补审', '缺陷处理与补审02均完成')
report = report.replace('缺陷处理另补', '缺陷处理已闭合')
report = report.replace('缺陷处理补审', '缺陷处理补审02完成')
report = report.replace('缺陷处理另补审', '缺陷处理补审02完成')
report = report.replace('缺陷处理补审02完成02完成', '缺陷处理补审02完成')
report = report.replace('缺陷处理另补审', '缺陷处理补审02完成')
report = report.replace('工程缺件已修，补审另附', '工程缺件已修，补审02实际完成')
report = report.replace('CURRENT_DELIVERY_INDEX.md', 'CURRENT_DELIVERY_INDEX_V2.md')
report += '''

## 追加纠正与独审闭合（2026-10-12，V2）

旧FINAL_REPORT及return中的“9×2605”措辞保留为历史，明确纠正为九会话**合计2605帧**：304/258/464/239/202/238/251/523/126。五套新实跑base/A06/split/gate/fast各2605帧，共13025 ledger行；不是每会话2605帧，不改任何原始计数或评分。各轮验收表ACCEPTANCE_V1保持冻结；此处只是最终材料V2。

OPENCODE_FINAL_02：PID27084、420.659秒、child exit0、wrapper exit0、export exit0、actual model opencode-go/deepseek-v4.1-flash；完整brief/ponytail实际路径读取、carrier核验、只读grep/read、REVIEW_COMPLETE。STATUS与EXPORT为实际进程/模型依据，不以审核自述替代完成。其逐项确认P1-1真实九会话/19条DOM、P1-2独审完成、P2-3跨轮未完成分析增长已经披露、P2-4当前8915导航闭合；未发现阻断当前工程交付的缺件。独审未重跑浏览器或多GB评测，其判断限于实际文件证据；不能等同人工算法接受。

非阻断限制保留：播放/暂停原日志只记录停下后的“播放”按钮态；旧8914 README明确为历史，由本V2入口引导，不修改其冻结SHA。补充BROWSER_OPERATIONS_V4保存近距f220 gate/fast同帧实物与键盘221；其中初次fill输入尚未触发change的f0/输入220不一致行标为未完成，不能纳入PASS。实际键盘ArrowUp+Tab触发同步加载，完整V3验收结果不被该未完成行替代。

结束全树15402文件实际SHA之后新增的Demo v2/审核/报告/return等，在FINAL_INCREMENTAL_BOUNDARY逐项重新SHA登记，并复核所有实跑SUMMARY加载源与TOOLING_SOURCES_V3。未变化size+mtime沿用先前实际SHA，不冒称再次全树内容冻结；.git内部、自身输出不在扫描，外部lock历史消失仍单列。H1/H2/H3源、配置、原模型与GT不因补审修改。新增两个收口脚本是材料工具，不进入算法和性能。

工程PASS为材料与当前可操作Demo闭合；算法FAIL、GT BLOCKED、生产BLOCKED，设备/部署/采集/物理NOT_RUN，不ACCEPTED。下一轮证据依据仍是银行自支持与单核混簇，未登记或运行该方向，不能将建议当成果。
'''

def write_new(name, text):
    with (OUT / name).open('x', encoding='utf-8') as f:
        f.write(text)


write_new('FINAL_REPORT_V2.md', report)
rows = []
for line in report.splitlines():
    match = re.match(r'\| (R0[234]-\d+) \| (PASS|FAIL|NOT_RUN|BLOCKED) \| (.*?) \|$', line)
    if match:
        rows.append(dict(zip(['id', 'status', 'basis'], match.groups())))
assert len(rows) == 27 and len({r['id'] for r in rows}) == 27
write_new('ACCEPTANCE_FINAL_V2.json', json.dumps({
    'status': 'SUBMITTED_SELF_CHECK_NOT_ACCEPTED', 'acceptance': rows,
    'engineering': 'PASS', 'algorithm': 'FAIL', 'GT': 'BLOCKED', 'production': 'BLOCKED',
    'device_deploy_capture_physics': 'NOT_RUN', 'review': 'OPENCODE_FINAL_02_STATUS.json',
    'unchanged_acceptance': 'each round ACCEPTANCE_V1.md; V2 is a record correction, not a new standard'
}, ensure_ascii=False, indent=2))
write_new('CURRENT_DELIVERY_INDEX_V2.md', '''# 当前交付入口（V2，2026-10-12）

当前可操作Demo：[8915三同步视图](http://127.0.0.1:8915/)。启动说明：sidequests/human_fusion_lab_next/d05/r04/demo_v2/README.md。当前选择fast，R03失败gate可同帧对照。旧r04/README与8914为历史，不作为当前入口。

最终完整结果：FINAL_REPORT_V2.md / ACCEPTANCE_FINAL_V2.json；逐ID标准仍为各轮唯一ACCEPTANCE_V1.md。真正加载源码在各runs/*SUMMARY.json，工具及当前Demo SHA在TOOLING_SOURCES_V3.json；结束增量实际SHA在FINAL_INCREMENTAL_BOUNDARY.json。原始结果不改。

真实九会话/19条操作：BROWSER_OPERATIONS_V3.json / BROWSER_FULL_VERIFICATION.json；补充f220失败/成功版本、键盘步进在BROWSER_OPERATIONS_V4.json（含一条未完成填值动作，明确排除PASS）。截图DEMO_V2_FINAL_FAR_XZ.jpg与DEMO_V2_NEAR_F220_GATE.jpg。

指定独审01/02的md、STATUS、EXPORT及FINAL_REVIEW_DEFECT_HANDLING/GROWTH_PROVENANCE留在本目录。两次实际exit0/export0/模型核验，补审02闭合工程缺件；独审不替代人工ACCEPTED。人工最小包MINIMAL_HUMAN_REVIEW_PACKAGE_V2.json，S9 INVALID_BINDING。追加回传docs/human_capture/returns/HFUS-D05.md。

工程PASS（当前材料）；算法FAIL（部分收益）；GT/生产BLOCKED；设备/部署/采集/物理NOT_RUN；未ACCEPTED。
''')
return_path = ROOT / 'docs/human_capture/returns/HFUS-D05.md'
with return_path.open('a', encoding='utf-8') as f:
    f.write('''

### 2026-10-12 R02/R03/R04 最终补审与措辞纠正（追加，不改旧账）

前述“9×2605”明确纠正：九会话合计2605帧，逐会话304/258/464/239/202/238/251/523/126；五套base/A06/split/gate/fast完整实跑共13025 ledger行。没有23445帧的单轮实验；PARITY_SUMMARY及各SUMMARY/ledger计数未改。最终报告材料V2与ACCEPTANCE_FINAL_V2只纠正记录，原唯一ACCEPTANCE_V1标准与原FAIL/BLOCKED保留。

OPENCODE_FINAL_02实际PID27084，420.659s，child/wrapper/export均exit0；实际opencode-go/deepseek-v4.1-flash，完整brief/ponytail读取、载体核验、只读grep/read、REVIEW_COMPLETE，见真实STATUS/EXPORT/md。独审核验九会话19条DOM、三窗SHA/索引时间一致；P1-1/P1-2/P2-4闭合，P2-3未完成新分析增长与非原子范围已披露，不阻断当前工程交付。独审未自行重跑浏览器或大ledger，不替代人工接受。

当前唯一入口：[R04交付V2](../evidence/2026-10-12_hfus_d05_r4/CURRENT_DELIVERY_INDEX_V2.md)、[最终报告V2](../evidence/2026-10-12_hfus_d05_r4/FINAL_REPORT_V2.md)、[逐ID自验](../evidence/2026-10-12_hfus_d05_r4/ACCEPTANCE_FINAL_V2.json)、[当前Demo](http://127.0.0.1:8915/)。Demo v2/source工具实际SHA仍TOOLING_SOURCES_V3，各实跑加载源仍各SUMMARY。两个新收口脚本只写材料，不入算法；最终新增/变更材料SHA与实际加载源复核另见FINAL_INCREMENTAL_BOUNDARY。初次fill数值但尚未触发change的补充浏览器行明确未完成，真正gate/fast f220及键盘221另有加载DOM；不冒充成功动作。

逐ID状态维持报告表：R02-01..05 PASS、06/07 BLOCKED、08/09 FAIL、10/11 PASS；R03-01..03 PASS、04 FAIL、05 BLOCKED、06 PASS、07 FAIL、08/09 PASS；R04-01..07 PASS（R04-03是9会话合计2605帧，R04-06补审02已实际完成）。工程PASS指当前材料完整可审；算法FAIL，far32/turn2/occl61FN及家具高分自维持未解决，H2 near184→179拒绝晋级；GT与生产BLOCKED，S9 INVALID_BINDING，设备/部署/采集/物理NOT_RUN。未ACCEPTED。

唯一writer主控；实际skill C:/Users/30680/.codex/skills/ponytail/SKILL.md；master HEAD026e06303f60ed1bbe4ddc4d037836db68da6d27。没有commit/push/reset/checkout/clean/部署/采集/驱动网络或原模型GT修改；旧失败与评分保留。下一方向为银行自支持/单核混簇的证据驱动单因素登记，本次不把未运行建议当交付成果。
''')
entry = '''## 2026-10-12 HFUS-D05 离线返工最终交付 V2（当前入口）

仅HUMAN-FUSION隔离离线范围，原D05及R02/R03/R04唯一ACCEPTANCE_V1不变。当前：[交付入口V2](evidence/2026-10-12_hfus_d05_r4/CURRENT_DELIVERY_INDEX_V2.md)、[完整结果V2](evidence/2026-10-12_hfus_d05_r4/FINAL_REPORT_V2.md)、[逐ID状态](evidence/2026-10-12_hfus_d05_r4/ACCEPTANCE_FINAL_V2.json)、[追加回传](returns/HFUS-D05.md)、[当前三窗Demo](http://127.0.0.1:8915/)。九会话合计2605帧，独审02真实exit0/export0完成；算法FAIL、GT/生产BLOCKED、未ACCEPTED。人工最小包仍V2，S9 INVALID_BINDING。旧报告/8914/失败记录均保留，以下入口为历史。

'''
readme = ROOT / 'docs/human_capture/README.md'
original = readme.read_text(encoding='utf-8')
assert entry not in original
readme.write_text(entry + original, encoding='utf-8')
print(json.dumps({'written': ['FINAL_REPORT_V2.md', 'ACCEPTANCE_FINAL_V2.json', 'CURRENT_DELIVERY_INDEX_V2.md'],
                  'acceptance_ids': len(rows), 'review_actual_exit': status['exit_code'],
                  'report_sha256': hashlib.sha256((OUT / 'FINAL_REPORT_V2.md').read_bytes()).hexdigest()}, ensure_ascii=True))
