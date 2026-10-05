from pathlib import Path

ROOT=Path(__file__).resolve().parents[4]
DOC=ROOT/'docs/human_fall'
entry=('2026-10-04 GL-I05 R2 **软件独审PASS / STOPPED**：[唯一v1](GLI05_ACCEPTANCE.md)/'
       '[收口](evidence/2026-10-04_gl_i05_r2/31_CLOSEOUT.md)/'
       '[最终指定二审](evidence/2026-10-04_gl_i05_r2/opencode_second_review_02/00_review.md)。'
       'C01–C06/E01–E02/S01/Q01–Q10 PASS；B01/B02 BLOCKED、D01/D02 NOT_RUN，整单未ACCEPTED。'
       '无writer、无新软件FAIL，仅离线研究/源点证据工具；生产/输入/旧证据冻结，GL04/GL05设备边界保持。'
       '原算法二审检查器覆盖偏差已保留全版本并新编号不可变复验，未掩盖历史。')
for name in ('README.md','DISPATCH.md','WORKFLOW.md'):
    path=DOC/name;old=path.read_text(encoding='utf8');first,rest=old.split('\n',1)
    path.write_text(first+'\n\n'+entry+'\n'+rest,encoding='utf8')
path=DOC/'GLI05_ACCEPTANCE.md';lines=path.read_text(encoding='utf8').splitlines()
software={'C01','C02','C03','C04','C05','C06','E01','E02','S01'}|{'Q%02d'%i for i in range(1,11)}
for i,line in enumerate(lines):
    if line.startswith('状态：'):
        lines[i]='状态：GL-I05 R2软件独审PASS / STOPPED。判据保持v1；最终不可变指定二审与收口见evidence/2026-10-04_gl_i05_r2/31_CLOSEOUT.md。B01/B02 BLOCKED、D01/D02 NOT_RUN，整单未ACCEPTED；无writer、不接运行时。R1及原二审过程历史保留。'
    if line.startswith('| '):
        cells=line.split('|');key=cells[1].strip()
        if key in software:
            cells[-2]=' PASS（R2最终独审） '
            lines[i]='|'.join(cells)
path.write_text('\n'.join(lines)+'\n',encoding='utf8')
path=DOC/'GLI05_TASK.md';lines=path.read_text(encoding='utf8').splitlines()
lines[2]='状态：GL-I05 R2软件独审PASS / STOPPED。Codex唯一研究writer已停写，指定Go Flash/defaultDB最终不可变二审通过；C/E/S/Q软件PASS，B01/B02 BLOCKED、D01/D02 NOT_RUN，整单未ACCEPTED。只离线研究，不接生产/不启动GL-05。详见evidence/2026-10-04_gl_i05_r2/31_CLOSEOUT.md。'
path.write_text('\n'.join(lines)+'\n',encoding='utf8')
append=('\n\n## 2026-10-04 GL-I05 R2 Codex最终独审收口\n\n'
        'C01–C06/E01–E02/S01/Q01–Q10 PASS，B01/B02 BLOCKED，D01/D02 NOT_RUN；整单未ACCEPTED。'
        '唯一GLI05_ACCEPTANCE.md v1、收口evidence/2026-10-04_gl_i05_r2/31_CLOSEOUT.md、'
        '最终指定Go Flash/defaultDB二审opencode_second_review_02/00_review.md。'
        '实际最终probe10.891s/exit0，复验155.906s/exit0/stop，session ses_efd29d375ffeh5FIoGvw4SS2G2；'
        '29_revalidation_session.json核实际provider/model，首尾76 SHA与13检查器SHA不变。'
        '原940.140s算法二审自身检查器覆盖偏差从原始CLI流恢复27脚本版本/26命令输出，'
        '新编号一次执行复验后才收口S01/Q10，不掩盖历史。38case同序列正确、六synthetic dominant正例、'
        '源点351255行精确匹配；Python3.8 AST通过，冻结代码不变复用423/2回归。'
        '无writer、无新FAIL、不派R3；只离线研究与证据工具，不生产接入/部署/采集/网络/driver，GL04/GL05边界保持。\n')
for name in ('REVIEW_LOG.md','returns/GL-I05.md','CLI_RECOVERY.md'):
    with (DOC/name).open('a',encoding='utf8') as f:f.write(append)
