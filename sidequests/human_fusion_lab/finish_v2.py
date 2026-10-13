"""Write the concrete delivery from real run artifacts; preserve prior attempts."""
import hashlib
import json
import pathlib
import statistics

root = pathlib.Path(__file__).resolve().parents[2]
lab = root / 'sidequests/human_fusion_lab'
out = root / 'docs/human_capture/evidence/2026-10-11_human_fusion_demo_v2_r1'
read = lambda n: json.loads((out / n).read_text(encoding='utf-8'))
comparison = read('COMPARISON.json')
cases = read('CASES.json')
details = read('CASE_DETAILS.json')
browser = read('BROWSER_CHECK_03.json')
assert browser['status'] == 'PASS'
baseline = read('BASELINE.json')
changed = []
checked = 0
for name, v in baseline['files'].items():
    if 'sha256' not in v or name == 'docs/human_capture/README.md':
        continue
    p = root / name
    h = hashlib.sha256()
    if p.is_file():
        with p.open('rb') as f:
            for block in iter(lambda: f.read(1024 * 1024), b''):
                h.update(block)
        current = h.hexdigest()
    else:
        current = 'MISSING'
    checked += 1
    if current != v['sha256']:
        changed.append({'path': name, 'before': v['sha256'], 'after': current, 'modified_local': str(p.stat().st_mtime) if p.exists() else None})
(out / 'FREEZE_FINAL.json').write_text(json.dumps({'checked': checked, 'intentional_original_change': ['docs/human_capture/README.md: prepend current authorization only'], 'changed': changed, 'status': 'BLOCKED' if changed else 'PASS'}, ensure_ascii=False, indent=2), encoding='utf-8')

# Preserve the exact pre-diagnostic runtime used by the completed full replay.
# Its only later algorithm-neutral change added layer_observations to responses.
source = (lab / 'v2_runtime.js').read_text(encoding='utf-8')
start = source.index('  const fgSet=new Set(st.det.foreground());')
end = source.index('  const events=[];', start)
source = source[:start] + source[end:]
source = source.replace('foreground:st.det.foreground(),layer_observations,coordinate:', 'foreground:st.det.foreground(),coordinate:')
(out / 'FULL_REPLAY_RUNTIME_PRE_DIAGNOSTICS.js').write_text(source, encoding='utf-8')

lines = ['# HUMAN-FUSION Demo V2 实际交付', '',
         '2026-10-11（Asia/Shanghai）。SUBMITTED；软件逐项作者自验通过，S9可信GT/真实骨架资格/整树冻结仍BLOCKED，未ACCEPTED。无部署、生产接入、采集、提交或推送。', '',
         '## 启动与查看', '',
         '当前本机服务已运行：[打开 Demo V2](http://127.0.0.1:8798/)。双击 `D:\\Code\\ldiar\\sidequests\\human_fusion_lab\\start_demo_v2.cmd`；或在仓库根运行 `node sidequests/human_fusion_lab/server_v2.js 8798`。仅监听127.0.0.1，需要本机既有Node和九会话文件。', '',
         '先选择会话和模型；播放/暂停、上一帧/下一帧、拖动帧条、重置均可用。3D、XY俯视、XZ侧视同步；分层勾选原始点、背景过滤后点、候选、分类着色、GT和轨迹。“聚焦人体/当前候选”可以放大真实人体点。原始点保留原成员，仅统一乘已有研究R/T用于显示，并非已经通过物理验收的坐标。', '',
         '右侧案例下拉直接跳转35个代表性帧。点击候选行看同点集四模型分数、点数、GT距离、几何支撑和分层诊断。四模型比较均重新从当前候选完整原始行提取51/69维特征；模型切换另触发管线从帧0重放，其保留状态与候选可能改变。检测时间仅含engine.tick，不含四模型对比分数、点云IO、HTTP与绘制，不等于浏览器帧率。', '',
         '人工标注：暂停→打开圈点→任意视图拖矩形（投影内所有深度点，需3D框进一步裁剪）或填XYZ框选点→选类别/人体编号→保存本帧草稿→下载。可导入或撤销本帧草稿；草稿是raw28B原始行索引，带实际meta/bin SHA与坐标契约，永远不自动成为可信GT。下载后可运行 `node sidequests/human_fusion_lab/annotation_v2.js draft.json NEW-output.json` 校验索引/边界/同帧编号/重叠/源点/绑定并导出新绑定草稿；不能覆盖既有文件。', '',
         '## 真实运行和代表帧', '',
         '截图由本机Chrome实际执行V2并通过CDP截取；原始点全部来自captures/remote，未生成模拟点云、未注入检测结果。九会话F0截图：`SESSION_cap_*_F0_03.png`。', '']
examples = [('近距成功', 'http://127.0.0.1:8798/?sid=cap_20261010_175429&model=xgb69_candidate&index=20', 'SUCCESS_NEAR_F20_03.png', 'S3-near f20：1167候选点；同候选RF51原0.980、XGB69约0.998；GT TP1/FP0/FN0。橙轴为表面几何代理，不是人体关节。'),
            ('遮挡漏检', 'http://127.0.0.1:8798/?sid=cap_20261010_180235&model=xgb69_candidate&index=128', 'PERSON_MISS_F128_03.png', 'S6 f128：GT人体33原始点→A链最终前景18点→对应候选覆盖0。另一处380点候选与该人体不对应，RF51原约0.88/XGB约0.01；人体漏检与模型分歧同时显示。'),
            ('家具误检', 'http://127.0.0.1:8798/?sid=cap_20261010_175227&model=rf51_baseline&index=20', 'FURNITURE_RF51_F20_03.png', 'S1空场 f20：RF51预测人体，可信家具GT重叠证实误检；同候选XGB拒绝。S1属于训练负样本，不能把此成功拒绝当独立家具泛化。')]
for title, url, image, note in examples:
    lines += [f'[{title}：打开真实帧]({url})。{note}', '', f'![{title}]({image})', '']
lines += ['S9示例：[f0双人会话](http://127.0.0.1:8798/?sid=cap_20261010_180751&model=xgb69_candidate&index=0)，GT UNKNOWN。见S9_UNKNOWN_F0_03.png；不计算双人GT指标。', '',
          '## 全帧运行与跨会话验证', '',
          '九会话共2605帧，两管线18次运行共5210 tick；全部同帧ID唯一，回退/重置后候选/分数/ID确定性复验通过。原21次共享ID缺陷由每轨每帧一对一关联和一次投票修复；V1权重/算法源只读，V2各模型在每个session/segment重置都使用现有UniqueTracker。18次运行明细在cap_*__*.json，原验证日志仍保留最后冻结断言失败。', '',
          'TP/FP/FN为0.75m XY一对一门下的观测次数，不是独立受试人数。accepted>=0.35；strong>=0.55。UNKNOWN不算负例。非空场缺少完整家具GT，未匹配预测仅称FP，不能统称家具。S9全未知显示“—”，没有可靠0/0/0结论。', '',
          '| 会话 | 已标 / 未知帧 | RF51候选 TP/FP/FN | XGB候选 TP/FP/FN | RF51轨迹 TP/FP/FN | XGB轨迹 TP/FP/FN |',
          '|---|---:|---:|---:|---:|---:|']
fmt = lambda v: '/'.join(str(v[k]) for k in ['tp','fp','fn'])
rows = comparison['rows']
for a, b in zip(rows[::2], rows[1::2]):
    valid = a['gt_known'] > 0
    values = [fmt(r[k]) if valid else '— UNKNOWN' for r,k in [(a,'candidate'),(b,'candidate'),(a,'track'),(b,'track')]]
    lines.append(f"| {a['activity']} | {a['gt_known']} / {a['gt_unknown']} | " + ' | '.join(values) + ' |')
lines += ['', 'S1 RF51的604个未匹配候选中，566个有>=80%家具点重叠；XGB为0。S6 XGB仍漏6次，确认轨迹仍漏10次。远距/长静止标注稀疏，不能将已标帧召回推广到全会话。训练S1/S3-near/S4/S5；历史验证S3-far；历史测试S7/S8；压力S6；S9 BLOCKED。所有分组来自既有AUDIT/训练记录，历史测试曾被观察。独立未见人员/新场景、独立跨会话家具负样本泛化仍UNKNOWN；本轮没有训练或挑测试参数。', '',
          '### 相同候选评分对比', '',
          '下表分别固定RF51和XGB管线生成的当前候选，四模型复评分后累计已标帧GT对照。同组内点集相同；跨组候选和保留状态不同。仅分类评分，无独立跟踪对拍含义。', '',
          '| 固定候选管线 | 复评分模型 | TP / FP / FN |', '|---|---|---:|']
for anchor in ['rf51_baseline','xgb69_candidate']:
    for m in comparison['models']:
        total = {k:sum(r['same_candidate'][m][k] for r in rows if r['model']==anchor) for k in ['tp','fp','fn']}
        lines.append(f'| {anchor} | {m} | {fmt(total)} |')
lines += ['', '## 根因与修复边界', '',
          '- 跟踪：旧FusionTracker逐候选找最近active轨迹，没有claimed集合，会多候选共享ID并多次投票。V2在engine._tick_fusion之前确保使用UniqueTracker，覆盖begin和segment重置，不修改V1/生产。每帧一票、失配0票、寿命及9×2重放验证通过。',
          '- 家具：S1真实候选的几何/高度特征可像人体，原RF51高分；共同候选上的新RF/XGB可拒绝其中大量家具。研究模型看过S1，尚缺独立家具会话负样本验证。不能只降低阈值修复遮挡漏检。',
          '- 漏检：S6 f128为提案层失败，33个GT原始点中18点保留、没有对应候选。rf51 f91为303→55点且无对应候选。当前前景诊断是A链清理/保留后的最终点集，BG与cleanup不能用此字段单独归因。原只读ATTRIBUTION另记录背景/提案失败；见CASE_DETAILS.json，所有推断按实际点支撑限定。',
          '- S9：GT_V1/V2、draft和各备份均绑定aaaa…，meta绑定缺失；无法从现有声明证明人工标签属于当前文件。V2明确拒绝该绑定，并提供新原始行标注+实际双SHA验证，消除新草稿的错误绑定路径。历史可信GT恢复G01仍BLOCKED，需要真实重标/人工重新确认；本轮不伪造GT_V3。', '',
          '## 骨架实现状态与可观测性', '',
          '| 层 | 已存在内容 | 当前资格 |', '|---|---|---|',
          '| 雷达到地面坐标 | core/leveling.js使用既有R/T；可能来自参考地面，但不是本轮可靠物理标定 | UNCALIBRATED |',
          '| 人体分割 | V1 A/B融合候选及RF/XGB识别，具备真实点索引；家具/遮挡失败保留 | 离线可观察，未生产验收 |',
          '| 人体关键点 | pc_apps/human_limb有17点/6点启发式旧算法，README记录六代真实失败；HR-SKELETON-OFFLINE r1有5–7区域节点和独立时序原型 | 不是不存在算法；已有算法的真人GT效果仍BLOCKED |',
          '| 拓扑连接 | 旧limb_lib有BONES；本V2只连upper/middle/lower三表面带中心 | GEOMETRIC_PROXY_ONLY，非解剖骨架 |',
          '| 姿态与跌倒 | 主线存在相关代码；融合轨迹缺乏有效pose_history，当前演示不输出有效姿态/跌倒结论 | UNKNOWN |', '',
          '既有skeleton.py normalize/nodes/process/SkeletonTracker代码已核查；既有15项纯数学/合成回归在本轮-W error重跑通过，日志existing_skeleton_tests.log。真实120行先前仍BLOCKED_GT，不把合成测试改成真人效果。旧limb_lib_test仅2个合成人形测试；未在V2执行或复活其失败的人体自动锁定。', '',
          '可观测性固定抽取每个已标会话首/中/末annotated ordinal，而非按成功帧挑选；OBSERVABILITY.json仅列>=80%PERSON点纯度候选。17个候选支撑176–7587点，P5–P95高度跨度约1.15–1.48m。这表明部分主体表面有足够点支撑粗几何，但不是完整人体身高、不是头/盆骨/手腕可见性证明，点数多也可能混簇。', '',
          '头部：最高点可能是手/背景，当前没有HEAD可见区域GT，UNKNOWN。躯干：中带重心可输出，但不是胸椎关节；骨盆：下中带仅表面代理，不能命名真实髋关节。四肢：缺左右身份/遮挡可见性/真实关节GT，全部UNKNOWN。不能以高度比例补齐17关节。本轮粗轴不做身份保证、置信概率或姿态/跌倒判断；缺点不输出伪关节。', '',
          '## 验收、冻结及下一步', '',
          f"最终Chrome {len(browser['checks'])} 条检查通过，包括九次真实会话切换和真实漏检截图；annotation binding 7项拒绝/边界检查通过；设备和物理未运行。软件作者自验不冒充独立复审。首轮浏览器检查在CASES生成前结束，其失败日志保留；第三轮新文件全通过。", '',
          f"全Git清单基线含untracked共{len(baseline['files'])}文件；HEAD {baseline['head']} / {baseline['branch']}。最终核对{checked}文件，除README授权新增外的原文件变化见FREEZE_FINAL.json。发现下列既有结果在工作期间被其他活动改写，本轮实现没有写它们，也没有还原或覆盖；S01整树冻结BLOCKED。", '']
for c in changed:
    lines.append('- ' + c['path'])
lines += ['', '下一步明确任务：', '',
          '1. 先实际查看成功/遮挡漏检/家具误检三例及九会话，标注工具重标S9关键帧，记录真实人编号/可见性/实际文件双SHA；可信评估仍须重新审阅，新草稿不自动放行。',
          '2. 在新离线工单将S6点损失拆为参考背景→清理→聚类→候选，固定同原始点对比低点数提案或点集保留策略；同时增加独立家具会话负样本，避免靠S1训练集成功宣称修复。',
          '3. 给头/躯干/骨盆及可见四肢画真实区域标签，核地面坐标来源与物理误差，再比较既有5–7区域原型与三表面轴的稳定性；没有可靠标定仍UNCALIBRATED，没有解剖GT仍UNKNOWN。',
          '4. 单独处理外部证据漂移并保存新轮记录；本轮不改回R9/Q01。用户未确认离线检测、骨架及姿态效果前，板端部署、生产替换、现场发布持续禁止。', '']
(out / 'REPORT.md').write_text('\n'.join(lines), encoding='utf-8')

accept_path = root / 'docs/human_capture/HUMAN_FUSION_DEMO_V2_ACCEPTANCE.md'
text = accept_path.read_text(encoding='utf-8')
for line in text.splitlines():
    if line.startswith('| ') and line.endswith('|'):
        ident = line.split('|')[1].strip()
        if ident in ['V01','V02','V03','V04','V05','T01','A01','E01','K01','K02']:
            text = text.replace(line, line.replace('NOT_RUN', 'PASS（作者自验；详REPORT）'))
        if ident == 'S01':
            text = text.replace(line, line.replace('NOT_RUN', 'BLOCKED（外部4个既有结果漂移；生产源与输入未见变化）'))
accept_path.write_text(text, encoding='utf-8')

manifest = {}
for p in sorted(lab.glob('*v2*')):
    if p.is_file():
        manifest[str(p.relative_to(root))] = hashlib.sha256(p.read_bytes()).hexdigest()
for p in sorted(out.iterdir()):
    if p.is_file():
        manifest[str(p.relative_to(root))] = hashlib.sha256(p.read_bytes()).hexdigest()
manifest[str(accept_path.relative_to(root))] = hashlib.sha256(accept_path.read_bytes()).hexdigest()
(out / 'DELIVERY_SHA256.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
return_path = root / 'docs/human_capture/returns/HUMAN-FUSION-DEMO-V2.md'
ret = f'''# HUMAN-FUSION-DEMO-V2 回传

## 2026-10-11 r1 / Codex唯一writer

- 状态SUBMITTED；逐条作者自验，未ACCEPTED。软件PASS条目V01–V05/T01/A01/E01/K01/K02；G01/P01 BLOCKED；S01 BLOCKED（外部既有结果漂移）；D01 NOT_RUN且明确禁止。
- 当前唯一表：[HUMAN_FUSION_DEMO_V2_ACCEPTANCE.md](../HUMAN_FUSION_DEMO_V2_ACCEPTANCE.md) v1；SHA {hashlib.sha256(accept_path.read_bytes()).hexdigest()}。
- 起始branch/HEAD：{baseline['branch']} / {baseline['head']}；9452文件含untracked基线BASELINE.json；所有用户原差异保留，不reset/checkout/clean/commit/push。
- ponytail SKILL.md实际读取路径：C:/Users/30680/.codex/skills/ponytail/SKILL.md。
- 单writer仅V2新文件与当前文档；复用V1而不改其源和模型。不dispatch agent，不部署、采集、生产切换或激活ML。

## 集中诊断与实际变更

| ID | 根因与修复 | 入口/状态覆盖 |
|---|---|---|
| T01 | FusionTracker没有同帧占用，导致21次共享ID及多票；V2 Runtime复用UniqueTracker | 每model/begin/segment回退重建与reset；18全帧运行0重复 |
| V03 | V1切模型会改变候选，不是同候选比较；V2从同raw完整候选重提51/69特征 | UI四分数/18运行的同候选列；实际classifier仍单当前管线 |
| V05/G01 | S9 placeholder SHA、缺meta绑定；Runtime拒绝不可信GT，新草稿带双SHA | 缺/错/稀疏GT UNKNOWN；可信S9仍BLOCKED |
| A01 | V1无本页标注；派生V2添加投影矩形与3D框、下载/导入/撤销 | raw28B行、同帧track唯一/索引界限/源点/坐标/SHA校验；草稿不改旧GT |
| K01/K02 | 既有骨架原型不等于已实现可靠人体关节 | 只显示有支撑三表面轴，完整关节/肢体/姿态UNKNOWN，UNCALIBRATED |

实际新文件：v2_runtime.js / server_v2.js / demo_v2.html / start_demo_v2.cmd / annotation_v2.js，以及派生、验证、收口工具。全部最终SHA见DELIVERY_SHA256.json；全帧运行采用的Runtime前诊断版本已从唯一后续差异还原保存FULL_REPLAY_RUNTIME_PRE_DIAGNOSTICS.js（只追加layer_observations，不改变检测跟踪）。新文档只在README顶部追加入口、独立验收表/回传/新证据目录。

## 逐条验收与证据

| ID | 实际验证 | 结果 |
|---|---|---|
| V01/V02 | BROWSER_CHECK_03.json九会话切换、三视图、帧条/暂停/重置及分层；真实截图 | PASS |
| V03 | validate_v2.js十八运行的same_candidate指标；浏览器四分数 | PASS |
| V04 | 35代表帧CASES/CASE_DETAILS；成功/漏检/家具截图及九会话截图 | PASS |
| V05 | 当前GT SHA与会话绑定；S9错误源显示UNKNOWN；未知不算负例 | PASS |
| T01 | 5210tick全帧、每帧一票/失配/寿命及回退reset确定性；collect追加诊断后重验 | PASS |
| G01 | 源及各备份都错绑定，无可靠来源；新绑定草稿工具已交付，历史GT不冒修复 | BLOCKED |
| A01 | 浏览器保存/撤销实际索引草稿；annotation_v2 --test绑定/边界/重叠校验 | PASS |
| E01 | 十八运行的跨会话表、UNKNOWN和训练/历史留出分列；独立家具/人员资格保持未知 | PASS（评估交付，非泛化合格） |
| K01 | 原limb/HR-SKELETON代码与真实资格审查，15项旧数学测试-W error | PASS（状态核查） |
| K02 | OBSERVABILITY实际候选点支撑及代理输出，缺解剖标签明确UNKNOWN/UNCALIBRATED | PASS（代理诊断，非关节精度） |
| S01 | FREEZE_CHECK与FREEZE_FINAL，4既有结果外部变化，不回写；无本轮生产修改 | BLOCKED |
| D01/P01 | 未部署/生产/采集；用户效果与物理确认不能由作者代替 | NOT_RUN / BLOCKED |

## 未闭合与复审入口

[完整实际报告](../evidence/2026-10-11_human_fusion_demo_v2_r1/REPORT.md)包含启动地址、真实例、模型对比、骨架分层与明确后续任务。第一批browser检查因CASES尚未生成失败，原日志保留；03轮通过。初次全帧检查在冻结断言失败，十八已完成结果保存并新collect归档，不改失败记录。不将自验冒称独立复审；若后续复审，以上现行表/源码SHA/完整日志为入口。

当前下一步为S9真实人工重标、独立家具验证及S6背景/清理/提案分层改善；解剖可见性/节点GT及可靠物理标定待补。保持用户未确认离线检测、骨架、姿态效果前禁止板端部署、生产替换、现场发布。
'''
with return_path.open('a', encoding='utf-8') as f:
    f.write(ret)
print('Report:', out / 'REPORT.md', 'Freeze changed:', len(changed), 'Browser checks:', len(browser['checks']))
