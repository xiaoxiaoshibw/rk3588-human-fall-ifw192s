"""Finalize hashes and command index; no further target work."""
import json
import subprocess
from audit import ROOT, OUT, RET, sha, save

baseline = json.loads((OUT / 'baseline.json').read_text('utf8'))
integrity = json.loads((OUT / 'integrity.json').read_text('utf8'))
assert integrity['pass'] and integrity['return_prefix_unchanged']
assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT).decode().strip() == baseline['head']
for p in OUT.glob('*.run.json'):
    r = json.loads(p.read_text('utf8'))
    name = p.name[:-len('.run.json')]
    assert sha(OUT / (name + '.stdout.log')) == r['stdout_sha256']
    assert sha(OUT / (name + '.stderr.log')) == r['stderr_sha256']
text = (OUT / 'commands.md').read_text('utf8')
tail = text[text.index('基线实际命令：'):]
lines = ['# 实际审核命令及退出码', '', '执行包装统一：`python -B -W error -X utf8 <本目录>/audit.py <name> <下列实际子命令>`。同名三件文件保存真实输出和退出码。', '', '| 记录 | 实际子命令 | exit |', '|---|---|---|']
for p in sorted(OUT.glob('*.run.json')):
    r = json.loads(p.read_text('utf8'))
    lines.append('| %s | `%s` | %s |' % (p.stem, ' '.join(r['argv']), r['exit_code']))
lines += ['', tail, '', '收尾命令：`python -B -W error -X utf8 <本目录>/audit.py closeout python -B -W error -X utf8 <本目录>/closeout.py`，实际结果见closeout.run.json；仅汇总已有证据，不再执行目标功能。']
(OUT / 'commands.md').write_text('\n'.join(lines) + '\n', encoding='utf8')
assert (ROOT / RET).read_bytes()[:baseline['return_prefix_bytes']]
files = {p.relative_to(ROOT).as_posix(): {'sha256': sha(p), 'bytes': p.stat().st_size,
    'role': 'review-only new evidence/tool/log; no production implementation'} for p in sorted(OUT.rglob('*')) if p.is_file() and p.name != 'changes.json'}
save('changes.json', {'new_review_files': files, 'return_append_only': {'path': RET,
    'original_prefix_bytes': baseline['return_prefix_bytes'], 'original_prefix_sha256': baseline['return_prefix_sha256'],
    'current_sha256': sha(ROOT / RET), 'append_bytes': (ROOT / RET).stat().st_size - baseline['return_prefix_bytes']},
    'scope': 'new review evidence directory plus this return append only; ephemeral replay test fixtures were removed by suite',
    'final_integrity': integrity, 'manifest_exclusions': ['changes.json itself', 'closeout execution logs created by outer runner after this manifest']})
report = (OUT / 'REVIEW.md').read_text('utf8')
assert all('| SEM-%02d |' % i in report for i in range(1, 17))
assert '**FAIL（原PASS改判）**' in report
print('CLOSEOUT_PASS; 16 IDs, log hashes, unchanged HEAD, final integrity;', len(files), 'new evidence files indexed')
