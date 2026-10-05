from pathlib import Path
root=Path(__file__).resolve().parents[4]; docs=root/'docs/human_fall'
review='''

## Codex GL04 R6 独立复审 / 2026-10-03

v1 **REWORK**，仅V07/V09 source来源消费者仍FAIL。独立90/92/95/97全部41/2/3/20 PASS、54lib exit0，原48完全保留SHA；R5原阻断全闭合。新98两条明确position_source_from=unavailable/predicted却显示当前XYZ/实测是真FAIL，五条过严要求隐藏灰诊断的探索assert由契约审查否决，保留失败历史并登记容忍限制，不扩大范围。完整逐V/C/M与SHA/命令/浏览器六图在[R6 CODEX_REVIEW](evidence/2026-10-03_gl04_r6/CODEX_REVIEW.md)。

V01/V02/V03/V05/V06/V08 PASS，V07/V09 FAIL，V04 NOT_RUN（DPR1/1.2实测但跨导航/布局，未隔离DPR-only，完整camera clip未做），V10 BLOCKED，D01 NOT_RUN。C08 FAIL、C12 NOT_RUN，其余C01–C15 PASS；M07 FAIL、M03/M11 NOT_RUN，其余M01–M11 PASS。pending是本地state输入，不做采集；localhost断连/静默/当前终态恢复及历史/选择ACK通过。

唯一OpenCode session ses_f01ba3f48ffepSrGKkcHrb3onk/default DB/Go Flash：probe8.828秒成功，03主动上下文暂停exit1、官方真压缩summary=true、05同session续接exit0/SUBMITTED停写。实际ponytail读取.claude路径，回传误称.config/skill已据CLI read纠正。正式/core/driver/旧证据不改，原48不降。R7先[设计矩阵](evidence/2026-10-03_gl04_r7/PLAN_REVIEW.md)/[唯一工单](AI_PROMPT_GL04_OPENCODE_R7.md)，只补source实测来源共享门，bbox-only负旗不清合法raw中心；原预测诊断不变。无GL05/部署/采集/板端网络/commit/push/reset。
'''
p=docs/'REVIEW_LOG.md'
if '## Codex GL04 R6 独立复审 /' not in p.read_text(encoding='utf-8'):p.write_text(p.read_text(encoding='utf-8')+review,encoding='utf-8')
p=docs/'returns/GL-04.md'
if '## Codex GL04 R6 审查附记' not in p.read_text(encoding='utf-8'):
    p.write_text(p.read_text(encoding='utf-8')+'''\n\n## Codex GL04 R6 审查附记 / 2026-10-03

独立REWORK：V01/V02/V03/V05/V06/V08 PASS，V07/V09 FAIL（显式source来源非actual却仍当前位置/实测），V04 NOT_RUN，V10 BLOCKED，D01 NOT_RUN。原95/97阻断闭合、41/2/3/20独立与54lib过；原48 SHA文字完全保留。新98探索中只有两source provenance FAIL入现行C08/V07，五灰诊断hide预期过严不当阻断，详evidence/2026-10-03_gl04_r6/CODEX_REVIEW.md及99_contract_adjudication.md。六图/当前source/ground/unknown/静默/断连/pending终态恢复均为本地synthetic/offline，不设备、不采集。R7只补source位置/实测消费者，原bbox-only negative下actual_points raw与灰诊断语义保留。

提交元数据纠正：实际03日志read的ponytail路径为C:/Users/30680/.claude/skills/ponytail/SKILL.md；并无skill工具调用，回传.config/skill表述误记。已实际先读，非未使用。index before列40位值为Git blob而非SHA256，after/现场仍原6e687d95...SHA256一致。原回传不覆写，后续准确声明。正式/core/driver/旧证据/用户改动未动，无部署/GL05/commit/push/reset。\n''',encoding='utf-8')
st={k:'PASS' for k in ['V01','V02','V03','V05','V06','V08','M01','M02','M04','M05','M06','M08','M09','M10']};st.update(V07='FAIL',V09='FAIL',V04='NOT_RUN',V10='BLOCKED',D01='NOT_RUN',M07='FAIL',M03='NOT_RUN',M11='NOT_RUN')
p=docs/'GL04_ACCEPTANCE.md'; s=p.read_text(encoding='utf-8'); lines=s.splitlines()
for i,line in enumerate(lines):
    for key,value in st.items():
        if line.startswith('| '+key+' |'):lines[i]=line.rsplit('|',2)[0]+'| '+value+' |';break
if '## R6独立结果 / 2026-10-03' not in s:
    p.write_text('\n'.join(lines)+'\n\n## R6独立结果 / 2026-10-03\n\nv1不变，仅结果列更新。V07/V09 source来源消费者REWORK，R5原阻断全闭合；真实六图/生命周期、逐V/C/M与限制见[R6复审](evidence/2026-10-03_gl04_r6/CODEX_REVIEW.md)。R7同工作项范围内继续，先[设计矩阵](evidence/2026-10-03_gl04_r7/PLAN_REVIEW.md)/[工单](AI_PROMPT_GL04_OPENCODE_R7.md)/≤1分钟probe；源provenance门与bbox观察门分开，灰预测诊断原义保留。正式未获审不并入，V04未完成浏览器项、V10/D01分层；无GL05/部署/采集。\n',encoding='utf-8')
p=docs/'DISPATCH.md';s=p.read_text(encoding='utf-8')
if not s.startswith('# 当前活动覆盖 / 2026-10-03 GL-04 R7'):
    s=s.replace('# 当前活动覆盖 / 2026-10-03 GL-04 R6恢复开发','# 历史活动覆盖 / 2026-10-03 GL-04 R6恢复开发',1)
    p.write_text('# 当前活动覆盖 / 2026-10-03 GL-04 R7准备\n\n唯一活动GL04，Codex独审/编排，唯一OpenCode Go Flash/default DB writer。R6已SUBMITTED/停写，独审仅V07/V09 source provenance REWORK，原阻断全部闭合；[R6复审](evidence/2026-10-03_gl04_r6/CODEX_REVIEW.md)、[v1](GL04_ACCEPTANCE.md)、[R7完整矩阵](evidence/2026-10-03_gl04_r7/PLAN_REVIEW.md)、[唯一R7工单](AI_PROMPT_GL04_OPENCODE_R7.md)。新派工先≤1分钟probe，原session长上下文先真压缩；没有第二writer。V04隔离DPR/完整clip仍NOT_RUN，V10 BLOCKED/D01 NOT_RUN；正式冻结，不GL05/部署/采集/板端网络，不改原54/旧证据/用户Q-E帮助。下方R6执行/服务阻塞均历史。\n\n'+s,encoding='utf-8')
p=docs/'WORKFLOW.md';s=p.read_text(encoding='utf-8')
if '2026-10-03 R6独审覆盖' not in s:s=s.replace('# 工单开发与验收流程 v2','# 工单开发与验收流程 v2\n\n2026-10-03 R6独审覆盖：同项R7继续范围内source provenance返工，R6已停写/REWORK仅V07/V09，原R5阻断全闭合；当前[DISPATCH](DISPATCH.md)/[R6复审](evidence/2026-10-03_gl04_r6/CODEX_REVIEW.md)。唯一Codex编排独审/OpenCode Go Flash default DB writer，新派工先≤1分钟probe、原长session真压缩。下方R6执行与首次服务BLOCKED为历史；正式/GL05/部署/采集/板端网络边界不变。',1);p.write_text(s,encoding='utf-8')
print('R6 per-ID closeout recorded; R7 design ready; v1 criteria preserved')
