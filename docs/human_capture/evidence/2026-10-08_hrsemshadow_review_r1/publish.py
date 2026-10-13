"""Publish review records only, with append-only return prefix guard."""
import hashlib
import json
from audit import ROOT, OUT, RET, save

states = ['PASS', 'PASS', 'PASS', 'PASS', 'BLOCKED', 'BLOCKED', 'BLOCKED', 'BLOCKED',
          'PASS', 'BLOCKED', 'PASS', 'FAIL', 'PASS', 'PASS', 'PASS', 'PASS']
rows = [{'id': 'SEM-%02d' % (i + 1), 'status': s, 'evidence': 'REVIEW.md'} for i, s in enumerate(states)]
save('acceptance_review.json', {'ticket': 'HR-SEM-SHADOW', 'acceptance_version': 'v1',
    'acceptance_sha256': '3b5b83da5a83c460bc7590011034647f77272be70d1f92f7c2ddb9c0bd8498dd',
    'independent_review': True, 'delivery_decision': 'REWORK_REQUIRED; offline delivery not accepted',
    'production_eligible': False, 'rows': rows,
    'changed_from_selfcheck': [{'id': 'SEM-12', 'from': 'PASS', 'to': 'FAIL', 'reason': 'unbound external cluster index can misrepresent reviewed member set'}],
    'WD02': 'inputs and artifacts intact; extra harness generator-code equality diagnosed; no WD02 execution or release',
    'browser_UI': 'BLOCKED; prior tool restriction retained; no policy bypass'})
lines = ['# 实际审核命令及退出码', '',
    'Python 前缀统一 `python -B -W error -X utf8`；`audit.py <name> <argv...>` 将实际子进程 stdout/stderr 和 exit 存入同名三件文件。', '',
    '| 记录 | 实际子命令 | exit |', '|---|---|---|']
for p in sorted(OUT.glob('*.run.json')):
    r = json.loads(p.read_text('utf8'))
    args = r.get('argv', r.get('command', []))
    lines.append('| %s | `%s` | %s |' % (p.stem, ' '.join(args), r['exit_code']))
lines += ['', '基线实际命令：`python -B -W error -X utf8 docs/human_capture/evidence/2026-10-08_hrsemshadow_review_r1/audit.py baseline`，exit0；6056实际文件43,280,721,488字节。',
    '', '初期只读探索命令包括 Get-Content（用户指定八组文件、相关源码/日志）、rg（源调用者/路径/记忆关键词）、git branch/rev-parse/status/diff、python版本与node --version。这些PowerShell读取调用exit0；第一次profile输出oh-my-posh/PSReadLine环境警告，随后用login=false。一次Windows rg通配目录参数报os error123，改用已核实路径；一次临时Python读取表达式产生unclosed-file ResourceWarning，未采用为审核证明，后续全部文件读取使用上下文管理器。',
    '', 'data初次扫描由审核者中止（精准核对自己的python子进程38480后Stop-Process），exit4294967295；理由是审核工具重复构建集合造成不必要耗时。仅优化本轮审核脚本，data2 exit0。',
    '', 'negatives初次exit1位于最后12样本的跨VM对象deepStrictEqual（结构/数值一致但原型不同）；初版保存为negative_audit_initial.js。改为规范化值哈希比较，不改算法/参数，negatives2 exit0；两次完整日志保留。',
    '', 'registration_check.js将临时夹具限定到本证据test_tmp；真实run23ID，T37-20不在自动suite。replay既有suite创建的两个os.tmpdir/hr03-*剪辑夹具由该suite自行移除，未保留或改变输入/生产文件。',
    '', '最终发布/完整性命令也有独立run记录。最终发布只写本目录与append-only return；结束的完整性覆盖全部旧文件和旧return前缀。']
(OUT / 'commands.md').write_text('\n'.join(lines) + '\n', encoding='utf8')
b = json.loads((OUT / 'baseline.json').read_text('utf8'))
ret = ROOT / RET
old = ret.read_bytes()
assert len(old) == b['return_prefix_bytes'] and hashlib.sha256(old).hexdigest() == b['return_prefix_sha256'], 'return changed since review baseline'
table = '\n'.join('| %s | %s | [独立依据与定位](../evidence/2026-10-08_hrsemshadow_review_r1/REVIEW.md) |' % (r['id'], r['status']) for r in rows)
text = '''

## 2026-10-08 HR-SEM-SHADOW 独立复审 r1（Codex，PC离线）

### 本轮信息

- 用户直接授权独立PC离线复审；单审核者，无子代理/OpenCode/实施CLI；实际模型标识未核实不填。
- 唯一表 `docs/human_capture/HR_SEM_SHADOW_ACCEPTANCE.md` v1，SHA `3b5b83da5a83c460bc7590011034647f77272be70d1f92f7c2ddb9c0bd8498dd`；工单SHA `f9e9e4f705c2ed571d495f7164341bead7e768106eb48458ce40f474f4e819d6`。
- **独立结论 REWORK_REQUIRED：本单离线证据与设计交付暂不接受，生产接入不具备资格。** SEM-12从执行者PASS明确改判FAIL；其余逐项见下表。原执行记录保留，不重写历史。
- 起始 master / `cfbb80c57508be1a0435fdb92260f698dc763934`；完整本轮基线6056实际文件43,280,721,488字节，dirty及用户原差异保留。r1起始5908记录、143产物、12工具源码及实际digest重新核对，零漂移。
- ponytail实际实读路径：`C:/Users/30680/.codex/skills/ponytail/SKILL.md`（full）。stdlib、已安装NumPy和只读纯函数；无新依赖，无生产修复。
- 审核报告：[REVIEW.md](../evidence/2026-10-08_hrsemshadow_review_r1/REVIEW.md)；全部工具/日志/结果只在 `evidence/2026-10-08_hrsemshadow_review_r1/`；实际命令/exit：[commands.md](../evidence/2026-10-08_hrsemshadow_review_r1/commands.md)。

### 集中诊断与根因覆盖

| 类别/ID | 根因与实际影响 | 最小返工要求与边界 |
|---|---|---|
| 实现错误 / SEM-12 | 全帧查看入口不绑定所选clusters.jsonl及行成员。1029点真实簇换成row0，仍复制原member SHA并显示源SHA通过；原GT格式validator接受该合成内存记录。 | 新轮绑定index digest、重算成员SHA、校frame/seq/rows并阻断篡改，补正常载入/拒绝检查。本轮只复现，不修代码，不造真人GT。 |
| 工具契约 / SEM-10 | WD02源与全部派生产物SHA完整；只有历史leveling.py与当前生成代码不同。shadow.level额外要求二者相等，现有levelingBinding契约没有该条件。 | 更正“输入漂移”归因，区分生成provenance与当前消费者绑定，后续澄清协议。WD02本轮仍未运行，不换job、不重签、不放行。 |
| 目标不足 / SEM-05、08 | 完整簇HUMAN帧上界13/244、1/195；ROI抽样成功不能外推整簇。 | 保留数值目标不足与GT阻断两层事实；后续独立校准/版本设计，不调当前阈值或95%分母。 |
| GT/覆盖 / SEM-05～08、10 | 真人全帧簇/连续person_id、185+5边缘点、WD01区域HUMAN身份未闭合；箱子UNKNOWN、low_bar全空、格栅未覆盖、WD02未跑。 | 人工可追溯标签与实际非空覆盖；机器ID/ROI不作GT，空输入不计负例通过。 |
| 既有风险 / SEM-04、11 | 无效点污染原图/拓扑；原Tracker同帧复用及观测票不老化。 | 保留审计对照；I01/T01/T02需另授权，本轮不改生产Tracker/Fall。 |
| 工具限制 / SEM-12 | r1实际浏览器UI环回超时/file策略阻断，headless不能替代。 | 保留BLOCKED，不能绕过浏览器安全策略；与索引绑定实现错误分开。 |

### 实际变更与独立验收

仅新增本复审目录和本return末尾段；详细文件SHA/用途见本轮 `changes.json`。旧生产源码、冻结参数、captures、旧evidence和原return前缀完整性见本轮 `integrity.json`。没有commit/push/reset/checkout/clean、签装artifact、生产旗标、板端连接、部署采集、ML或后续工单。

| ID | 独立状态 | 依据 |
|---|---|---|
''' + table + '''

### 验证、限制与停止

- 原始输入全重算：1276原始帧/1561分支帧/4311簇，9366阶段序列、1561参照票及原Tracker快照、12,019,508成员坐标与r1一致。无效源row独立核对11,744,951；52228边缘线索全部按原row重建，185+5对账。
- 旧可用负例448分支帧/2210簇/458区域输出、24ROI与12空场冻结抽样重新核对。空场两口径0 HUMAN成立，UNKNOWN/小簇/无簇及上游删除分母保留；四段HUMAN帧13/244、269/271、281/281、1/195是结构代理，不是GT准确率。
- 原碰撞43帧=114254的8+空场WS的35，114205过期确认88帧；每机器身份每实际帧≤1票、五个实际帧含缺失、3票+min_age通过；关联歧义UNKNOWN，真人身份BLOCKED。
- 实际回归PL38、replay45、registration23ID exit0；两对数据实际digest核对，r1旧失败保留。本审核初次data中断exit4294967295、negative跨VM断言exit1保留，仅审核工具修正后data2/negatives2 exit0；不修改生产或算法值。全部实际命令、源码SHA、退出码及日志可复审。
- 设计默认关/回退/三值票源/生命周期/源码触点/GT和独立复审依赖明确；目前不建议生产切换。设备/物理/板端/部署/采集/网络驱动/ML/生产接入/下一工单均NOT_RUN，实际浏览器UI仍BLOCKED。
- 本轮审核完成后停止；不自动修复、不启动实施CLI、不进入下一工单。后续若返工，应新增证据轮并保留r1与本复审记录。
'''
(OUT / 'return_append.md').write_text(text, encoding='utf8')
with ret.open('ab') as f:
    f.write(text.encode('utf8'))
assert ret.read_bytes()[:len(old)] == old
print('REVIEW_PUBLISHED', len(rows), 'SEM rows; return appended; prefix preserved')
