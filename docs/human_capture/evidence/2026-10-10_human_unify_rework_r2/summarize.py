from pathlib import Path
import json,hashlib
base=Path('docs/human_capture/evidence/2026-10-10_human_unify_rework_r2')
summary=[];issues=[];frames=0
for d in sorted((base/'runs_01').iterdir()):
 m=json.loads((d/'manifest.json').read_text(encoding='utf-8-sig'))
 for e in m['sessions']:
  file=d/e['file'];j=json.loads(file.read_text(encoding='utf-8-sig'))
  if hashlib.sha256(file.read_bytes()).hexdigest()!=e['sha256']:issues.append(str(file))
  if hashlib.sha256((d/e['csv']).read_bytes()).hexdigest()!=e['csv_sha256']:issues.append(e['csv'])
  for p,h in j['run_meta']['source_sha256'].items():
   if hashlib.sha256(Path(p).read_bytes()).hexdigest()!=h:issues.append(p)
  summary.append({'sid':d.name,'mode':e['mode'],'gt':j['prf']['level'],**j['session_summary']})
  frames+=j['session_summary']['n_frames']
assert not issues,issues
(base/'matrix_summary.json').write_text(json.dumps({'runs':len(summary),'frame_evaluations':frames,'hash_issues':issues,'summary':summary},ensure_ascii=False,indent=2),encoding='utf-8')
lines=['# 本轮45次运行实测结果','', 'accepted/rejected仅为分类器接受/拒绝候选；不代表真人/家具身份。current是会话末帧当前确认；ever是历史曾确认的track身份数，不是人数。','', '| sid | mode | accepted帧 | rejected帧 | 当前确认track | 曾确认track | ms/f | GT来源 |','|---|---|---|---|---|---|---|---|']
for s in summary:lines.append('| {sid} | {mode} | {frames_with_accepted_cand} | {frames_with_rejected_cand} | {n_tracks_confirmed_current} | {n_tracks_ever_confirmed} | {mean_ms_per_frame} | {gt} |'.format(**s))
(base/'AB_RESULTS.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
print('runs',len(summary),'frames',frames,'hash issues',len(issues))
