"""Assemble the S07F author report and the extractor diff artifact."""
import difflib
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'r11'))

from common2 import EV, OLD_EV, read, sha

ITEM = 'HFUS-TCMS-02-REALDEV-02-S07F'
RUNS = ('MECHANISM', 'MECHANISM_R2', 'MECHANISM_R3', 'REGISTER_VARIANT', 'RAW_NEW2', 'FG_NEW2', 'CONCLUDE', 'VERIFY2', 'TEST_REGIONS2', 'TEST_REGIONS2_R2', 'TEST_REGIONS2_R3', 'PLOTS', 'REPORT', 'REPORT_R2', 'REPORT_R3', 'REPORT_R4', 'ERRATA', 'OPENCODE_REVIEW')
WINDOWS = ('full', 'empty', 'standing', 'opening', 'hold', 'small_motion', 'exit')


def main():
    gate = read(EV / 'EFFECT_GATE2.json')
    mech = read(EV / 'MECHANISM_SUPPORT_RULES_R3.json')
    dual = read(EV / 'MECHANISM_DUAL_POP_R3.json')
    ver = read(EV / 'VERIFY2.json')
    rp = read(EV / 'REGION_PROTOCOL_V2.json')
    fgn = read(EV / 'FG_NEW2_SUMMARY.json')
    rwn = read(EV / 'RAW_NEW2_SUMMARY.json')
    old = read(OLD_EV / 'FG_NEW_SUMMARY.json')
    base = read(OLD_EV / 'RAW_OLD_SUMMARY.json')
    diff = ''.join(difflib.unified_diff(
        (HERE.parent / 'r11' / 'regions.py').read_text(encoding='utf8').splitlines(True),
        (HERE / 'regions2.py').read_text(encoding='utf8').splitlines(True),
        fromfile='r11/regions.py', tofile='r12/regions2.py', n=2))
    diff_path = EV / 'REGIONS2_DIFF.txt'
    if not diff_path.exists():
        with diff_path.open('x', encoding='utf8', newline='\n') as f:
            f.write(diff)
    run_rows = []
    for label in RUNS:
        r = read(EV / (label + '_RUN.json'))
        cmd = ' '.join('"' + c + '"' if ' ' in c else c for c in r['command'][1:])
        run_rows.append('| %s | `%s` | %d | %.1f |' % (label, cmd, r['exit_code'], r['seconds']))
    s07f = gate['frozen_checks']
    s07 = read(OLD_EV / 'EFFECT_GATE.json')['checks']
    rule_rows = []
    for k in ('OUTER_A|R0', 'OUTER_A|R1', 'OUTER_A|R4', 'OUTER_A|R5', 'OUTER_A|RB', 'OUTER_B|RB'):
        v = mech['rules'][k]
        rule_rows.append('| %s | %d | %s | %s | %d |' % (k, v['valid'], v['max_step'], v['over100'][:2], len(v['drops'])))
    win_rows = []
    for w in WINDOWS:
        a = old[w]['nodes']['OUTER_A']['raw']
        b = fgn[w]['nodes']['OUTER_A']['raw']
        c = rwn[w]['nodes']['OUTER_A']['raw']
        win_rows.append('| %s | %d/%d | %s | %d | %d/%d | %s | %d | %d/%d | %s |' % (
            w, a['valid_frames'], a['total_frames'], a['max_consecutive_step_mm'], a['missing_frames'],
            b['valid_frames'], b['total_frames'], b['max_consecutive_step_mm'], b['missing_frames'],
            c['valid_frames'], c['total_frames'], c['max_consecutive_step_mm']))
    node_rows = []
    for k in fgn['hold']['nodes']:
        cn = fgn['hold']['nodes'][k]['raw']
        on = old['hold']['nodes'][k]['raw']
        bn = base['hold']['nodes'][k]['raw']
        node_rows.append('| %s | %d | %d | %s | %s | %s |' % (
            k, cn['valid_frames'], on['valid_frames'], cn['max_consecutive_step_mm'], on['max_consecutive_step_mm'], bn['max_consecutive_step_mm']))
    edge_rows = []
    for key, e in fgn['hold']['edges'].items():
        edge_rows.append('| %s | %d | %d | %d |' % (key, e['measured_frames'], e['current_measured_calibrated_frames'], old['hold']['edges'][key]['current_measured_calibrated_frames']))
    drops_rows = ['| %s | %d | %d | %s |' % (fi, v['mask_n'], v['ncomp'], v['reason']) for fi, v in sorted(ver['drops'].items(), key=lambda kv: int(kv[0]))]
    gaps = rp['evidence']['dual_population_separation_m']
    checks_rows = ['| %s | %s | %s |' % (k, 'PASS' if s07.get(k) else 'FAIL', 'PASS' if v else 'FAIL') for k, v in s07f.items()]
    text = f'''# {ITEM} 作者交付（SUBMITTED；修复专项 PASS；冻结门 8/10；不推广）

修复目标：S07-06 的 OUTER_A 双纵向支撑群跳变（保持段最大 900mm）。本项登记唯一变体：OUTER_A/B 支撑带与 UPPER 同带 [0.52,0.88)（原 [0.33,0.88)），远端分位数域随之；其余规则/门/契约不变。策略 RESEARCH（区域支撑机制）+ENGINEERING（契约/复现/封存）；唯一 writer 本会话（OpenCode 客户端；声明模型 opencode-go/deepseek-v4.1-flash，未独立审计）；ponytail 实际路径 C:/Users/30680/.config/opencode/skills/ponytail/SKILL.md（skill 工具加载，full）。

- 唯一验收 [ACCEPTANCE_V1.md](ACCEPTANCE_V1.md) SHA {sha(EV / 'ACCEPTANCE_V1.md')}
- 协议 [PROTOCOL_V1.json](PROTOCOL_V1.json) SHA {sha(EV / 'PROTOCOL_V1.json')}；变体登记 [REGION_PROTOCOL_V2.json](REGION_PROTOCOL_V2.json) SHA {sha(EV / 'REGION_PROTOCOL_V2.json')}
- 隔离代码 sidequests/hfus_tcms_02/realdev/r12；数据与 S07 证据只读（159/159 MANIFEST 复核一致，见 FROZEN_BINDINGS.json）

## 机制复核（SS03）

- r11 提取器掩码复刻与 S07 FG_NEW partitions 全帧一致：{mech['mask_replica']['frames']} 帧 × 13 节点 = {mech['mask_replica']['nodes']} 次比较，0 不一致。
- 保持段 OUTER_A 双纵向群：下带 frac .33-.44 与上带 frac .72-.88，两群沿主轴最大间隙在案例帧上为 0.41-0.86m（f190-192 = 0.838/0.855/0.855m；全量见 REGION_PROTOCOL_V2_ERRATA.json）；两群横向位置接近，r0 组内中位数随成员数在群间切换（f190-192 为先例）。r11 保持段 OUTER_A 掩码 {mech['r11_hold_multicomponent_frames']} of 151 帧为多连通分量。
- 支撑规则对比（保持段，全部从源行重算；R1=最大分量、R4=顶锚分量、R5=上分支邻接分量、RB=带内远端分位数）：

| 规则 | 有效帧 | 最大连续步长 mm | >100mm 首例 | 缺测帧 |
|---|---|---|---|---|
{chr(10).join(rule_rows)}

- 结论：分量挑选类规则（R1/R4/R5）在保持段或群间切换、或缺测过多；RB 保持单一连通支撑（{ver['connectivity']['single_component']}/{ver['connectivity']['hold_frames']}，0.30m 连接）并覆盖 145/151。登记的唯一变体 = RB。
- 合成边界（test_regions2）：下带群在 r11 掩码中包含、在 S07F 掩码中被排除；中位数方向、单连通、非 OUTER 节点逐字节相等、排列确定性、契约拒绝均通过。

## 变体与差异（SS02）

REGIONS2_DIFF.txt（r11/regions.py → r12/regions2.py）为完整差异：docstring、import（common2）、OUTER 带行 + 注释，以及 1 处冗余 np.asarray 包装（BRANCHES_NOT_SEPARATED 检查内，等值表达式，数值语义相同；原样保留并在此披露）。语义变化仅 OUTER 带 [0.33,0.88)→[0.52,0.88) 一处；0.8m 支撑门、几何阈值、参数、契约均未改。

## 运行记录（SS01/SS04）

| 标签 | 命令 | exit | 秒 |
|---|---|---|---|
{chr(10).join(run_rows)}

MECHANISM 首轮 exit1（rejected 帧的 diagnostics 无 partitions）、TEST_REGIONS2 两轮失败、REPORT 三轮失败均原样保留（REPORT 各行于本报告首版后补列；ERRATA 与 OPENCODE_REVIEW 亦在首版后运行）。每次运行 source_sha/协议 SHA 见对应 *_RUN.json。

## 效果（SS05/SS06）

冻结门十项（S07-06 原阈值，候选 FG_NEW2 vs 冻结 RAW_OLD/FOREGROUND_COUNTS）：

| 检查 | S07 | S07F |
|---|---|---|
{chr(10).join(checks_rows)}

- 冻结门通过 {gate['ten_passed']}/10（S07 为 {gate['s07_ten_passed']}/10）；仍失败：{', '.join(k for k, v in s07f.items() if not v)}。决定：{gate['decision']}。
- 修复专项：OUTER_A 保持段最大连续步长 {fgn['hold']['nodes']['OUTER_A']['raw']['max_consecutive_step_mm']:.1f}mm ≤ 100（S07 900.0）；有效 {fgn['hold']['nodes']['OUTER_A']['raw']['valid_frames']}/151 ≥ 136；缺测 {len(ver['drops'])} ≤ 10 且逐帧列明；跨缺测步长 {gate['fix']['spanning_steps']} 全部 ≤ 100mm。

## 逐窗口 OUTER_A（S07 FG_NEW vs S07F FG_NEW2 vs S07F RAW_NEW2）

| 窗口 | S07 有效/全 | S07 最大步长 | S07 缺测 | S07F FG 有效/全 | S07F FG 最大步长 | S07F FG 缺测 | S07F RAW 有效/全 | S07F RAW 最大步长 |
|---|---|---|---|---|---|---|---|---|
{chr(10).join(win_rows)}

## 保持段逐节点（FG_NEW2 vs S07 FG_NEW vs 冻结基线 RAW_OLD）

| 节点 | 有效(新/S07) | 最大步长 (新/S07/基线) mm |
|---|---|---|
{chr(10).join(node_rows)}

（其余节点与 S07 完全一致，因为只有 OUTER 代码路径变化。）

## 持续标定边（保持段，当前测量且 CALIBRATED 帧数）

| 边 | 测量帧 | 新 cal≥75 | S07 cal≥75 |
|---|---|---|---|
{chr(10).join(edge_rows)}

仍为 5 条 ≥75（< 6 门），与本修复无关。

## 缺测帧（SS06 披露）

| 帧 | 掩码点数 | 连通分量 | 原因 |
|---|---|---|---|
{chr(10).join(drops_rows)}

全部为掩码点数 5 < 6（原始支撑门），无整窗缺测替代；跨缺测步长见上。

## 核验（SS04）

- summarize(FRAMES)==SUMMARY（两组）、逐节点源行重算最大误差 < 1e-10m、386 帧/组：{ver['summary_reconciliation']}
- 单一连通群比例 {ver['connectivity']['single_component']}/{ver['connectivity']['hold_frames']}（hist {ver['connectivity']['component_hist']}）；缺测帧与登记机制预期一致。
- 相对 S07 位置差（双有效帧）：n={ver['outer_a_delta_vs_s07_mm']['n']}，min/p50/max = {ver['outer_a_delta_vs_s07_mm']['min']}/{ver['outer_a_delta_vs_s07_mm']['p50']}/{ver['outer_a_delta_vs_s07_mm']['max']}mm —— 最大值来自 f191（S07 中位点在被修正的下带群内）。

## 边界与限制

- 两段数据 REUSED_DEVELOPMENT 非独立测试；区域骨架非解剖关节，人体效果/关节精度 BLOCKED，点纯度/召回 UNKNOWN。
- S07F 只声称 OUTER 带一致性这一处语义变化及其可验证结果；共同节点回归（4 节点 10-16mm）与持续标定 6 边问题在本修复范围之外，仍按数值保留。
- 独立执行 NOT_RUN；未部署/采集/训练/下载/驱动网络/Git 写。
- 复现顺序：register2 → MECHANISM(_R2,_R3) → REGISTER_VARIANT → RAW_NEW2 → FG_NEW2 → CONCLUDE → VERIFY2 → TEST_REGIONS2(_R2,_R3) → PLOTS → REPORT → DELIVER（全部经 execute2 记录；重跑须新证据轮次、排他创建）。
'''
    with (EV / 'AUTHOR_REPORT.md').open('x', encoding='utf8', newline='\n') as f:
        f.write(text)
    print('report written', flush=True)


if __name__ == '__main__':
    main()
