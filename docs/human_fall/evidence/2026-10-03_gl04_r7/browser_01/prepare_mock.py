from pathlib import Path
out=Path(__file__).parent
src=out.parent.parent/'2026-10-03_gl04_r6/browser_01/codex_mock_bridge_r6.js'
s=src.read_text(encoding='utf-8')
s=s.replace("  if(mode==='bad_source_unavailable')state.position_source_from='unavailable';", "  if(mode==='bad_source_unavailable')state.position_source_from='unavailable';\n  if(mode==='bad_source_predicted')state.position_source_from='predicted';\n  if(mode==='bbox_negative_actual'){state.bbox_observed=false;state.position_source_from='actual_points';}")
p=out/'codex_mock_bridge_r7.js'
if p.exists():raise SystemExit('No overwrite')
p.write_text(s,encoding='utf-8')
