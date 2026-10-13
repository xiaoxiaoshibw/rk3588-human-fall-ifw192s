"""Register the next phase as planning only; preserve every old document prefix."""
import hashlib
import json
from pathlib import Path
import re
from datetime import datetime, timezone, timedelta
from record_plan import OUT, ROOT, APPEND, NEW, sha, save

def append(name, text):
    with (ROOT / name).open('ab') as f:
        f.write(text.encode('utf8'))

stamp = datetime.now(timezone(timedelta(hours=8))).isoformat()
append('docs/human_capture/README.md', '''

## 2026-10-08 下一阶段骨架离线计划登记（仅计划，未开工）

用户本聊天要求“制定下一个阶段计划”，已制定 [下一阶段离线粗骨架计划 v1](HUMAN_SKELETON_OFFLINE_PLAN.md)、[HR-SKELETON-OFFLINE 工单](tickets/HR-SKELETON-OFFLINE.md)及其唯一验收表 [HR_SKELETON_OFFLINE_ACCEPTANCE.md v1](HR_SKELETON_OFFLINE_ACCEPTANCE.md)。状态DRAFT_READY_FOR_DISPATCH，SKO-01～18全部NOT_RUN。本轮仅规划；后续用户明确开工后才做人工确认人体簇→可逆标准化→5–7粗结构节点→独立时序→离线复审。

最新SEM R2已修复SEM-12工具绑定，但SEM-05～08、10与WD02仍BLOCKED，[R2报告](evidence/2026-10-08_hrsemshadow_r2/REVIEW_R2.md)；真实身份GT缺失、05/08结构上界不足95%。本计划是受控离线可行性，不等于正式W04/W05放行，不改W03/SEM/RET-V2历史状态，不重开已关闭HR-07/08、不激活HR-09/ML，不部署采集或修改生产。
''')
append('docs/human_capture/tickets/INDEX.md', '''

## 2026-10-08 下一阶段骨架离线工单（仅制定）

| ID | 主题 | 状态 | 唯一验收表 |
|---|---|---|---|
| [HR-SKELETON-OFFLINE](HR-SKELETON-OFFLINE.md) | 人工确认人体簇上的标准化、5–7粗结构节点与独立时序可行性 | DRAFT_READY_FOR_DISPATCH；未开工 | [HR_SKELETON_OFFLINE_ACCEPTANCE.md v1](../HR_SKELETON_OFFLINE_ACCEPTANCE.md) |

正式W04/W05和旧HR-07是不同范围；不改变旧关闭决定、W03/SEM BLOCKED或生产边界。实施以新的明确用户开工授权为准。
''')
append('docs/human_capture/HUMAN_RECOGNITION_NEXT_STAGE_PLAN.md', '''

## 2026-10-08 R2之后的离线骨架规划更新（仅计划）

用户本聊天在询问骨架时点后要求制定下一阶段计划。最新 [SEM-SHADOW-R2](evidence/2026-10-08_hrsemshadow_r2/REVIEW_R2.md)：SEM-12 PASS，其余人体GT/旧负例项与WD02仍BLOCKED，离线交付未ACCEPTED；W03正式冻结与W04/W05主线门保持。

新增 [HUMAN_SKELETON_OFFLINE_PLAN.md v1](HUMAN_SKELETON_OFFLINE_PLAN.md) / [HR-SKELETON-OFFLINE](tickets/HR-SKELETON-OFFLINE.md)，唯一验收表 [HR_SKELETON_OFFLINE_ACCEPTANCE.md v1](HR_SKELETON_OFFLINE_ACCEPTANCE.md)。先A固定来源/100原始帧窗口，B最小真实人工身份/节点可见性，C可逆标准化，D粗结构节点，E独立时序，F验证/复审。人工确认输入是实验夹具，不替代正式自动选人；WD02不进入本实验且继续阻断；head/hand歧义与无点UNKNOWN必测。

状态DRAFT_READY_FOR_DISPATCH，未实施。只规划受控离线可行性，不跳过原主线放行、不重开旧limb/ML；正式接入仍须原前置验收和单独授权。先最小GT再真实节点试验，GT缺失只完成独立工具部分、相应真实指标BLOCKED。
''')
table = ROOT / 'docs/human_capture/HR_SKELETON_OFFLINE_ACCEPTANCE.md'
ticket = ROOT / 'docs/human_capture/tickets/HR-SKELETON-OFFLINE.md'
plan = ROOT / 'docs/human_capture/HUMAN_SKELETON_OFFLINE_PLAN.md'
ids = re.findall(r'^\| (SKO-\d{2}) \|', table.read_text('utf8'), re.M)
assert ids == [f'SKO-{n:02d}' for n in range(1, 19)]
rows = [l for l in table.read_text('utf8').splitlines() if re.match(r'^\| SKO-\d{2} \|', l)]
assert all(l.endswith('| NOT_RUN |') for l in rows)
links = []
for file in [plan, ticket, table] + [ROOT / n for n in APPEND]:
    for target in re.findall(r'\]\(([^)]+)\)', file.read_text('utf8')):
        if '://' in target or target.startswith('#'):
            continue
        target = target.split('#')[0]
        resolved = file.parent / target
        # Existing historical links can be stale; this plan must not silently fix them.
        if file in [plan, ticket, table] or any(key in target for key in ['SKELETON', 'skeleton']):
            assert resolved.is_file(), (file, target)
            links.append({'from': file.relative_to(ROOT).as_posix(), 'target': target})
save('01_document_checks.json', {'version': 1, 'acceptance_ids': ids, 'all_initial_NOT_RUN': True,
    'verified_links': links, 'plan_sha256': sha(plan), 'ticket_sha256': sha(ticket), 'acceptance_sha256': sha(table),
    'implementation_tests_run': False, 'scope': 'document structure, links and authorization boundary only'})
b = json.loads((OUT / '00_baseline.json').read_text('utf8'))
content = f'''# HR-SKELETON-OFFLINE 回传记录

## {stamp} 计划制定轮（Codex）

### 本轮信息

- 工单HR-SKELETON-OFFLINE / plan r1 / 本聊天Codex单writer，用户只请求“制定下一个阶段计划”。无算法实施、人工标签生成、采集或部署；无子代理/OpenCode/模型切换。
- 状态DRAFT_READY_FOR_DISPATCH / PLAN_RECORDED，未开工，未ACCEPTED。唯一表HR_SKELETON_OFFLINE_ACCEPTANCE.md v1，SHA `{sha(table)}`；工单SHA `{sha(ticket)}`。
- 起始 {b['branch']} / {b['head']}；全tracked/untracked及ignored captures/HC evidence/console dist的6263路径、43,359,798,841字节基线，见evidence/2026-10-08_hrskeleton_plan_r1/00_baseline.json及dirty记录。
- ponytail实读 `C:/Users/30680/.codex/skills/ponytail/SKILL.md`，full；本轮只进行代码范围设计和文档制作，不改算法。

### 诊断与范围设计

| 已知问题 | 本计划处理 | 保留边界 |
|---|---|---|
| 当前GT不足、HEAD0/195、05/08结构上界低 | 先绑定/人工身份与节点可见性，固定开发/验证窗口；无点UNKNOWN | 不把工具修复当人体性能通过，不修改SEM原表 |
| HR-07旧纯几何错误锁家具 | 新任务仅已确认完整人体簇，身份不是密度/PCA/pin推断 | 不重开关闭支线，不声称自动识别人 |
| W03未冻结、WD02争议 | 独立离线可行性；不消费WD02，正式W04/W05门保留 | 不绕过检查、生产旗标或原验收 |

### 实际文档变更

新增HUMAN_SKELETON_OFFLINE_PLAN.md、tickets/HR-SKELETON-OFFLINE.md、唯一验收表、本return及本计划evidence；README/INDEX/HUMAN_RECOGNITION_NEXT_STAGE_PLAN只末尾追加登记，原前缀最终检查。新文件SHA见01_document_checks.json/manifest.json。

### 逐条验收状态

SKO-01～18 **全部NOT_RUN**：本轮制定工单，不执行骨架验收。文档检查独立记录为01_document_checks.json，不冒充任何算法条目PASS。设备/物理/生产/采集/部署/模型/正式W04/W05全部NOT_RUN/未授权。

### 计划出口与停止点

A固定数据→B真实最小GT→C可逆标准化→D有支撑粗节点→E独立时序→F固定验证与独立复审。100唯一帧/120分支行预登记，开发/验证按会话分开；先两个开发会话各3连续PERSON帧的可信GT才做真实节点，未标部分BLOCKED；这个工作量条件不是人体/骨架精度门。

当前停止在计划可转发。本轮不启动算法或要求用户现在标注；未来开工由用户另行明确授权，GT缺失时独立可做部分继续、真人效果项BLOCKED。完整四肢、精确关节、多姿态/跌倒和生产接入不在本单范围；无commit/push或旧资产重写。
'''
return_path = ROOT / 'docs/human_capture/returns/HR-SKELETON-OFFLINE.md'
with return_path.open('x', encoding='utf8') as f:
    f.write(content)
print('PLAN_REGISTERED', len(ids), 'unique NOT_RUN IDs;', len(links), 'links verified; algorithms not run')
