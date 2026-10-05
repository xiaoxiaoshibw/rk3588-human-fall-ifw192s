import pathlib
out=pathlib.Path(__file__).parent
repo=out.parents[4]
src=out.parent.parent/'2026-10-03_gl04_r5'
names=['codex_runtime_harness.js','codex_full_review.js','92_codex_consumers.js','95_codex_source_fall_gate.js','97_codex_additional.js']
for name in names:
    dest=out/name
    if dest.exists(): raise SystemExit('Independent evidence exists: '+str(dest))
    s=(src/name).read_text(encoding='utf-8')
    s=s.replace("path.resolve(__dirname, '../../../..')","path.resolve(__dirname, '../../../../..')")
    s=s.replace("path.resolve(__dirname, '../../../../webui/","path.resolve(__dirname, '../../../../../webui/")
    dest.write_text(s,encoding='utf-8')
print('copied five existing independent checks; only depth adjusted; assertions unchanged')
