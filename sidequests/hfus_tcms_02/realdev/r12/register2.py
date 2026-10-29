"""S07F item registration; exclusive outputs, no data writes.

Item: HFUS-TCMS-02-REALDEV-02-S07F (branch-band-consistent single support for
the region OUTER nodes; fix continuation of S07-06 FAIL, no promotion).
Run: python -B -W error sidequests/hfus_tcms_02/realdev/r12/register2.py
"""
import hashlib
import json
import os
import subprocess
import sys
import platform
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
EV = ROOT / 'docs/human_fall/evidence/2026-10-18_hfus_tcms_02_s07f_r1'
HERE = Path(__file__).resolve().parent
OLD_EV = ROOT / 'docs/human_fall/evidence/2026-10-18_hfus_tcms_02_s07_r1'


def sha(p):
    with Path(p).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def put(p, x):
    p = Path(p)
    with p.open('x', encoding='utf8', newline='\n') as f:
        if isinstance(x, str):
            f.write(x)
        else:
            json.dump(x, f, ensure_ascii=False, indent=2, allow_nan=False)
            f.write('\n')


def scan_tree():
    result = {}
    paths = []
    for base, dirs, files in os.walk(ROOT, followlinks=False):
        dirs[:] = [n for n in dirs if n not in ('.git', 'data') and not (Path(base) / n).is_junction() and not (Path(base) / n).is_symlink()]
        for n in files:
            p = Path(base) / n
            if p.is_symlink():
                continue
            paths.append(p)
    for p in paths:
        s = p.stat()
        result[p.relative_to(ROOT).as_posix()] = [s.st_size, s.st_mtime_ns]
    return result


def verify_s07_manifest():
    mf = json.loads((OLD_EV / 'MANIFEST.json').read_text(encoding='utf8'))['files']
    bad = []
    for name, v in mf.items():
        f = OLD_EV / name
        if not f.exists():
            bad.append('MISSING ' + name)
            continue
        if f.stat().st_size != v['bytes'] or sha(f) != v['sha256']:
            bad.append('DIFF ' + name)
    return dict(entries=len(mf), problems=bad)


def main():
    if EV.exists():
        raise FileExistsError('evidence dir exists; refusing to re-register')
    started = time.time()
    tree = scan_tree()
    EV.mkdir(parents=True)
    with (EV / 'BASELINE_SCAN.json').open('x', encoding='utf8', newline='\n') as f:
        json.dump(dict(files=tree, branch=subprocess.check_output(['git', 'branch', '--show-current'], cwd=ROOT, text=True).strip(), head=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(), status=subprocess.check_output(['git', 'status', '--porcelain=v1', '--untracked-files=all'], cwd=ROOT, text=True), seconds=time.time() - started, method='size+mtime_ns full scan; no data/.git/junction traversal; bound files additionally SHA below'), f, ensure_ascii=False, allow_nan=False, separators=(',', ':'))
        f.write('\n')
    inputs = {}
    for sid in ('cap_20261017_113516', 'cap_20261018_110029'):
        inputs[sid] = {n: dict(sha256=sha(ROOT / 'data/sessions' / sid / n), bytes=(ROOT / 'data/sessions' / sid / n).stat().st_size) for n in ('meta.json', 'points.bin')}
    put(EV / 'INPUTS.json', inputs)
    frozen = {}
    for rel in sorted(os.listdir(HERE)):
        if rel.endswith('.py'):
            frozen['sidequests/hfus_tcms_02/realdev/r12/' + rel] = sha(HERE / rel)
    for rel in ('wire.py', 'calibrate.py'):
        frozen['sidequests/hfus_tcms_02/realdev/r08/' + rel] = sha(ROOT / 'sidequests/hfus_tcms_02/realdev/r08' / rel)
    for rel in ('skeleton.py', 'paths.py'):
        frozen['sidequests/human_fusion_lab_next/real_fall/r04/' + rel] = sha(ROOT / 'sidequests/human_fusion_lab_next/real_fall/r04' / rel)
    frozen['sidequests/hfus_tcms_02/realdev/r01/contracts.py'] = sha(ROOT / 'sidequests/hfus_tcms_02/realdev/r01/contracts.py')
    frozen['docs/human_capture/evidence/2026-10-09_hrskeleton_offline_r1/skeleton.py'] = sha(ROOT / 'docs/human_capture/evidence/2026-10-09_hrskeleton_offline_r1/skeleton.py')
    frozen['docs/human_fall/evidence/2026-10-18_hfus_pose_jitter_01_r1/diagnose.py'] = sha(ROOT / 'docs/human_fall/evidence/2026-10-18_hfus_pose_jitter_01_r1/diagnose.py')
    for name in ('ACCEPTANCE_V1.md', 'PROTOCOL_V1.json', 'REGION_PROTOCOL_V1.json', 'EFFECT_GATE.json', 'FOREGROUND_LEDGER.npz', 'FOREGROUND_COUNTS.json', 'RAW_OLD_SUMMARY.json', 'FG_OLD_SUMMARY.json', 'RAW_NEW_SUMMARY.json', 'FG_NEW_SUMMARY.json', 'CANDIDATE_FAILURE_DIAGNOSIS.json', 'CANDIDATE_FAILURE_DIAGNOSIS_R2.json'):
        frozen['docs/human_fall/evidence/2026-10-18_hfus_tcms_02_s07_r1/' + name] = sha(OLD_EV / name)
    put(EV / 'FROZEN_BINDINGS.json', dict(files=frozen, s07_manifest_verification=verify_s07_manifest()))
    put(EV / 'ENVIRONMENT.json', dict(python=sys.version, executable=sys.executable, platform=platform.platform(), skills=['C:/Users/30680/.config/opencode/skills/ponytail/SKILL.md'], skill_note='ponytail loaded via OpenCode skill tool (full); scientific-toolkit not read in this session', writer_session='OpenCode app session; declared model opencode-go/deepseek-v4.1-flash (not independently audited)', strategy=dict(region_support_fix='RESEARCH', contracts_replay_seal='ENGINEERING')))
    put(EV / 'ACCEPTANCE_V1.md', '''# S07F 唯一当前验收 v1（实验前冻结）

|ID|类别|验收|
|---|---|---|
|SS01|交付|输入、范围、基线、协议与冻结绑定（含 S07 证据 MANIFEST 全量复核）在执行前冻结；两段数据仍 REUSED_DEVELOPMENT 非独立测试|
|SS02|工程|唯一新变体且只改一处语义：OUTER_A/B 支撑带从 [0.33,0.88) 改为与 UPPER 分支相同的 [0.52,0.88)，远端分位数域随之；不放宽任何冻结门或 0.8m 支撑门，无 EMA/预测/补点/历史/逐帧手选；合成边界（双群带内外、连通单/多、顺序确定性、输入不变异、合同拒绝）通过|
|SS03|机制|源行级复核双纵向群根因：f190–192 及保持段 >100mm 案例的两群几何/间距/选择变化；导出支撑规则对比（原状/最大分量/顶锚/上分支邻接/带一致）并说明唯一变体选择依据；结论不超出几何证据|
|SS04|研究证据|386 帧一次官方候选运行（RAW_NEW2/FG_NEW2）：全部固定窗口、逐帧账本、支撑源行、标定复用、日志与失败保留；新候选支撑单一连通群比例与缺测帧逐帧原因|
|SS05|研究效果（冻结门复评）|复制 S07-06 全部 10 项冻结检查（同窗口/基线/分母）复评并逐项报告；任一失败=NO_PROMOTION 如实记录，不因本项修复目标而豁免|
|SS06|修复专项标准|OUTER_A：保持段最大连续步长 ≤100mm；有效帧 ≥136；相对 S07 FG_NEW 的丢失帧 ≤10 且逐帧列明原因、跨缺测步长另表；不得以整窗缺测换稳定|
|SS07|交付+独审|可复现命令/环境/源码 SHA/失败/范围核验；MANIFEST/FINAL_SEAL；逐 ID 结果；只读审核交接；独立执行另记|

复制基线= S07 冻结的 RAW_OLD 保持段与 FOREGROUND_COUNTS 原样只读使用；S07-06 的 10 项检查含义与阈值一律不改。
本项只声称"OUTER 支撑带一致性"这一处语义变化及其可验证结果；已知与修复无关的冻结项（如共同节点回归、持续标定 6 边）若仍失败按数值如实报告。
区域骨架非解剖关节；人体效果/关节精度 BLOCKED；点纯度/召回 UNKNOWN；不部署/采集/训练/下载/Git 写。
''')
    protocol = dict(item='HFUS-TCMS-02-REALDEV-02-S07F', version=1, coordinate='RAW/innolidar meters; same sessions as S07 (reused development)', data_role='REUSED_DEVELOPMENT_NOT_INDEPENDENT_TEST', windows=dict(full=[0, 386], empty=[0, 100], standing=[100, 160], opening=[160, 183], hold=[183, 334], small_motion=[334, 348], exit=[348, 386]), roi=[[.75, 2.4], [.9, 1.65], [-.4, 1.85]], foreground=dict(reuse='S07 frozen FOREGROUND_LEDGER.npz and FOREGROUND_COUNTS.json read-only; reference build and 6cm gate unchanged; no recompute'), region=dict(stage='(1) source-row mechanism review of the dual longitudinal populations; (2) register exactly ONE variant before candidate runs; (3) one official 386-frame candidate run RAW_NEW2+FG_NEW2', variant='OUTER_A/B distal support computed with eligibility band [0.52,0.88) (same as UPPER branch; previously [0.33,0.88)); distal quantile domain follows the band; every other rule, threshold, gate and contract identical to r11/regions.py', prohibited=['relaxing any frozen gate or the 0.8m support gate', 'EMA', 'prediction', 'display fill', 'future filtering', 'per-frame manual selection', 'second variant after observing outcomes'], verification='regions2.py diff vs r11/regions.py limited to the band change and docstring; resulting OUTER support single-connected-component ratio reported at 0.30m linkage'), statistics=dict(std='population sqrt(sum(axis variances))*1000 mm', steps='only consecutive source indices, distribution and max; no missing bridge; across-drop spanning steps reported separately', relative='current measured CHEST only, else null; paired denominator', edges='reuse r08 CalibrationLayer; current measurement separate from persisted state'), gate=dict(frozen='replicate the ten S07-06 checks unchanged for the new candidate (candidate FG_NEW2 vs frozen RAW_OLD)', fix='OUTER_A hold max consecutive step <=100mm; valid >=136; drops vs S07 FG_NEW <=10, each listed with reason; spanning steps table; no whole-window missing substitution'), stop='one variant only; failure retained and no promotion; NO_PROMOTION unless all ten frozen checks pass', unknown=dict(purity='UNKNOWN', recall='UNKNOWN', joint_accuracy='BLOCKED', human_effect='BLOCKED'))
    put(EV / 'PROTOCOL_V1.json', protocol)
    workflow = ROOT / 'docs/human_fall/WORKFLOW.md'
    old = workflow.read_bytes()
    entry = '''## 2026-10-18 HFUS-TCMS-02-REALDEV-02-S07F 空间单一支撑修复（进行中）

用户本聊天选定"新修复项：OUTER_A 双支撑群"，承接 S07-06 FAIL（停止推广）。本会话为唯一实现 writer（OpenCode 客户端；声明模型 opencode-go/deepseek-v4.1-flash，未独立审计；ponytail 实际路径见回传），策略 RESEARCH（区域支撑机制修复）+ENGINEERING（契约/复现/封存）。当前唯一[验收v1](evidence/2026-10-18_hfus_tcms_02_s07f_r1/ACCEPTANCE_V1.md)、[协议v1](evidence/2026-10-18_hfus_tcms_02_s07f_r1/PROTOCOL_V1.json)。隔离代码 r12；先源行机制复核双纵向群，再登记唯一变体（OUTER 支撑带与 UPPER 同带 [0.52,0.88) 且结果单一连通群验证），一次 386 帧候选运行；S07 冻结门原样复评、本项修复专项标准单列；失败保留、不推广。data/S07及更早证据/冻结源码/配置/模型只读；无部署/采集/训练/下载/驱动网络/Git 写；区域骨架非解剖关节。以下历史原字节保留。

'''
    workflow.write_bytes(entry.encode('utf8') + old)
    put(EV / 'REGISTRATION.json', dict(epoch=time.time(), acceptance_sha=sha(EV / 'ACCEPTANCE_V1.md'), protocol_sha=sha(EV / 'PROTOCOL_V1.json'), inputs_sha=sha(EV / 'INPUTS.json'), frozen_bindings_sha=sha(EV / 'FROZEN_BINDINGS.json'), workflow_old_sha=hashlib.sha256(old).hexdigest(), workflow_entry_added=True))
    print('registered', EV)


if __name__ == '__main__':
    main()
