from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
DOC = ROOT / 'docs/human_fall'
entry = ('2026-10-04 GL-I05 R2 **同项返工实施中**：R1指定Go Flash/defaultDB独审REWORK，'
         '[R1收口](evidence/2026-10-04_gl_i05_r1/09_CLOSEOUT.md)/'
         '[二审](evidence/2026-10-04_gl_i05_r1/opencode_second_review_01/00_review.md)/'
         '[唯一验收v1](GLI05_ACCEPTANCE.md)。Codex唯一研究writer，旧提交停写；'
         '只新evidence/2026-10-04_gl_i05_r2/research_01，生产/数据/旧证据冻结。'
         '完成自验停写后fresh probe再指定二审；B01/B02 BLOCKED、D01/D02 NOT_RUN，未ACCEPTED。')
for name in ('README.md', 'DISPATCH.md', 'WORKFLOW.md'):
    path = DOC / name
    old = path.read_text(encoding='utf8')
    first, rest = old.split('\n', 1)
    path.write_text(first + '\n\n' + entry + '\n' + rest, encoding='utf8')
results = {key: 'FAIL' for key in ('C01', 'C02', 'C03', 'C06', 'E01',
                                  'Q01', 'Q03', 'Q05', 'Q08', 'Q09')}
results.update({key: 'PASS' for key in ('C04', 'C05', 'E02', 'S01', 'Q02', 'Q04',
                                      'Q06', 'Q07', 'Q10')})
path = DOC / 'GLI05_ACCEPTANCE.md'
lines = path.read_text(encoding='utf8').splitlines()
for i, line in enumerate(lines):
    if line.startswith('状态：'):
        lines[i] = '状态：R1独审REWORK，R2同项实施中。下表是最近已验证R1结果，R2不得自验冒称独审PASS。判据仍v1；证据见evidence/2026-10-04_gl_i05_r1/09_CLOSEOUT.md。'
    if line.startswith('| '):
        cells = line.split('|')
        key = cells[1].strip()
        if key in results:
            cells[-2] = ' ' + results[key] + '（R1独审） '
            lines[i] = '|'.join(cells)
path.write_text('\n'.join(lines) + '\n', encoding='utf8')
path = DOC / 'GLI05_TASK.md'
lines = path.read_text(encoding='utf8').splitlines()
lines[2] = '状态：R1独审REWORK；用户2026-10-04继续开发授权同项R2。Codex唯一研究writer，OpenCode二审已停写。仅新2026-10-04_gl_i05_r2研究目录；判据v1/冻结/物理边界保持。'
path.write_text('\n'.join(lines) + '\n', encoding='utf8')
for name in ('returns/GL-I05.md', 'REVIEW_LOG.md', 'CLI_RECOVERY.md'):
    with (DOC / name).open('a', encoding='utf8') as f:
        f.write('\n\n2026-10-04 Codex接回GL-I05 R1：fresh probe14.718秒exit0，指定Go Flash/defaultDB二审987.890秒exit0/stop，session ses_efd6ab110ffeW3TtBoZU04eyAW。C01/C02/C03/C06/E01 FAIL，C04/C05/E02/S01 PASS；Q01/Q03/Q05/Q08/Q09 FAIL，其余Q PASS；B01/B02 BLOCKED，D01/D02 NOT_RUN，未ACCEPTED。收口evidence/2026-10-04_gl_i05_r1/09_CLOSEOUT.md。用户继续授权同项R2，Codex唯一研究writer，只新2026-10-04_gl_i05_r2，旧提交/生产/输入/旧证据只读。\n')
