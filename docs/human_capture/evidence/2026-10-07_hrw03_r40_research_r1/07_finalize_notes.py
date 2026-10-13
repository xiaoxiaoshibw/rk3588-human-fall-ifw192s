from pathlib import Path
import hashlib
import json

OUT = Path(__file__).parent
ROOT = OUT.parents[3]
target = ROOT / 'docs/human_capture/returns/HR-W03.md'
before = (OUT / '05_return_before.txt').read_bytes()
append = (OUT / '05_return_append.md').read_text(encoding='utf-8').encode('utf-8')
assert target.read_bytes() == before + append
note = '''

### R40收尾补记（只追加）

06_integrity首轮exit1：393个protected文件无漂移；失败仅因校验器把以Windows文本方式保存的append.md之CRLF，与实际以二进制追加的LF相比较。原return前缀和实际追加内容正确，没有回传破坏。旧失败stdout/stderr/run/json/md保留；r2按真实追加字节复核，09_integrity_r2.md/json为当前完整性结果。

集中报告现以07_research_and_minimal_plan_r2.md为最终；研究结论、GT/production状态不变，仅补完整性校验修订及真实首轮exit1记录。观察到范围外README变化及cap_20261007_154920/下载部署证据新增，均保留，未由本轮脚本写入，不推测操作者。REWORK_REQUIRED不变。
'''
with (OUT / '07_return_final_note.md').open('x', encoding='utf-8') as f:
    f.write(note)
with target.open('ab') as f:
    f.write(note.encode('utf-8'))
assert target.read_bytes() == before + append + note.encode('utf-8')
report = (OUT / '07_research_and_minimal_plan.md').read_text(encoding='utf-8')
report = report.replace('[09_integrity.md](09_integrity.md)', '[09_integrity_r2.md](09_integrity_r2.md)')
report = report.replace('最终 [09_integrity_r2.md]', '当前最终 [09_integrity_r2.md]')
report += '''

## 收尾修订 r2

本r2仅补校验与记录，不改变研究数字/GT或方案。06_integrity首轮exit1的原因是校验器比较CRLF文本产物与实际LF追加字节，393个受保护文件已经全部一致。现由原return字节+规范化实际追加字符串+本次补记验证，旧失败run/stdout/stderr与09_integrity.json/md保留，09_integrity_r2.json/md为当前。前文诊断exit0只指baseline/读取/02/03/04等命令，不包括首次完整性校验；真实失败不抹除。

范围外观测：docs/human_capture/README.md变化；captures/remote/cap_20261007_154920/{meta.json,points.bin}与docs/human_capture/evidence/2026-10-07_files_download_deploy/README.md新增。它们不是本轮写入目标，保持原状；当前绑定source/reference、R39历史与7个源码未受影响。最终仍REWORK_REQUIRED。
'''
with (OUT / '07_research_and_minimal_plan_r2.md').open('x', encoding='utf-8') as f:
    f.write(report)
print(json.dumps({'report': '07_research_and_minimal_plan_r2.md', 'return_prefix_preserved': True, 'current_return_sha256': hashlib.sha256(target.read_bytes()).hexdigest(), 'initial_integrity_failure_preserved': True}))
