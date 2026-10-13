"""Append this item's return and seal new evidence; previous evidence stays immutable."""
import subprocess
from prepare import E,R,load,save,sha,inventory

audit=load(E/'opencode_completion.json')
actual=load(E/'opencode_actual_model.json')
assert audit['exit_code']==0 and audit['marker']
assert actual['models']==['opencode-go/deepseek-v4.1-flash']
assert actual['last_finish']=='stop' and actual['export_exit_code']==0
assert 'Codex裁定：逻辑FAIL=无' in (E/'09_CODEX_CROSS_REVIEW.md').read_text(encoding='utf8')
baseline=load(E/'01_baseline.json')
guards=baseline['guards']
changed={path:dict(before=digest,after=sha(path)) for path,digest in guards.items() if sha(path)!=digest}
assert not changed,changed
version=load(E/'candidate_version.json')
assert sha(E/'candidate/floor_sheet.py')==version['source_sha256']
assert load(E/'05_regression_03_command.json')['candidate_sha256']==version['source_sha256']
assert load(E/'05_regression_03_command.json')['exit_code']==0
assert load(E/'04_benchmark.json')['candidate_sha256']==version['source_sha256']

bench=load(E/'04_benchmark.json')
table='| 候选数 | 路径 | 09B 中位秒 | 09C 中位秒 | 加速倍数 |\n|---:|---|---:|---:|---:|\n'
for row in bench['results']:
    if row['case']=='line':continue
    label={'failed_with_feasible':'失败兜底有解','noncollinear_no_solution':'非共线无解'}[row['case']]
    table+=f"| {row['size']} | {label} | {row['median_sec']['baseline']:.4f} | {row['median_sec']['candidate']:.4f} | {row['speedup']:.2f} |\n"
status={k:'PASS' for k in ['C01','C02','C03','C04','C05','C06','C07','C08','C09']}
status.update(E01='BLOCKED',D01='NOT_RUN')
notes={
 'C01':'主树全文件含 untracked/ignored SHA 库存；09B 164 项 manifest 及冻结资产起止核验',
 'C02':'60 候选分项插桩，min inclusive、循环残余和计数开销明确披露',
 'C03':'距离复用、原叉积几何剪枝；原成功/describe/SVD/门控不变；无 cap',
 'C04':'09B 完整枚举 full-dict 差分；正式基准每轮 exact dict 相同',
 'C05':'35 冻结 + 6 新差分 = 41 项 -W error；最终 03 回归 exit0；板端 NOT_RUN',
 'C06':'本机 25/60/100 无插桩三次交替基准；生产时延验收 NOT_RUN',
 'C07':'真实 bin 重建 11 clean cells；最终源码再次绑定；ROI 不变，TLS 仍 BLOCKED',
 'C08':'真实只读指定 CLI 模型/有效权限/IO/session export；作者核验与审计 UNKNOWN 区分',
 'C09':'旧资产不变，append-only 本工单 return、最终 manifest 逐 SHA 复算',
 'E01':'无生产接入、CL2-10、发布或部署授权',
 'D01':'无设备/物理/采集/B2/B3；121647 有效 TLS BLOCKED'}
acceptance='| ID | 状态 | 证据与限制 |\n|---|---|---|\n'+''.join(
    f'| {key} | {value} | {notes[key]} |\n' for key,value in status.items())
save('verdict.json',dict(state='SUBMITTED / STOPPED',acceptance_version='v1',
     acceptance_sha256=sha(E/'00_SCOPE_AND_ACCEPTANCE.md'),status=status,notes=notes,
     runtime_source_sha256=version['source_sha256'],production_integrated=False,
     effective_TLS='BLOCKED',physical_cause='UNKNOWN',device='NOT_RUN',production_latency='NOT_RUN'))

return_path=R/'docs/sidequests/returns/CL2-09C.md'
return_path.parent.mkdir(parents=True,exist_ok=True)
before=return_path.read_bytes() if return_path.exists() else b''
record=f'''\n\n## CL2-09C / r1 / Codex / 2026-10-09 Asia/Shanghai

状态：SUBMITTED / STOPPED。CL2-09B 已按用户裁定为离线修复 PASS；本轮不回填旧记录。唯一验收表 v1：{E.as_posix()}/00_SCOPE_AND_ACCEPTANCE.md；SHA {sha(E/'00_SCOPE_AND_ACCEPTANCE.md')}。

起始 {baseline['branch']} / {baseline['HEAD']}，混合 dirty tree 含 untracked/ignored 的库存为 01_baseline.json。Codex 唯一 writer，ponytail 实际路径 C:/Users/30680/.codex/skills/ponytail/SKILL.md。OpenCode 只读审计实际 session {actual['session']}，模型 {actual['models'][0]}，CLI {actual['CLI_version']}。

根因及调用者：_roi_metrics 失败兜底逐四元组重复距离与共线检查；影响 detect_floor_regions_v2→v3。只在新隔离 candidate/floor_sheet.py 预计算成对 hypot、嵌套原序间距剪枝、复用原叉积共线关系。原成功、完整失败 dict、稳定并列、SVD、独立计数及门控保留；15cm/身份/purity/TLS 源不改。可审查补丁 02_fix.patch。源码 SHA {version['source_sha256']}。

{table}

41 项测试含 35 冻结项和 6 新差分项，最终实际 argv/exit0/源码 SHA 在 05_regression_03_command.json，具名日志 05_regression_03.stderr；原沙箱 socket 失败留存，不降断言。本机 Python3.12.10/NumPy1.26.4；板端 Python3.8/NumPy1.17 实际性能 NOT_RUN。

{acceptance}

未闭合：最坏仍 O(n⁴)，不声明任意输入绝对时限；生产接入与 CL2-10 BLOCKED；121647 ordinal72/ROI2 P95=0.05029186936019117m，50mm 门控仍 FAIL，有效 TLS BLOCKED，物理成因 UNKNOWN。无部署、采集、B2/B3、commit/push。

全部原始证据、独审和 Codex 裁决位于 {E.as_posix()}。新 return 仅追加，本轮 manifest 与 final_integrity 绑定最终字节；停止，不自动推进。
'''
with return_path.open('ab') as stream:stream.write(record.encode('utf8'))
after=return_path.read_bytes()
assert after.startswith(before) and after[len(before):]==record.encode('utf8')
save('return_append_record.json',dict(path=str(return_path),previous_bytes=len(before),
     appended_bytes=len(after)-len(before),source_sha256=version['source_sha256'],sha256=sha(return_path),
     append_only_prefix_verified=True))

end=inventory(R)
own_return=return_path.relative_to(R).as_posix()
context_changes={path:dict(before=baseline['full_tree'].get(path),after=end.get(path))
    for path in sorted(set(baseline['full_tree'])|set(end))
    if path!=own_return and baseline['full_tree'].get(path)!=end.get(path)}
save('09_integrity.json',dict(protected_assets_verified=len(guards),protected_assets_changed=changed,
     full_tree_end=end,scope_excludes=str(E),out_of_scope_context_changes=context_changes,
     original_HEAD=baseline['HEAD'],final_HEAD=subprocess.check_output(['git','rev-parse','HEAD'],cwd=R,text=True).strip(),
     note='Concurrent outside-scope differences are context only, not reverted or attributed.'))
report=f'''# CL2-09C 离线等价性能优化提交

2026-10-09 Asia/Shanghai。**SUBMITTED / STOPPED；C01–C09 自验 PASS；尚不具备生产接入资格。** 设备/物理/B2/B3 NOT_RUN，121647 有效 TLS BLOCKED、物理成因 UNKNOWN。唯一验收表 v1 为 [00_SCOPE_AND_ACCEPTANCE.md](00_SCOPE_AND_ACCEPTANCE.md)。

只交付新隔离 [candidate/floor_sheet.py](candidate/floor_sheet.py) 与 [02_fix.patch](02_fix.patch)，variant `cl209c_exact_roi_search_v1`。冻结 09B 完整实现作 oracle。通过距离表、原序间距剪枝和首对共线关系复用去掉重复工作；原成功路径、describe/SVD/门控及稳定并列规则未改变。无 cap、超时判无解、近似阈值或质量标准降低。详细证明及第一版记录见 [07_AUTHOR_ANALYSIS.md](07_AUTHOR_ANALYSIS.md)。

## 实际性能

{table}

每格为同输入、同本机环境、基线/候选交替三次无插桩调用的中位数，所有轮次完整 dict 精确相同；原始样本和环境/源码 SHA 见 [04_benchmark.json](04_benchmark.json)。完全共线快速拒绝亦已测量。首样本不是冷 OS/BLAS 进程；范围/时序抖动公开，不把相对加速当板端保证。最坏仍 O(n⁴)，内存 O(n²)，生产时延验收 NOT_RUN。

[03_profile_03.json](03_profile_03.json) 分别记录排序、枚举 next、hypot、min、np.all、SVD；含插桩开销且存在 inclusive 项，不相加或当真实基准。SVD 数值输入与执行保持原样，不声称减少 SVD 次数。

## 等价、门控与审计

41 项（35 冻结 + 6 新差分）最终 -B -W error 全过。新检查以 09B 穷举完整 dict 为 oracle，覆盖小/大、无解、重复、并列、反序、平移、边界和 caller ownership。命令/exit0/最终源码 SHA 在 [05_regression_03_command.json](05_regression_03_command.json)，具名日志在 [05_regression_03.stderr](05_regression_03.stderr)。原沙箱 socket 失败保留；没有降断言。本机 Python3.12.10/NumPy1.26.4，Python3.8 语法通过；板端运行 NOT_RUN。

原 121647 bin 只读重建 11 个 clean cells，09B/09C/原四 ROI 完全相同；最终绑定见 [06_session_final_binding.json](06_session_final_binding.json)。ordinal72/ROI2 P95=0.05029186936019117m，50mm 门控仍 FAIL、有效 TLS BLOCKED。未重新拟合 TLS、导出替代真实输入或判定物理成因。

真实 OpenCode CLI {actual['CLI_version']} / `{actual['models'][0]}` / session `{actual['session']}`，只读白名单，其他工具 deny。独审 [08_OPENCODE_REVIEW.md](08_OPENCODE_REVIEW.md)；作者交叉裁决 [09_CODEX_CROSS_REVIEW.md](09_CODEX_CROSS_REVIEW.md)。原 IO/argv/有效权限/完整 export 均保留；审计员没有亲自重跑数值/SHA，UNKNOWN 边界保留，不伪称双份执行。

## 逐项验收与完整性

{acceptance}

09B 164 项 manifest 已复算；{len(guards)} 个历史/源码/输入守护起止相同。主树含 untracked/ignored 的起止库存和 {len(context_changes)} 个范围外上下文变化记录在 01_baseline.json / 09_integrity.json，不回滚或归因。原生产 floor_sheet.py、历史证据及真实输入未由本轮修改。ponytail 实际路径 C:/Users/30680/.codex/skills/ponytail/SKILL.md。无新依赖。

本工单 return 已 append-only 写入 docs/sidequests/returns/CL2-09C.md；不回填 CLUSTER-01 或 09B。最终字节由 final_integrity.json、[10_evidence_manifest.json](10_evidence_manifest.json) 绑定。当前停止点是隔离离线交付；不自动开启 CL2-10、生产接入、发布、部署、采集、B2/B3 或 commit/push。
'''
(E/'FINAL_REPORT.md').write_text(report,encoding='utf8')
save('final_integrity.json',dict(protected_assets_verified=len(guards),protected_assets_unchanged=True,
     candidate_sha256=sha(E/'candidate/floor_sheet.py'),baseline_sha256=sha(E/'baseline/floor_sheet.py'),
     acceptance_sha256=sha(E/'00_SCOPE_AND_ACCEPTANCE.md'),final_report_sha256=sha(E/'FINAL_REPORT.md'),
     return_path=str(return_path),return_sha256=sha(return_path),out_of_scope_changes=len(context_changes)))
manifest={p.relative_to(E).as_posix():sha(p) for p in E.rglob('*') if p.is_file() and p.name!='10_evidence_manifest.json'}
save('10_evidence_manifest.json',dict(files=manifest,excludes=['10_evidence_manifest.json'],count=len(manifest)))
for name,digest in manifest.items():assert sha(E/name)==digest,name
assert sha(return_path)==load(E/'final_integrity.json')['return_sha256']
print('SEALED_MANIFEST_PASS',len(manifest),'CONTEXT_CHANGES',len(context_changes),flush=True)
