"""Actual post-audit closure, strict append-only original CLUSTER-01 return."""
import sys
from prepare import E,R,C,RETURN,load,save,sha,inventory,git

audit=load(E/'opencode_completion_03.json');model=load(E/'opencode_actual_model_03.json')
assert audit['exit_code']==0 and audit['marker']
assert model['models']==['opencode-go/deepseek-v4.1-flash'] and model['last_finish']=='stop' and model['export_exit_code']==0
assert '未解决逻辑FAIL：无' in (E/'04_codex_cross_review.md').read_text(encoding='utf8')
baseline=load(E/'00_baseline.json')
guards=dict(baseline['guards'])
for binding in load(E/'04_cohort_integrity.json')['bindings']:
    assert sha(binding['copy'])==binding['sha256']
    guards[binding['origin']]=binding['sha256']
changed={p:dict(before=d,after=sha(p)) for p,d in guards.items() if sha(p)!=d}
assert not changed,changed
assert RETURN.resolve()==RETURN and not RETURN.is_symlink()
before=RETURN.read_bytes()
assert before==(E/'return_before.bin').read_bytes() and sha(RETURN)==baseline['return_before_sha256'],'Return changed concurrently; stop append'
assert load(E/'03_regression_command.json')['exit_code']==0
assert load(E/'03_regression_command.json')['code_unchanged']
assert sha(E/'candidate/floor_sheet.py')==sha(C/'candidate/floor_sheet.py')
for folder in ['candidate','frozen','baseline']:
    for p in (E/folder).rglob('*.py'):assert sha(p)==sha(C/p.relative_to(E)),str(p)

statuses={key:'PASS' for key in ['T100','T101','T102','T103','T104','T105','T106','T108','T109','T110','T111']}
statuses.update(T107='BLOCKED',TLS01='BLOCKED',E01='BLOCKED',D01='NOT_RUN')
notes={
 'T100':'四阶段实际证据/patch/tests/return读取，manifest85/97/164/126；main全文件库存，578资产SHA，执行09C与生产分离',
 'T101':'11段原bin重建七数组精确相同；目标218帧四ROI分布/梯度；72/ROI2独立标量P95/RMS及拒绝复现',
 'T102':'固定ROI/所有点，展布和FIT份额；联合几何不退化，未换困难ROI',
 'T103':'配套刚体变换距离保持；仅数学控制，不称真实外参已校准',
 'T104':'FIT-only局部平面预测留出；定位数值失配贡献，物理根因/模型适用资格UNKNOWN',
 'T105':'正权重所有行保留：ROI等权失败转移72→144，帧等权不改善；ring/XY混杂不校准、不删尾点',
 'T106':'原TLS/独立SVD和标量排序/RMS复算、原全部门重现，50mm P95未变',
 'T107':'物理因果缺独立表面GT/bag，无可资格的单刚体修复；未编码候选，不伪造diff',
 'T108':'全部10个原TLS-valid会话、固定留出与11段诊断策略复现；无修复后泛化，非盲测/独立物理GT',
 'T109':'46项-W error及09C同源码配对100格精确输出/真实耗时；O(n4)/O(n2)保持，板端NOT_RUN',
 'T110':'实际指定CLI独审，模型/export/权限/raw/exit齐备；未解决逻辑FAIL无，执行UNKNOWN保留',
 'T111':'旧资产起止不变，原CLUSTER-01 return严格只追加，最终manifest逐SHA',
 'TLS01':'原121647有效TLS仍BLOCKED，P95超限保持，不自动解锁',
 'E01':'生产/隔离链路集成/发布/部署未授权',
 'D01':'无设备/物理干预/采集/B2/B3'}
order=['T100','T101','T102','T103','T104','T105','T106','T107','T108','T109','T110','T111','TLS01','E01','D01']
table='| ID | 结果 | 证据与限制 |\n|---|---|---|\n'+''.join(f'| {k} | {statuses[k]} | {notes[k]} |\n' for k in order)
save('verdict.json',dict(result='BLOCKED',submission='SUBMITTED / STOPPED',statuses=statuses,notes=notes,
    acceptance_version='v1',acceptance_sha256=sha(E/'00_SCOPE_AND_ACCEPTANCE.md'),
    effective_TLS='BLOCKED',production='BLOCKED',physical_root_cause='UNKNOWN',repair_implemented=False,
    repaired_generalization='NOT_RUN',original_success_reproduction='10/10 TLS-valid retained; 114754 NO_RECOMMENDATION retained'))

record=f'''\n\n## CLUSTER-01 / CL2-10 R1 — 2026-10-09 Asia/Shanghai / Codex主控 + OpenCode独审 / BLOCKED · STOPPED

- 本轮用户明确授权“121647有效TLS残差归因与定向离线修复（证据充分才编码）”；不是旧CL2-10链路集成提议。唯一表 {E.as_posix()}/00_SCOPE_AND_ACCEPTANCE.md v1 / SHA {sha(E/'00_SCOPE_AND_ACCEPTANCE.md')}。生产/发布/设备/B2/B3未授权，未commit/push/deploy/capture。
- Codex唯一writer（仅诊断脚本/证据），ponytail实际路径C:/Users/30680/.codex/skills/ponytail/SKILL.md；scientific-toolkit的科学计算/EDA用于格式、行域和假设对照。主树起点{baseline['main_git']['branch']}/{baseline['main_git']['HEAD']}，dirty树含untracked/ignored全文件SHA；实际用冻结09C源码d0b3e313…，生产selector92d2ed…，未集成09B/09C。历史08/09A/09B/09C manifest85/97/164/126项全部复算；原NORMAL domain不在cl208audit overlay，找到原作业domain且匹配历史manifest后才复制。外部Git cwd沙箱失败保留，GIT_OPTIONAL_LOCKS=0只读核验后完成冻结。
- 根因等级：原拒绝机制直接数值证据强，物理唯一成因UNKNOWN。七原超限帧重现；72/ROI2=300点、RMS27.417988mm、支持率0.9466667，P95=50.291869360mm>50mm，P99=57.888807mm、max=60.713527mm，独立标量邻值低端50.227391mm本身超门。原GL_HOLDOUT_QUALITY正确。
- 单变量：独立SVD/配套刚体控制距离差≤浮点量级；ROI等权72 P95降49.770859mm但144升51.164517mm，ROI3和全FIT RMS恶化；frame等权72仍50.292049mm；四局部平面72/144/217降38.298270/36.493698/36.348731mm，但不是一个刚体TLS，不可放行。定位共同平面与测量局部几何失配的数值贡献，不能区分真地面/测距/混合表面。所有评价点/困难ROI/原门保留，未删尾点、未按SID/frame优化候选、未反向调验收集。
- 补审数值门收窄：frame等权通过原TLS/SVD数值差容差，但72 P95仍FAIL；ROI等权同时数值门FAIL与144 P95 FAIL。算法身份不同不蕴含必超数值容差。原报告selector=frozen dd1b58，本轮TLS诊断不调用selector；09C d0b3e3仅用于搜索回归。T108集合限定原CL2-07正常人体cohort，原11/10集合及两份binding SHA已补入inputs/cohort核验，不冒称全部capture或空场模板已试验。
- 11段原bin重建七数组精确一致，FIT/固定holdout行互斥。10个原TLS-valid均复現，114754仍valid但不推荐；现有capture不是独立物理GT，历史结果已知非盲测。46项-W error通过（35原+6差分+5诊断机制）；原09C搜索精确保留，单次较慢计时及原09C/本轮同SHA源码三轮配对原始值均保留，无算法复杂度改变，不承诺板端/生产时延。
- T107修复资格BLOCKED，无CL2-10最小算法补丁；candidate/只是复用09C冻结源。真实几何未修正，原72/ROI2修复前后都50.291869360mm FAIL。有效TLS仍BLOCKED；生产BLOCKED；无修复后泛化PASS。缺原现场身份/独立五点几何和本地原bag，后续可补证/规划，不具备直接算法修复/生产资格。
- OpenCode CLI {model['CLI_version']} / 实际{model['models'][0]} / session{model['session']}，初审/补审exit0/finish stop/export0，严格read白名单；原命令/输出/权限/model核验保存。独审 {E.as_posix()}/04_independent_review_02.md及03.md，首轮shell引号exit2未进入模型且IO/空文本保留；作者裁决04_codex_cross_review.md，未解决逻辑FAIL无，模型未亲自数值/SHA执行UNKNOWN保留。

{table}

- 本轮evidence：{E.as_posix()}，FINAL_REPORT/01_root_cause/02_shadow_ab_results/03_regression_results/04_independent_review/05_evidence_manifest齐全。初始578及补审cohort保护资产（最终{len(guards)}项）起止复算与append-only前缀核验绑定final_integrity.json；旧SHA/旧失败/旧记录不回填。新基线/代码/参数/执行环境记录完整。CL2-10到此停止，未自动解锁TLS、生产、B2/B3或后续阶段。
'''
with RETURN.open('ab') as stream:stream.write(record.encode('utf8'))
after=RETURN.read_bytes();assert after.startswith(before) and after[len(before):]==record.encode('utf8')
save('return_append_record.json',dict(path=str(RETURN),before_sha256=baseline['return_before_sha256'],
    after_sha256=sha(RETURN),append_only=True,old_prefix_exact=True,appended_bytes=len(after)-len(before)))

end=inventory(R)
outside={p:dict(before=baseline['main_all_files'].get(p),after=end.get(p))
         for p in sorted(set(end)|set(baseline['main_all_files'])) if end.get(p)!=baseline['main_all_files'].get(p)}
save('06_integrity.json',dict(protected_assets_verified=len(guards),protected_assets_changed=changed,
    main_files_end=end,main_context_changes=outside,main_git_end=git(R),
    scope='New evidence only in main; external CLUSTER-01 return authorized append. Outside-scope concurrent context not reverted or attributed.'))
pair=load(E/'03_search_paired.json');performance=''
for row in pair['rows']:
    performance+=f"- {row['case']}：当前原09C {row['median_sec']['control_09c']:.4f}s / 本轮副本 {row['median_sec']['local_10']:.4f}s（配对三次中位）。\n"
report=f'''# CL2-10 最终报告

2026-10-09 Asia/Shanghai。**CL2-10 结果：BLOCKED；SUBMITTED / STOPPED。121647有效TLS和生产接入仍BLOCKED。** 无生产算法改动、无CL2-10修复候选、无设备/B2/B3/采集。唯一验收表[00_SCOPE_AND_ACCEPTANCE.md](00_SCOPE_AND_ACCEPTANCE.md) v1。

## 1. 真实失败原因与证据等级

直接数值原因已独立复现：固定ROI2相对共同TLS平面具有持续局部位置结构，72/ROI2的300点原绝对距离P95=50.291869360mm>50mm。独立SVD与标量排序证明不是数值/统计误判，正确触发GL_HOLDOUT_QUALITY。共同平面与**测量局部几何**失配的数值贡献有FIT-only局部模型/留出对照支持；真实地面形状、测距偏差、内部混合表面或提取链中的唯一物理原因仍UNKNOWN。

E1：原bin/七数组/门控/标量计算直接证据强；E2：预注册单变量算法/坐标反事实，只证明计算机制；E3：独立表面身份/真实几何或设备干预缺失。不能把E2的局部拟合或投影当真实几何修正。详细根因、全部四ROI分布/几何/方向/梯度在[01_root_cause.md](01_root_cause.md)、01_reproduction.json及01_channel_diagnostics.json。

## 2. 修复前后与单变量结果

| 原ROI2 P95 mm | ordinal72 | ordinal144 | ordinal217 | 结论 |
|---|---:|---:|---:|---|
| 原TLS / 本轮结束原TLS | 50.291869 | 49.991438 | 46.854799 | 未修复，原FAIL保持 |
| ROI等总权重诊断 | 49.770859 | 51.164517 | 47.085129 | 失败转移至144，不合格 |
| 帧等总权重诊断 | 50.292049 | 49.991128 | 46.854618 | 无有效改善 |
| 四局部平面诊断 | 38.298270 | 36.493698 | 36.348731 | 非单一刚体TLS，不可放行 |

原72/ROI2 RMS=27.417988mm、signed mean=-0.796739mm、median=-1.229937mm、P99=57.888807mm、max=60.713527mm。ROI等权全FIT RMS22.383→22.541mm，72/ROI3 RMS11.066→13.120mm，改善不是整体几何修正。正权重所有FIT点保留、评价全点/固定困难ROI不变；没有删尾点/降低样本/改门。原bag在meta中仅为板端路径，本地未发现可复解码bag或原现场GT。

配套刚体坐标变化和独立SVD仅浮点量级差，不以此宣称真实外参正确。各项失败假设、不改善、其他ROI恶化及所有11段完整分布保留在[02_shadow_ab_results.json](02_shadow_ab_results.json)。这是诊断结果，**没有可资格的shadow修复**。

数值门必须按[01_root_cause.md](01_root_cause.md)末尾补记解读：帧等权通过原TLS/SVD角差/offset容差，但72 P95仍失败；ROI等权数值门失败且144 P95失败。不能把“不是现行raw算法身份”扩大为“一定超数值门”。补记与原AB数据均保留，不覆盖早先过宽措辞。

## 3. 最小算法变更与回归

生产/算法变更为0，没有补丁或新TLS导出；candidate/是复用09C冻结源，不是新修复。主树生产selector与09C不同，未把离线补丁假定为已集成。原报告生成selector为frozen dd1b58；TLS诊断沿原ROI/源行、**不运行selector**，09C d0b3e3仅搜索回归。原CL2-07正常人体cohort的10个TLS-valid全部原bin/七数组/原门复现；114754仍valid但NO_RECOMMENDATION。inputs/cohort和04_cohort_integrity.json闭合原11/10集合与既存SHA；不声称空场模板或任意其他capture已测试。固定holdout不进入拟合，历史验收已知不冒称盲测、不同capture不等于独立物理GT。

46项-W error回归通过：35原09B、6原09C差分、5诊断机制；详细命令/源SHA/exit0和具名结果见[03_regression_results.txt](03_regression_results.txt)、03_regression_command.json。不用测试总数替代修复资格。新修复后的泛化NOT_RUN。

复用09C源码逐SHA相同，100格关键搜索完整结果精确相同，原边界/假拒绝/无解/共线/小集回归保持。初次单测4.038/7.183s比旧中位数高，原慢记录保留；当前同环境原09C/本轮副本配对三次结果：

{performance}

未显示新增代码/复杂度退化，不推测热/时钟/调度原因；最坏O(n⁴)、O(n²)内存不变，仍不保证生产时延。没有重复09C性能开发。

## 4. OpenCode独审

实际CLI{model['CLI_version']} / `{model['models'][0]}` / session `{model['session']}`，初审/补审进程exit0、export0、finish stop。逐文件read白名单，其他agent工具deny；CLI命令/raw IO/有效权限/实际model完整记录保存。首轮shell引号错误exit2，未进入模型，不计独审；原IO/空文本保留。实际原文[初审](04_independent_review_02.md)、[补审](04_independent_review_03.md)，[索引](04_independent_review.md)，作者裁决[04_codex_cross_review.md](04_codex_cross_review.md)。T100/T108动作项已CLOSED、数值门区分准确、未解决逻辑FAIL无，总体BLOCKED/无修复资格；模型未执行数值/SHA的UNKNOWN保留，不伪称双份执行。

## 5. 逐ID验收与完整性

{table}

08/09A/09B/09C manifest85/97/164/126项复算；初始578项及补审cohort来源合计{len(guards)}保护资产起止相同。主树全文件含untracked/ignored起止库存及{len(outside)}个范围外上下文变化记录在00_baseline.json/06_integrity.json，未回滚或归因。旧证据、输入、GT、代码/参数未修改。原CLUSTER-01 return仅追加，前缀精确核验；最终字节绑定final_integrity.json及[05_evidence_manifest.json](05_evidence_manifest.json)。ponytail实际路径C:/Users/30680/.codex/skills/ponytail/SKILL.md；无新依赖。

## 6. 未解决风险与下一阶段条件

物理归因仍缺原现场对应表面的独立身份/几何和原bag独立复解码；现有同场景数据不能识别真表面与测量偏差的分摊，也不能凭多局部平面证明合法调平修复。T107 BLOCKED，因此不满足用户八项离线PASS条件。

**尚不具备直接算法修复或生产接入条件。** 可继续规划/取得原bag复解码或09A五点独立几何补证；对应不清或场景已变则仍BLOCKED。当前不擅自连板、重采、校准外参、放行TLS、发布/部署或启动B2/B3。原121647有效TLS解除必须另有授权和验收。本轮到此停止。
'''
(E/'FINAL_REPORT.md').write_text(report,encoding='utf8')
save('final_integrity.json',dict(protected_assets_verified=len(guards),protected_assets_unchanged=True,
    final_report_sha256=sha(E/'FINAL_REPORT.md'),verdict_sha256=sha(E/'verdict.json'),
    runtime_sha256=sha(E/'candidate/floor_sheet.py'),new_repair=False,
    return_path=str(RETURN),return_sha256=sha(RETURN),prefix_unchanged=True,main_context_changes=len(outside)))
with (E/'04_independent_review.md').open('a',encoding='utf8') as stream:
    stream.write('''# CL2-10 独审索引（Codex索引，模型原文另存）

首轮CLI引号解析exit2，未进入模型；机器文本为空，不计完成。该文件此前为空占位，现仅追加索引，首轮真实raw错误/完成记录保持。

实际OpenCode CLI独审和同会话补审：

- [初审原文](04_independent_review_02.md)
- [补审原文](04_independent_review_03.md)
- [实际模型/会话/退出](opencode_actual_model_03.json)
- [Codex交叉裁决](04_codex_cross_review.md)

补审裁定：未解决逻辑FAIL无；T100/T108动作项CLOSED、数值门区分准确；总体BLOCKED，无算法修复资格。模型未亲自执行数值/SHA，UNKNOWN保持。有效TLS/生产BLOCKED，设备/B2/B3 NOT_RUN。
''')
manifest={p.relative_to(E).as_posix():sha(p) for p in E.rglob('*') if p.is_file() and p.name!='05_evidence_manifest.json'}
save('05_evidence_manifest.json',dict(files=manifest,count=len(manifest),excludes=['05_evidence_manifest.json'],
     return_path=str(RETURN),return_sha256=sha(RETURN)))
for name,digest in manifest.items():assert sha(E/name)==digest,name
assert sha(RETURN)==load(E/'final_integrity.json')['return_sha256']
print('CL210_BLOCKED_SEALED',len(manifest),'PROTECTED',len(guards),'OUTSIDE_CONTEXT',len(outside),flush=True)
