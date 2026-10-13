from pathlib import Path
import json,hashlib
base=Path('docs/human_capture/evidence/2026-10-10_human_unify_rework_r2');summary=[];frames=0
for d in sorted((base/'runs_03').iterdir()):
 if not (d/'manifest.json').exists():raise SystemExit('WAIT: matrix not complete')
 m=json.loads((d/'manifest.json').read_text(encoding='utf-8-sig'))
 assert len(m['sessions'])==5
 for e in m['sessions']:
  file=d/e['file'];j=json.loads(file.read_text(encoding='utf-8-sig'))
  assert hashlib.sha256(file.read_bytes()).hexdigest()==e['sha256']
  assert hashlib.sha256((d/e['csv']).read_bytes()).hexdigest()==e['csv_sha256']
  for p,h in j['run_meta']['source_sha256'].items():assert hashlib.sha256(Path(p).read_bytes()).hexdigest()==h,p
  for name,h in j['run_meta']['input_sha256'].items():assert hashlib.sha256((Path('captures/remote')/d.name/('points.bin' if name=='points' else 'meta.json')).read_bytes()).hexdigest()==h
  summary.append({'sid':d.name,'mode':e['mode'],'gt':j['prf']['level'],**j['session_summary']});frames+=j['session_summary']['n_frames']
assert len(summary)==45
for sid in set(x['sid'] for x in summary):
 a=next(x for x in summary if x['sid']==sid and x['mode']=='BASE_A');u=next(x for x in summary if x['sid']==sid and x['mode']=='U1')
 for key in ['frames_with_accepted_cand','frames_with_rejected_cand','frames_with_confirmed_tracks','n_tracks_total','n_tracks_confirmed_current','n_tracks_ever_confirmed']:assert a[key]==u[key],(sid,key)
(base/'matrix_summary_03.json').write_text(json.dumps({'runs':45,'frame_evaluations':frames,'hash_issues':[],'A_U1_equal':True,'summary':summary},ensure_ascii=False,indent=2),encoding='utf-8')
lines=['# 当前依赖45次运行结果','', '本表来源runs_03；完整文件、CSV、输入及当前实现SHA复算通过。accepted/rejected不是真人/家具身份；current与ever均为track数，不是人数。','', '| sid | mode | accepted帧 | rejected帧 | 当前确认track | 曾确认track | ms/f | GT来源 |','|---|---|---|---|---|---|---|---|']
for s in summary:lines.append('| {sid} | {mode} | {frames_with_accepted_cand} | {frames_with_rejected_cand} | {n_tracks_confirmed_current} | {n_tracks_ever_confirmed} | {mean_ms_per_frame} | {gt} |'.format(**s))
(base/'AB_RESULTS_CURRENT.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
print('CURRENT PASS:45 runs',frames,'frame evaluations,A=U1,all source/input/JSON/CSV SHA matched')
