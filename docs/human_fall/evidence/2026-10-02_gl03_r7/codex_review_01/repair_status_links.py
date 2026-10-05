from pathlib import Path
ROOT=Path(__file__).resolve().parents[5]
for name in ('returns/GL-03.md','REVIEW_LOG.md','CLI_RECOVERY.md'):
    path=ROOT/'docs/human_fall'/name
    text=path.read_text(encoding='utf-8')
    if name=='returns/GL-03.md':
        marker='# Codex GL03 R7 独立复审 /'
        before,after=text.split(marker,1)
        after=after.replace('](evidence/2026-10-02_gl03_r7/codex_review_01/CODEX_REVIEW.md)',
                            '](../evidence/2026-10-02_gl03_r7/codex_review_01/CODEX_REVIEW.md)')
        text=before+marker+after
    with path.open('w',encoding='utf-8',newline='') as f:
        f.write(text.rstrip()+'\n')
