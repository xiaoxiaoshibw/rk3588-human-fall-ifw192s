from pathlib import Path
out=Path(__file__).parent
src=out.parent.parent/'2026-10-03_gl04_r6/codex_review_01/98_codex_lifecycle.js'
s=src.read_text(encoding='utf-8')
s=s.replace("assert.strictEqual(o.target_visible,false,'inactive/non-occluded target cannot reappear through prediction diagnostic');","assert.strictEqual(o.position,'--');assert.strictEqual(o.fall,'unknown');if(o.target_visible)assert.strictEqual(o.target_color,'6b7a90');")
s=s.replace("assert.strictEqual(o.target_visible,false,'stale prediction cannot remain a current diagnostic box');","assert.strictEqual(o.position,'--');assert.strictEqual(o.fall,'unknown');if(o.target_visible)assert.strictEqual(o.target_color,'6b7a90');")
s=s.replace('is not a valid occluded prediction','keeps any diagnostic non-physical and non-current').replace('cannot redraw retained bbox','keeps any retained diagnostic non-physical')
s=s.replace('98_codex_lifecycle_results.json','98_codex_provenance_results.json')
p=out/'98_codex_provenance.js'
if p.exists():raise SystemExit('No overwrite')
p.write_text(s,encoding='utf-8')
print('source provenance assertions unchanged; diagnostic expectations corrected per R6 adjudication')
