import hashlib
import json
from pathlib import Path

OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[3]
DOC=ROOT/'docs/human_fall'
entry=('2026-10-04 主线GL-E01 R1 **来源链独审PASS / STOPPED**：'
       '[唯一v1](GLE01_ACCEPTANCE.md)/[收口](evidence/2026-10-04_mainline_evidence_r1/17_CLOSEOUT.md)/'
       '[指定独审](evidence/2026-10-04_mainline_evidence_r1/opencode_review_01/00_review.md)。'
       '原bag实际SHA、89frames/4372400points、26B→28B全部bytes/XYZ/meta/NPZ匹配，'
       'A01–A05/S01/Q01–Q06与B01来源链PASS；B02物理BLOCKED，D01 NOT_RUN，D02 DPR环境BLOCKED。'
       '旧NPZ/旧GL-I05记录不回填，GL-I05软件PASS保持；不新采集/部署/driver/network变化。'
       '当前主线转录制外参/ROI身份与实际DPR，详情见收口。')
for name in ('README.md','DISPATCH.md','WORKFLOW.md'):
    p=DOC/name;first,rest=p.read_text(encoding='utf8').split('\n',1)
    p.write_text(first+'\n\n'+entry+'\n'+rest,encoding='utf8')
p=DOC/'GLE01_ACCEPTANCE.md';lines=p.read_text(encoding='utf8').splitlines()
software={'A01','A02','A03','A04','A05','S01'}|{'Q%02d'%i for i in range(1,7)}
for i,line in enumerate(lines):
    if line.startswith('| '):
        cells=line.split('|');key=cells[1].strip()
        if key in software:cells[-2]=' PASS（指定独审） '
        elif key=='B01':cells[-2]=' PASS（仅来源链） '
        lines[i]='|'.join(cells)
lines.insert(2,'状态：GL-E01 R1来源链/软件取证独审PASS / STOPPED；B02 BLOCKED、D01 NOT_RUN、D02 BLOCKED，整单未ACCEPTED。见evidence/2026-10-04_mainline_evidence_r1/17_CLOSEOUT.md。')
p.write_text('\n'.join(lines)+'\n',encoding='utf8')
append=('\n\n## 2026-10-04 GL-E01 R1独审收口\n\n'
    'GLE01_ACCEPTANCE.md v1：A01–A05/S01/Q01–Q06 PASS，B01仅原bag→bin→NPZ来源链PASS；'
    'B02物理BLOCKED，D01 NOT_RUN，D02 DPR环境BLOCKED。'
    '用户继续主线后用既有SSH只读恢复原bag，89frames/4372400points/全量bytes与XYZ及headers精确对应，'
    '既定bag time round6原义保持；不回填旧NPZ/旧GL-I05当时来源未核字段。'
    '指定Go Flash/defaultDB probe11.468s/exit0，独审1099.531s/exit0/stop，'
    'session ses_efcf6b467ffewHbmcPqpeFNz16（15_review_session.json）；'
    'source/decoder/scope首尾不变；无新部署/采集/driver/网络配置/算法设备测试。'
    'timestamp逐点f64→f32最大数值误差0.007811已独立测得，不声称单位/微秒精度/同步；header精确保持。'
    '收口evidence/2026-10-04_mainline_evidence_r1/17_CLOSEOUT.md；'
    'GL-I05软件PASS保持，当前来源缺口已补，录制外参/ROI身份与GL04真实DPR仍待证据。\n')
for name in ('returns/GL-E01.md','REVIEW_LOG.md','CLI_RECOVERY.md'):
    with (DOC/name).open('a',encoding='utf8') as f:f.write(append)
