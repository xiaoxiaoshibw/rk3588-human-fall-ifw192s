import ast
import hashlib
import json
from pathlib import Path

OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[3]
DOC=ROOT/'docs/human_fall'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
for p in OUT.glob('*.py'):ast.parse(p.read_text(encoding='utf8'),feature_version=(3,8))
record=json.loads((OUT/'04_local_chain_audit.json').read_text(encoding='utf8'))
assert record['all_headers_layout_bytes_xyz_match'] and len(record['frames'])==89
path=DOC/'returns/GL-E01.md'
with path.open('x',encoding='utf8') as f:
    f.write('# GL-E01 回传 / R1 / Codex / 2026-10-04\n\n'
        'SUBMITTED / STOPPED；验收GLE01_ACCEPTANCE.md v1。'
        '用户本轮继续推进主线，恢复已有原件并只读取证；不是部署/新采集/网络配置。'
        'ponytail已读C:/Users/30680/.codex/skills/ponytail/SKILL.md，单证据writer。'
        'master/cbd0be1，00全树baseline；生产/原captures/NPZ/draft/旧证据不变。\n\n'
        '| ID | 自验 | 证据 |\n|---|---|---|\n'
        '| A01 | PASS | 02原bag实际存在/magic/SHA；03首尾SHA |\n'
        '| A02 | PASS | 03原PointCloud2布局26→28全量；04b headers精确/既定bag time6位舍入 |\n'
        '| A03 | PASS | 原bag canonical完整bytesSHA=本地bin；89frames/4372400points逐帧SHA与NPZ XYZ一致 |\n'
        '| A04 | PASS | 03数值转换loss0.007811、06反例；不校验单位/不声称微秒 |\n'
        '| A05 | PASS | 05当前config/log SHA/mtime/摘录未知绑定；不解B02 |\n'
        '| S01 | BLOCKED（待独审） | 范围/原始command-exit/3.8 AST、待实际指定模型二审 |\n'
        '| B01 | BLOCKED（待独审） | 源链自验通过，待独审，不是物理标定 |\n'
        '| B02 | BLOCKED | source-world/recording config/ground ROI身份未知 |\n'
        '| D01 | NOT_RUN | 未run跌倒算法/性能/测量/部署/采集 |\n'
        '| D02 | BLOCKED | 真实DPR控制接口不足；旧GL04实际项仍NOT_RUN |\n'
        '| Q01–Q05 | PASS（自验） | 06身份/帧负例及03–05实证 |\n'
        '| Q06 | BLOCKED（待独审） | 提交停写，新probe后独审 |\n\n'
        '命令与exit详07_READONLY_COMMANDS_AND_BOUNDARIES.md；设备只读01/02/03/05 exit0；'
        '04首版audit误把raw bag时间与已6位舍入meta作位级比较exit1，原日志保留；'
        '04b修复精确既定转换exit0，06负例exit0。旧timestamp微秒精度注释不作为证据。'
        '不改旧NPZ里的source_bag_hash_verified=false，追加独立来源链审计sidecar。'
        '准备交Go Flash/defaultDB独立复核，不宣称ACCEPTED。\n')
entry=('2026-10-04 当前主线GL-E01 **SUBMITTED待独审**：'
       '[唯一v1](GLE01_ACCEPTANCE.md)/[取证范围](evidence/2026-10-04_mainline_evidence_r1/00_SCOPE_AND_DIAG.md)。'
       '既有原bag已只读找到，实际SHA与声明一致，原26B独立重建canonical28B与本地bin/NPZ全量匹配；'
       '仅来源链自验，不是物理标定。Codex已停写，fresh probe后Go Flash/defaultDB复核。'
       'GL-I05软件PASS保持；外参/ROI身份仍BLOCKED，GL04真实DPR当前API不可控；不新采集/部署/网络/driver变化。')
for name in ('README.md','DISPATCH.md','WORKFLOW.md'):
    p=DOC/name;first,rest=p.read_text(encoding='utf8').split('\n',1)
    p.write_text(first+'\n\n'+entry+'\n'+rest,encoding='utf8')
files=list(OUT.glob('*'))+[DOC/'GLE01_ACCEPTANCE.md',path,
    ROOT/'captures/remote/cap_20261002_163621/meta.json',
    ROOT/'captures/remote/cap_20261002_163621/points.bin',
    DOC/'evidence/2026-10-03_gl_i02_r1/08_real/real_candidate.adapted.npz',
    ROOT/'src/human_capture/core/bag2session.py',ROOT/'src/human_fall_detection/core/capture_input.py']
manifest=dict(kind='gle01_submission',status='SUBMITTED',writer='Codex',
    acceptance='GLE01_ACCEPTANCE.md v1',head=json.loads((OUT/'00_before_baseline.json').read_text(encoding='utf8'))['head'],
    ponytail_skill_path='C:/Users/30680/.codex/skills/ponytail/SKILL.md',
    files={p.relative_to(ROOT).as_posix():sha(p) for p in files if p.is_file()},
    physical_verified=False,recording_config_binding='unknown',old_npz_unmodified=True)
with (OUT/'09_submission_manifest.json').open('x',encoding='utf8') as f:json.dump(manifest,f,indent=2)
print(json.dumps(dict(status='SUBMITTED',files=len(manifest['files']),source_points=record['total_points'])))
