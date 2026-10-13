"""Append the actual audit outcome and fail the preregistered algorithm gate."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
OUT = ROOT / 'docs/human_capture/evidence/2026-10-12_hfus_d05_r5'

def load(name):
    return json.loads((OUT / name).read_text(encoding='utf-8'))

audit = load('OPENCODE_FINAL_02_STATUS.json')
assert audit['dispatch_status'] == 'PASS' and audit['exit_code'] == audit['export_exit'] == 0
assert audit['actual_models'] == ['opencode-go/deepseek-v4.1-flash']
assert load('BROWSER_VERIFICATION_V2.json')['status'] == 'PASS'
assert load('analysis_v2/COMPARISON.json')['algorithm_registered_gate'] == 'FAIL'
for name in ['FULL_CONTROL', 'FULL_ANCHOR', 'CONTROL_PARITY', 'FULL_COMPARISON_V2',
             'BANK_CONTROL_AUDIT_V2', 'BANK_ANCHOR_AUDIT_V2', 'REPLAY_CONTRACTS',
             'PERFORMANCE', 'ENDING_BOUNDARY', 'BROWSER_VERIFICATION_V2']:
    assert load(name + '_EXIT.json')['exit_code'] == 0

states = {
    'R05-01': ('PASS', '起止全SHA与范围外新增单列；扫描非原子，42外部新增不宣称冻结'),
    'R05-02': ('PASS', '原retained直接续票假设证伪；PA原票/FG证明/锚点/owner实证；raw TTL标签限制另v2派生'),
    'R05-03': ('PASS', '真实control九会话合计2605帧，逐帧精确等价R04'),
    'R05-04': ('FAIL', 'anchor九会话完整，42赢24输；近距220–224全回退，H4不晋级'),
    'R05-05': ('FAIL', '保护窗口失败；软件契约PASS，真实身份/退出资格BLOCKED'),
    'R05-06': ('FAIL', 'control8/9和anchor6/9纯p95超50ms；全机竞争环境资格另BLOCKED'),
    'R05-07': ('PASS', '真浏览器26观察23已加载，九会话/三窗/控件/SHA；pending与旧跨tab记录排除'),
    'R05-08': ('PASS', '指定独审实际模型/只读/完整指令/技能/退出核验；补审与缺陷处理记录'),
    'R05-09': ('PASS', '完整逐帧/逐场景/连续案例/SHA/最小人工包与本次追加return'),
}
payload = {'acceptance': 'ACCEPTANCE_V1.md', 'ids': {k: {'status': v[0], 'evidence': v[1]} for k, v in states.items()},
           'engineering': 'PASS_reviewable_materials', 'algorithm': 'FAIL', 'gt': 'BLOCKED',
           'production': 'BLOCKED', 'device_physics_deploy_capture': 'NOT_RUN', 'accepted': False}
with (OUT / 'ACCEPTANCE_FINAL.json').open('x', encoding='utf-8') as f:
    json.dump(payload, f, ensure_ascii=False, indent=2)
report = (OUT / 'AUDIT_READY.md').read_text(encoding='utf-8').replace('实跑审核事实（尚非FINAL）', '本轮完整交付（算法FAIL，不晋级）')
report += '\n\n## 追加收口事实与原措辞纠正\n\n'
report += (OUT / 'BOUNDARY_AND_PERFORMANCE_SUPPLEMENT_V2.md').read_text(encoding='utf-8')
report += '\n\nfar剩15FN：f0/f1两次首次确认等待，f24–26与f43–52十三次混簇；覆盖.9725–.9825/纯度.7443–.7985，高分约.9975，门均过，不能称无候选。near剩73=2确认/51混簇/20BG；turn2BG；occl61=1确认/60混簇；5m5混簇；still2首次确认。逐项FAILURE_LEDGER，诊断阈值与正式strict匹配并列，未标帧UNKNOWN。\n\n'
report += '实际指定独审01/02、STATUS/EXPORT/md及REVIEW_DEFECT_HANDLING.md；完整技能/brief与模型核验PASS。只读审核不代替人工接受。真实九会话23加载观察以BROWSER_VERIFICATION_V2为准；旧AUDIT_READY的“正在验证”属于冻结中间记录。本轮最终主控源SHA TOOLING_SOURCES_V5，推理加载SHA各SUMMARY，结束增量FINAL_INCREMENTAL_BOUNDARY。\n\n'
report += '\n字段等价限定见PARITY_SUMMARY_V2.json（22字段、非整ledger字节相等）；独审缺陷REVIEW_DEFECT_HANDLING.md与REVIEW_FINAL_SUPPLEMENT.md。人工包用MINIMAL_HUMAN_REVIEW_V2.md，旧越界包保留。\n'
report += '| ID | 状态 | 依据 |\n|---|---|---|\n' + '\n'.join('|%s|%s|%s|' % (k, *v) for k, v in states.items())
report += '\n\n工程可审查材料PASS；算法FAIL；GT/生产BLOCKED；设备/物理/部署/采集NOT_RUN；未ACCEPTED。停止扩大always-anchor；下一轮条件修正只有假设，有far41偏移.411m反例，必须新登记与完整重跑。\n'
with (OUT / 'FINAL_REPORT.md').open('x', encoding='utf-8') as f:
    f.write(report)
entry = '''# HFUS-D05-R05 当前可审查交付

唯一验收ACCEPTANCE_V1，最终裁定ACCEPTANCE_FINAL与FINAL_REPORT；算法FAIL，不晋级。字段等价限定PARITY_SUMMARY_V2；REVIEW_DEFECT_HANDLING/REVIEW_FINAL_SUPPLEMENT。
Demo v2 http://127.0.0.1:8917/ ，默认保留control。可选anchor观察远行收益与near220–224回退；九会话/三窗同步/原始人工参照/点集与模型调用来源/有限coast/SHA；BROWSER_OPERATIONS_V2、BROWSER_VERIFICATION_V2与DEMO_V2_FINAL_FAR5_XZ截图是真实操作证据。
原始D04与R04保留；runs/control与anchor各9会话合计2605帧。analysis_v2的COMPARISON、FRAME_COMPARISON、FAILURE_LEDGER、CASE_INDEX和WIN_LOSS_INDEX；CAUSAL_WINDOWS连续片段。MINIMAL_HUMAN_REVIEW_V2人工最小包；S9 INVALID_BINDING。
源码sidequests/human_fusion_lab_next/d05/r05，实际推理源SHA各SUMMARY；工具V5与结束增量SHA。指定独审01/02及缺陷处理；失败分析、旧Demo与浏览器错误不覆盖。
性能实际FAIL，环境竞争资格BLOCKED；不宣称全树冻结、板端实时或ACCEPTED。工程材料PASS；算法FAIL；GT/生产BLOCKED；设备物理部署采集NOT_RUN。
'''
with (OUT / 'CURRENT_DELIVERY_INDEX.md').open('x', encoding='utf-8') as f:
    f.write(entry)
with (ROOT / 'docs/human_capture/returns/HFUS-D05.md').open('a', encoding='utf-8') as f:
    f.write('\n\n### 2026-10-12 HFUS-D05-R05 完整离线返工回传\n\n')
    f.write('实际ponytail C:/Users/30680/.codex/skills/ponytail/SKILL.md；Codex唯一writer，代理与指定OpenCode只读。master HEAD026e06303f60ed1bbe4ddc4d037836db68da6d27；15463初始SHA，结束全树及增量非原子，42外部新增与当前HFUS-RD-01进程单列，不干预，不声称全树冻结。旧资产模型/GT/captures/生产只读，没有Git写、部署采集/网络驱动或ML启用。\n\n')
    f.write('纠正旧回传“银行自维持”推断：retained/MERGED不能直接刷新原银行；家具是独立FG高分误接受播种→有限延续→过期→再入。PA多候选同内部track导致EMA偏移实证，原票不改。H4仅更新合法bank.xy为FG候选中心。完整control/anchor各九会话TOTAL2605帧/5210新账，真实exit0；control精确R04。42收益24回退，far67→84但27赢10输，near184→185但220–224五次全部TP→FN，因此H4拒绝晋级。walk10/turn4/occl10/5m7/still51不变；家具已标错误接受不变，纯FG chair高分仍未解决。\n\n')
    f.write('R05-01/02/03/07/08/09 PASS；R05-04/05/06 FAIL；05真实ID/退出另BLOCKED；06实际pure控制8/9、新版6/9超50ms，主控内部串行不证明全机无竞争，环境资格另BLOCKED。旧R04性能PASS保留不能替代本轮失败。三次工具失败枚举/UNKNOWN NULL/SHA项数均保持源/exit/log，新v2双方完整重算。TTL raw限制v2派生复核。Demo v1与跨tab错误保留，当前v2真26观察23加载九会话/三窗/控件/SHA，pending排除console[]。\n\n')
    f.write('指定独审最终补审02实际PID%d，child/export0、实际opencode-go/deepseek-v4.1-flash、完整brief/ponytail/载体/只读核验PASS，缺陷处理另附。不替代人工ACCEPTED。工程材料PASS；算法FAIL；GT/生产BLOCKED；设备/物理/部署/采集NOT_RUN。\n\n' % audit['pid'])
    f.write('[交付入口](../evidence/2026-10-12_hfus_d05_r5/CURRENT_DELIVERY_INDEX.md)、[完整报告](../evidence/2026-10-12_hfus_d05_r5/FINAL_REPORT.md)、[逐ID状态](../evidence/2026-10-12_hfus_d05_r5/ACCEPTANCE_FINAL.json)、[Demo](http://127.0.0.1:8917/)。源SHA TOOLING_SOURCES_V5/各SUMMARY；逐帧analysis_v2与连续案例/银行账/最小人工包/结束增量皆在R05目录。下一轮HFUS-D05-R06只是离线返工编号，不启动HFUS-D06/D07；仅检验超出原.4恢复圆才修正，有far41反例，尚无新结果。\n')
print(json.dumps({'written': ['FINAL_REPORT.md', 'ACCEPTANCE_FINAL.json', 'CURRENT_DELIVERY_INDEX.md'], 'algorithm': 'FAIL', 'audit_pid': audit['pid']}))
