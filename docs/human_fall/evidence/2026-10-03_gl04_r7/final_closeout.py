from pathlib import Path
root=Path(__file__).resolve().parents[4];d=root/'docs/human_fall'
summary='''

## Codex GL04 R7 独立复审 / 2026-10-03

当前**无代码FAIL，尚未软件收口**：V01/V02/V03/V05/V06/V07/V08/V09 PASS，V04实际DPR-only NOT_RUN，V10生产集成BLOCKED，D01设备NOT_RUN。R6两source provenance真FAIL已由独立98及真实生产preview入口31/32闭合，bbox-only negative仍保留合法raw（33）；原54完整SHA保留、55lib与41/2/3/20/10独立检查exit0。C12/M03 NOT_RUN，其余C01–C15/M01–M11 PASS；M11已用证据用相机UI+原生产JS在真实浏览器补齐两mode裁剪/退化，无伪命中/红屏。完整逐ID、SHA/命令/限制在[R7 CODEX_REVIEW](evidence/2026-10-03_gl04_r7/CODEX_REVIEW.md)。

指定Go Flash/default DB新probe9.172秒成功、原session真压缩后R7续接exit0/SUBMITTED/停写，实际skill工具ponytail已核。无活动writer、无新FAIL，不派R8。真实DPR-only不可控仍NOT_RUN，不用1/1.2跨页面观测或VM属性伪报。正式未获审不并入，GL05/部署/采集/板端网络未授权；用户Q/E/帮助/HR/重组、core/driver/旧证据/原54保留，不commit/push/reset。
'''
p=d/'REVIEW_LOG.md';s=p.read_text(encoding='utf-8')
if '## Codex GL04 R7 独立复审 /' not in s:p.write_text(s+summary,encoding='utf-8')
p=d/'returns/GL-04.md';s=p.read_text(encoding='utf-8')
if '## Codex GL04 R7 审查附记' not in s:p.write_text(s+summary.replace('## Codex GL04 R7 独立复审 /','## Codex GL04 R7 审查附记 /'),encoding='utf-8')
st={k:'PASS' for k in ['V01','V02','V03','V05','V06','V07','V08','V09']+['M%02d'%i for i in range(1,12)]};st.update(V04='NOT_RUN',V10='BLOCKED',D01='NOT_RUN',M03='NOT_RUN')
p=d/'GL04_ACCEPTANCE.md';s=p.read_text(encoding='utf-8');lines=s.splitlines()
for i,line in enumerate(lines):
    for key,value in st.items():
        if line.startswith('| '+key+' |'):lines[i]=line.rsplit('|',2)[0]+'| '+value+' |';break
if '## R7独立结果 /' not in s:p.write_text('\n'.join(lines)+'\n\n## R7独立结果 / 2026-10-03\n\nv1判据不变，仅结果列更新。代码无FAIL，V04/C12/M03实际DPR-only NOT_RUN，所以GL04尚未软件收口；V10/D01分层。真实clip/退化M11已补PASS，来源反例全部闭合。详[R7复审](evidence/2026-10-03_gl04_r7/CODEX_REVIEW.md)。无writer、不派R8、不并入正式/不GL05/部署/采集/板端网络；原54/用户改动/旧证据不动。\n',encoding='utf-8')
p=d/'DISPATCH.md';s=p.read_text(encoding='utf-8')
if not s.startswith('# 当前活动覆盖 / 2026-10-03 GL-04 R7待真实DPR'):
    s=s.replace('# 当前活动覆盖 / 2026-10-03 GL-04 R7准备','# 历史活动覆盖 / 2026-10-03 GL-04 R7准备',1)
    p.write_text('# 当前活动覆盖 / 2026-10-03 GL-04 R7待真实DPR浏览器收口\n\nR7 OpenCode Go Flash/default DB同session真压缩后exit0/SUBMITTED，Codex独立复审当前代码条目无FAIL。V01–03/V05–09 PASS，V04/C12/M03实际DPR-only NOT_RUN，V10结构BLOCKED/D01设备NOT_RUN；因此GL04尚未软件收口/ACCEPTED。唯一[验收v1](GL04_ACCEPTANCE.md)/[R7正式复审](evidence/2026-10-03_gl04_r7/CODEX_REVIEW.md)，R7工单仅历史追溯，无活动writer/无新FAIL，不派R8。真实两mode clip/退化M11已PASS，原54/源码SHA/浏览器来源修复已核。下一步只补真实DPR-only验证；正式仍冻结，不合并/不GL05/部署/采集/板端网络；外部Q/E/帮助/HR/重组和旧证据保留。下方R6/R7开发入口全部历史。\n\n'+s,encoding='utf-8')
p=d/'WORKFLOW.md';s=p.read_text(encoding='utf-8')
if '2026-10-03 R7独审当前覆盖' not in s:p.write_text(s.replace('# 工单开发与验收流程 v2','# 工单开发与验收流程 v2\n\n2026-10-03 R7独审当前覆盖：代码修复条目无FAIL，V04实际DPR-only NOT_RUN，GL04尚未软件收口；V10/D01分层。唯一Codex独审/编排，无活动OpenCode writer、无新FAIL、不派R8；[当前入口](DISPATCH.md)/[R7复审](evidence/2026-10-03_gl04_r7/CODEX_REVIEW.md)。仅待真实DPR浏览器验证，正式不并入、GL05/部署/采集/板端网络未授权。下方R6/R7开发/服务历史不作当前状态。',1),encoding='utf-8')
p=d/'tickets/GL-04_webui_level_view.md';s=p.read_text(encoding='utf-8');parts=s.splitlines()
parts[2]='执行：OpenCode Go Flash；独立审核/编排：Codex。当前R7代码条目无FAIL，V04真实DPR-only NOT_RUN，GL04尚未软件收口；V10 BLOCKED/D01 NOT_RUN。无活动writer、不派R8，详[当前入口](../DISPATCH.md)/[R7复审](../evidence/2026-10-03_gl04_r7/CODEX_REVIEW.md)。正式未获审不并入，不GL05/部署/采集。'
p.write_text('\n'.join(parts)+'\n',encoding='utf-8')
print('R7 per-ID status recorded; no software completion claimed; no deployment or formal merge')
