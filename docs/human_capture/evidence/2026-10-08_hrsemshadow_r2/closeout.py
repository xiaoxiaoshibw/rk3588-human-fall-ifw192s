"""Close R2 only after actual old-asset verification; create a final delivery manifest."""
import hashlib
import json
from datetime import datetime, timezone, timedelta
from record import OUT, ROOT, RETURN, sha, write

b = json.loads((OUT / '00_baseline.json').read_text('utf8'))
i = json.loads((OUT / 'integrity.json').read_text('utf8'))
assert i['pass'] and i['head_unchanged'] and i['return_prefix_unchanged']
assert not i['changed'] and not i['unexpected_new_git_files']
assert json.loads((OUT / 'browser_server_shutdown.json').read_text('utf-8-sig'))['scope'] == 'temporary R2 read-only helper only'
r1_count = sum(n.startswith('docs/human_capture/evidence/2026-10-08_hrsemshadow_r1/') for n in b['files'])
review_count = sum(n.startswith('docs/human_capture/evidence/2026-10-08_hrsemshadow_review_r1/') for n in b['files'])
old_return = b['files'][RETURN.relative_to(ROOT).as_posix()]
prefix = RETURN.read_bytes()[:old_return['bytes']]
assert hashlib.sha256(prefix).hexdigest() == old_return['sha256']
text = f'''# R2 旧资产与新交付完整性

最终 `integrity_final.run.json` exit0；`integrity.json` pass=true，head_unchanged=true。

- 起始6140路径、43,283,465,274字节；其中return独立验证旧字节前缀，其余{i['checked_files']}路径逐项检查SHA/大小、原符号链接或缺失状态。
- changed=[]；unexpected_new_git_files=[]。R1执行 evidence {r1_count}条路径和R1独立复审 evidence {review_count}条路径均保持起始内容；冻结验收表、ticket、原始captures、生产源码/config/阈值、console包无漂移。
- return原{old_return['bytes']}字节前缀SHA `{old_return['sha256']}`不变，只在末尾追加R2回传和完整性收尾。允许追加的return与禁止修改的冻结evidence分别核对。
- 基线范围：全git tracked/untracked加ignored captures、既有HC文档/evidence和console dist；当前R2目录排除于旧资产集，.git内部不属于业务资产检查。不将旧deleted tracked路径或src/CMakeLists符号链接改成新普通文件。
- 实际仓库新增仅R2目录；生产算法修改0、冻结门/原数据修改0、旧evidence改写0。HEAD/branch未改变，无commit/push/deploy/capture/生产接入。
- R2新产物的SHA见delivery_manifest.json，包含最终页面、源码、报告、合成夹具、截图和真实日志；manifest不自包含。先前页面草稿/有警告与失败日志保留，不计最终通过。
- 临时HTTP helper仅绑定127.0.0.1:8879供本地只读浏览器测试，已确认进程命令后停止，见browser_server_shutdown.json。浏览器UNKNOWN下载是明确SYNTHETIC夹具，复制到本目录用于验证，不作为真实GT。

完整性检查不代表GT真值或算法目标通过。最终分项为11 PASS、5 BLOCKED；WD02仍BLOCKED，离线交付BLOCKED，生产未授权。
'''
with (OUT / '05_integrity.md').open('x', encoding='utf8') as f:
    f.write(text)
stamp = datetime.now(timezone(timedelta(hours=8))).isoformat()
with RETURN.open('ab') as f:
    f.write(f'\n\n### {stamp} R2 完整性收尾\n\n- integrity_final实测exit0：{i["checked_files"]}非return路径无变化；return原{old_return["bytes"]}字节前缀不变；HEAD未变、范围外新增0。R1执行/复审证据均零改写。最终05_integrity与delivery_manifest已生成；临时本地server已停止。SEM-15按实测恢复PASS；整单仍SUBMITTED/BLOCKED、未ACCEPTED，生产未授权。\n'.encode('utf8'))
assert hashlib.sha256(RETURN.read_bytes()[:old_return['bytes']]).hexdigest() == old_return['sha256']
with (OUT / 'commands.md').open('a', encoding='utf8') as f:
    f.write('\n收尾实际命令：`python -B -W error -X utf8 docs/human_capture/evidence/2026-10-08_hrsemshadow_r2/record.py integrity`，由record.py run integrity_final记录，exit0。`closeout.py`只在此检查成功后生成05_integrity/manifest并追加上述return收尾。\n')
write('closeout_summary.json', {'old_checked': i['checked_files'], 'R1_evidence_paths': r1_count, 'R1_review_paths': review_count,
    'old_asset_changes': 0, 'return_prefix_preserved': True, 'outside_scope_additions': 0,
    'offline_delivery': 'BLOCKED', 'production': 'NOT_AUTHORIZED', 'return_final_sha256': sha(RETURN)})
write('delivery_manifest.json', {'created_asia_shanghai': stamp,
    'files': {p.relative_to(OUT).as_posix(): {'sha256': sha(p), 'bytes': p.stat().st_size}
              for p in sorted(OUT.rglob('*')) if p.is_file() and p.name != 'delivery_manifest.json'},
    'return_final_sha256': sha(RETURN), 'authority': 'Review tool/source/page hashes must be compared with a trusted delivery copy',
    'excludes': 'manifest itself and closeout process stdout/stderr/run metadata created after its snapshot'})
print('R2_CLOSED', i['checked_files'], 'old non-return paths unchanged; return prefix preserved; offline BLOCKED')
