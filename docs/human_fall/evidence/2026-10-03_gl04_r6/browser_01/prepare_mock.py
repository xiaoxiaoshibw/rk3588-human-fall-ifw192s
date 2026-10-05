from pathlib import Path
out=Path(__file__).parent
out.mkdir(exist_ok=True)
src=out.parent.parent/'2026-10-02_gl04_r2'/'codex_mock_bridge_v2.js'
s=src.read_text(encoding='utf-8').replace('../../../../webui/human_fall_preview/human_fall_lib.js','../../../../../webui/human_fall_preview/human_fall_lib.js').replace('8881','18091')
insert="""  if(mode==='bad_source_unavailable')state.position_source_from='unavailable';
  if(mode==='pending')state.baseline={status:'pending',request_id:'mock-baseline-1'};
  if(mode==='baseline_failed')state.baseline={status:'failed',reason:'synthetic_stream_unavailable',request_id:'mock-baseline-1'};
"""
s=s.replace('  return {snap,state};',insert+'  return {snap,state};')
p=out/'codex_mock_bridge_r6.js'
if p.exists():raise SystemExit('No overwriting mock evidence')
p.write_text(s,encoding='utf-8')
