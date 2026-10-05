"""User-authorized status closure; production code and old evidence read-only."""
from datetime import datetime, timezone, timedelta
from pathlib import Path
ROOT=Path(__file__).resolve().parents[5]
DOC=ROOT/'docs/human_fall'
stamp=datetime.now(timezone(timedelta(hours=8))).strftime('%Y-%m-%d %H:%M:%S +08:00')
report='evidence/2026-10-02_gl03_r7/codex_review_01/CODEX_REVIEW.md'
status=(f'当前按[WORKFLOW.md](WORKFLOW.md) v2及用户本轮交接授权，唯一生效编排/独立复审/状态收口者为 Codex。'
        f'范围内自动派 OpenCode CLI `opencode-go/deepseek-v4.1-flash` 已恢复，生产代码单写入者仍 OpenCode。'
        f'GL02软件PASS不变；GL03 R7 G01/G02/G03/G04/G05/G07/G08 软件PASS，G06真实分离BLOCKED，O01统计PASS/真实身份BLOCKED，D01设备NOT_RUN/现场BLOCKED。'
        f'当前无活动实现写入者、无新FAIL、无需R8；整单未标ACCEPTED，GL04须另获用户授权。'
        f'[R7独立复审]({report})、[验收v1](GL03_ACCEPTANCE.md)。')
table='''| ID | 独立结果 | 层级/边界 |
|---|---|---|
| G01 | PASS | reference 全点几何/中心原义 |
| G02 | PASS | ground 实际点/源索引 |
| G03 | PASS | R6旧矩阵及125格结构资格独立检查通过，类型/损坏/回退闭合 |
| G04 | PASS | R5/R6已过结果沿用；node_runtime 889ead5e 未变 |
| G05 | PASS | 固定standalone/prospective原子reload保留，不重做旧专项 |
| G06 | BLOCKED | disabled保留行为PASS；可信分离synthetic路径未启用NOT_RUN，真实桥接/分离BLOCKED |
| G07 | PASS | 合法legacy/None/unknown兼容、semantic及物理flags诚实性 |
| G08 | PASS | 相关回归/范围/SHA/静态语法；目标设备运行NOT_RUN |
| O01 | PASS | 仅ROI/pool探索统计；真实单帧根因/人体机器人身份BLOCKED |
| D01 | NOT_RUN | 设备运行未做；完整帧/现场身份物理BLOCKED |
'''
summary=(f'判据v1不变。详细逐格映射、命令/exit、SHA及来源见[R7独立复审]({report})。'
         'R6 14d 的7方法不足以代表全部类型格，本轮独立补125格全部PASS，原矩阵exit0；相关fall 326回归exit0（含GL03 54），不以测试总数验收。'
         '提交manifest全匹配，独立逆patch重建三处改动文件与R6 SHA一致，node_runtime 889ead5e保持；O01 R7/R3逐字节一致。'
         '首尾源码/旧证据未变；HEAD 8a5a2b2及CLI_RECOVERY外部变化保留单列，不归因不回滚。')

def read(name):return (DOC/name).read_text(encoding='utf-8')
def write(name,text):
    with (DOC/name).open('w',encoding='utf-8',newline='') as f:f.write(text)
def replace_paragraph(text,prefix,replacement):
    start=text.index(prefix);end=text.find('\n\n',start)
    if end<0:end=len(text)
    return text[:start]+replacement+text[end:]

accept=read('GL03_ACCEPTANCE.md')
accept=replace_paragraph(accept,'前置GL01/GL02软件PASS。',
    '前置GL01/GL02软件PASS。用户本轮授权Codex接回唯一编排/独立复审/状态收口角色，恢复指定OpenCode CLI范围内自动派工。'
    f'R7独立复审已闭合G03，G01/G02/G03/G04/G05/G07/G08软件PASS；G06及真实身份BLOCKED，O01统计PASS，D01设备NOT_RUN。'
    f'[R7复审]({report})。整单未标ACCEPTED；GL04/部署/采集/网络及模型变更仍未授权。旧403为隔离DB项目绑定问题，default DB已于17:49恢复（见CLI_RECOVERY）。')
accept=accept.replace('## 当前独立结果 / R6 /','## 历史独立结果 / R6 /')
write('GL03_ACCEPTANCE.md',accept+'\n\n## 当前独立结果 / R7 / 2026-10-02\n\n'+summary+'\n\n'+table+
      '\n已验证软件范围PASS，无新FAIL、不派R8。G06/O01真实身份/D01现场分层保留，整单未ACCEPTED，GL04等待用户授权。\n')

returns=read('returns/GL-03.md')
write('returns/GL-03.md',returns+'\n\n---\n\n# Codex GL03 R7 独立复审 / 2026-10-02\n\n'+
      'Codex按用户本轮交接接回唯一编排/独立复审/状态收口角色，Claude Code 17:54顶替记录为历史；生产代码写入者仍OpenCode，R7提交后停止写入。\n\n'+
      summary.replace(']('+report+')','](../'+report+')')+'\n\n'+table+'\n'+
      'G03结构资格已PASS，已验证软件范围PASS；无新FAIL，不启动R8。G06/O01真实身份/D01现场不足不因软件闭合而消失，整单不标ACCEPTED。'
      '范围内CLI自动派工模式恢复；GL04须下一单用户授权。未写生产源码/生产测试、未部署/采集/联网/换模型/commit/push/reset/clean。\n')

workflow=read('WORKFLOW.md')
workflow=replace_paragraph(workflow,'2026-10-02最新派工覆盖：',
    '2026-10-02最新派工覆盖（用户本轮明确授权）：Codex接回唯一生效编排/独立复审/状态收口角色，Claude Code 17:54顶替已交接。'
    '恢复Codex直接调用OpenCode CLI `opencode-go/deepseek-v4.1-flash`自动派发范围内返工并独立复审，生产代码单写入者仍OpenCode。'
    'R3起用户手动转发临时安排作废；default DB 17:49已恢复（见CLI_RECOVERY），每次新派工仍先做≤1分钟probe，不用OPENCODE_DB隔离库。')
workflow=replace_paragraph(workflow,'2026-10-02当前R6独立结果：',
    f'2026-10-02当前R7独立结果：G03结构资格闭合，G01/G02/G03/G04/G05/G07/G08软件PASS，G06/真实身份BLOCKED，O01统计PASS，D01设备NOT_RUN。'
    f'[R7复审]({report})及[验收v1](GL03_ACCEPTANCE.md)。无活动实现写入者、无新FAIL、不派R8；整单未ACCEPTED，GL04/部署/采集/网络/模型切换未授权。')
workflow=replace_paragraph(workflow,'历史派工方式（2026-10-01授权背景，',
    '历史派工/403及手动转发记录保留供追溯，均受上方当前自动派工授权和结果覆盖。R3隔离DB 403现归为项目绑定问题，不能继续称订阅故障；'
    '历史长会话故障和算法返工分流不变。GL02软件PASS与设备/物理分层结论保持。')
write('WORKFLOW.md',workflow)

for name in ('DISPATCH.md','README.md'):
    text=read(name)
    text=replace_paragraph(text,'当前按[WORKFLOW.md]',status)
    text=replace_paragraph(text,'2026-10-02顶替入口：',
        '2026-10-02本轮交接：Claude Code 17:54按CLAUDE_STANDBY顶替后现交回Codex；此后唯一生效编排者是Codex，登记见CLI_RECOVERY。'
        '\n\n以下旧R4/R3及手动派工状态均为历史，由顶部R7结果/自动派工授权覆盖。')
    write(name,text)

ticket=read('tickets/GL-03_candidates_geometry.md')
ticket=replace_paragraph(ticket,'执行：用户手动派指定OpenCode；',
    '执行：Codex自动派指定OpenCode CLI `opencode-go/deepseek-v4.1-flash`；审核/编排：唯一生效Codex。'
    'R7 G01/G02/G03/G04/G05/G07/G08软件PASS，G06及真实身份BLOCKED，O01统计PASS，D01设备NOT_RUN/现场BLOCKED。'
    '[验收v1](../GL03_ACCEPTANCE.md)、[R7独立复审](../'+report+')。无新FAIL，无活动写入者；整单未ACCEPTED，GL04等待用户授权，不部署采集。')
ticket=ticket.replace('Codex独立检查几何框与聚类证据后放行GL-04。',
    'Codex独立检查几何框与聚类证据后收口本单；GL-04另需用户授权，不因本单软件PASS自动放行。')
write('tickets/GL-03_candidates_geometry.md',ticket)

review=read('REVIEW_LOG.md')
start=review.index('最新状态：');end=review.index('\n\n',start)
old=review[start:end]
review=review[:start]+'最新状态（2026-10-02）：GL02软件PASS；GL03 R7软件范围PASS，G06/真实身份BLOCKED、O01统计PASS、D01设备NOT_RUN；Codex接回唯一编排，范围内CLI自动派工恢复，整单未ACCEPTED、GL04未授权。\n\n历史2026-09-30状态：'+old[len('最新状态：'):]+review[end:]
write('REVIEW_LOG.md',review+'\n\n## Codex GL03 R7 独立复审 / 2026-10-02\n\n'+summary+'\n\n'+table+'\n'+
      '编排交接及自动派工恢复见CLI_RECOVERY；无新FAIL、不派R8、无活动实现写入者。GL02收口及G04/G05原专项不重做。'
      '设备/身份限制继续分层，不宣布整单ACCEPTED或自动放行GL04。\n')

cli=read('CLI_RECOVERY.md')
cli=cli.replace('用户手动派发不代表服务已恢复，本单当前手动安排仍优先。',
    '本轮已由default DB成功probe及用户明确指令恢复自动派工；每次派工仍实查指定模型，隔离DB故障不外推为订阅故障。')
cli=cli.replace('## SQL store不兼容与服务权限 / 2026-10-02补记',
    '## 历史 SQL store不兼容与403 / 2026-10-02补记（结论以下方恢复事实为准）')
cli=cli.replace('在单个进程环境选私有task DB（不放源码树），保留原data/auth路径，既不改全局配置也不复制/打印凭据。',
    '历史尝试曾在单个进程环境选私有task DB；本轮已确认此隔离变量触发Go项目绑定403，恢复派工使用default DB与仓库cwd，不再沿用隔离库，不改全局配置或认证。')
marker='### 2026-10-02 复查：Console 连通 ≠ Go 推理恢复（已被后续否决）'
start=cli.index(marker)
cli=cli[:start]+'''### 2026-10-02 最新事实：default DB Go 推理恢复，自动派工恢复

- 原始服务证据：[06_defaultdb_probe.jsonl](evidence/2026-10-02_service_probe/06_defaultdb_probe.jsonl)。17:49 在 default DB + cwd=D:/Code/ldiar，指定 `opencode-go/deepseek-v4.1-flash` 返回 PROBE_OK，step_finish reason=stop，input 8294/output 4，cost 0.001251492。核对的是Go推理成功，不只Console连通。
- 用户已核实：R3及后续隔离DB（OPENCODE_DB）403为上下文/project绑定问题，不是订阅故障。01–05失败原始日志及R3 CODEX_BLOCKED保留为历史，不覆写；不能继续用其阻断整个default DB通道。HTTP400长上下文故障另行分流，不计算法失败。
- 自动派工已按用户本轮明确授权恢复：Codex直接调用CLI派范围内返工并独立复审，不经用户搬运；生产代码单写入者仍OpenCode。R3起手动转发为临时历史安排，现已作废。
- 后续派工使用default DB与仓库cwd，不设置OPENCODE_DB隔离库，不更改auth/全局配置/模型。每次派工仍执行≤1分钟无工具probe并记录真实exit/输出/session/实际模型；失败只记录该条件下服务BLOCKED，先区分隔离变量，不盲目重试或更换模型。
- GL03 R7独立复审未发现新FAIL，故本轮未启动CLI推理/新probe/生产写入者；不把17:49证据写成当前时刻的新服务实测。GL04仍需用户授权。

### 编排交接登记 / 2026-10-02

'''+f'- {stamp}：按用户本轮交接说明，Claude Code于17:54按CLAUDE_STANDBY顶替后交回Codex；此刻登记Codex接回唯一生效编排/独立复审/状态收口角色，Claude Code不再并行编排。HEAD `8a5a2b28f922794bc25277319fd8dc85681802f1`；活动工单GL-03/R7独立复审已软件闭合，真实身份/设备分层保留；恢复锚点[R7复审]({report})。无活动实现写入者，生产源码只由指定OpenCode写入。\n'
write('CLI_RECOVERY.md',cli)
print('Closed R7 status and handover at',stamp)
