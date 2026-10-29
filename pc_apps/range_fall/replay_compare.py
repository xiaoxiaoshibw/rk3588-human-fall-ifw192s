"""同款离线展示：只消费已保存结果或已审计W2，不拟合、不更新算法。"""
import argparse
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import html
import json
import math
from pathlib import Path
import re
import sys

import numpy as np

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
for p in (HERE,ROOT/'tools',ROOT/'src/human_fall_detection'):
    sys.path.insert(0,str(p))
import session_compare as sc
import range_experiment as experiment
from sync_audit import file_binding, digest, read_json, FILES

CAMERA_MAX_DELTA_S=0.20  # 画面显示预算，不是物理同步验收门。
STATES={'unknown','upright','descending','low_posture_unclassified','suspected','recovering'}


def require(condition,message):
    if not condition:raise ValueError(message)
def records(path):
    with path.open(encoding='utf-8') as f:return [json.loads(line) for line in f if line.strip()]
def pin(paths):return {str(p.resolve()):file_binding(p) for p in paths}
def verify(bindings):
    require(bindings=={p:file_binding(Path(p)) for p in bindings},'input or source changed during display export')
def js_records(path):
    raw=path.read_text(encoding='utf-8').strip()
    require(raw.startswith('window.FRAMES=') and raw.endswith(';'),'unsupported saved display data')
    return json.loads(raw[len('window.FRAMES='):-1])
def current_sources():
    return [Path(__file__),HERE/'replay_template.html',HERE/'session_compare.py',
            ROOT/'tools/range_experiment.py',ROOT/'tools/sync_audit.py',
            *sorted((ROOT/'src/human_fall_detection/core').glob('*.py')),
            sc.CALIBRATION/'ifw192s_azimuth_192x256.csv',sc.CALIBRATION/'ifw192s_elevation_192x256.csv']


def validate_display(rows):
    require(bool(rows),'empty display')
    for i,r in enumerate(rows):
        require(r['i']==i and type(r['t']) in (int,float) and math.isfinite(r['t']),'invalid display frame/time')
        require(r['st'] in STATES,'unsupported or confirmed display state')
        require(type(r['n']) is int and r['n']>=0,'invalid measured count')
        for key in ('hm','ht','sp','rt','vt'):
            require(r[key] is None or (type(r[key]) in (int,float) and math.isfinite(r[key])),'invalid display metric')
        for key in ('bg','tg'):
            require(len(r[key])%3==0 and all(type(v) is int for v in r[key]),'invalid quantized display points')
        require(len(r['bg'])<=3*sc.SCENE_DISPLAY_POINTS and len(r['tg'])<=3*sc.TARGET_DISPLAY_POINTS,'display cap exceeded')
        if not r['n']:
            require(not r['tg'] and r['bb'] is None and r['tid'] is None,'unmeasured frame has target geometry')
            require(all(r[k] is None for k in ('hm','ht','sp','rt','vt','c')),'unmeasured features are not unknown')
        else:
            require(bool(r['tid']) and r['bb'] is not None and len(r['bb'])==6,'missing measured target box')
            require(len(r['tg'])//3<=r['n'],'display sampling increased measurement count')
        if r['bb'] is not None:
            require(all(type(v) is int for v in r['bb']) and all(r['bb'][k]<=r['bb'][k+3] for k in range(3)),'invalid box')


def camera_link(camera,stamp):
    if camera is None or not camera[0] or type(stamp) not in (int,float) or not math.isfinite(stamp):return None
    target_ns=int(Decimal(str(stamp))*Decimal(10**9))
    i=min(range(len(camera[0])),key=lambda j:(abs(camera[0][j]['recv_unix_ns']-target_ns),j))
    return [i,(camera[0][i]['recv_unix_ns']-target_ns)/1e9]


def saved_view(folder,identity):
    summary=read_json(folder/'SUMMARY.json')
    require(summary.get('schema')=='session_compare_v1','unsupported saved view schema')
    require(summary['source_binding']==identity,'saved view source/calibration binding mismatch')
    require(summary['honesty']['non_causal_background'] is True,'saved mode only accepts declared historical display')
    require(not summary['fall']['confirmed_enabled'] and not summary['fall']['events'],'saved confirmed/event output forbidden')
    frozen=folder/'CHECKS.json'
    if frozen.exists():
        manifest=read_json(frozen).get('artifacts',{})
        require({'SUMMARY.json','GROUND.json','FRAMES.jsonl','data/frames.js'}<=set(manifest),'incomplete saved artifact manifest')
        for name,expected in manifest.items():
            path=(folder/name).resolve()
            require(folder in path.parents and file_binding(path)==expected,'saved artifact SHA mismatch: '+name)
        summary['saved_evidence_status']='FROZEN_BYTES_MATCH'
    else:summary['saved_evidence_status']='UNVERIFIED_NO_FROZEN_MANIFEST'
    summary['saved_algorithm_status']='HISTORICAL_NOT_REEXECUTED'
    rows=js_records(folder/'data/frames.js'); ledger=records(folder/'FRAMES.jsonl')
    require(len(rows)==summary['source']['frames'],'saved frame count mismatch')
    require([{k:v for k,v in row.items() if k not in ('bg','tg')} for row in rows]==ledger,'saved display/ledger mismatch')
    ground=read_json(folder/'GROUND.json')
    require(ground==summary['ground'] and ground['binding']==identity,'saved ground binding mismatch')
    return summary,rows,ground


def audited_view(session,replay,audit,identity,meta,grid,ground_path):
    report=read_json(audit/'SUMMARY.json'); content=dict(report); claimed=content.pop('content_sha256',None)
    require(claimed==digest(content) and report['status']=='SOFTWARE_AUDITED','audit content invalid or STALE')
    require(report['source_binding']==identity,'audit source/calibration binding mismatch')
    w2,files,changed=experiment.replay_bindings(replay,report['binding']['source'])
    require(not changed and report['binding']['replay']==files,'replay source changed or audit binding mismatch')
    require(report['binding']['mode']=='replay_and_rules' and report['binding']['frame_range']==[0,w2['frames']],'audit scope mismatch')
    require(report['rule_baseline']['executed'] and not report['rule_baseline']['confirmed_enabled'],'rule audit unavailable')
    require(report['input_replay_inference_sha256']==w2['inference_output_sha256'],'audit inference mismatch')
    for path,expected in report['binding']['audit_sources'].items():
        require(file_binding(ROOT/path)==expected,'audit source changed: '+path)
    # 完整清单必须包含当前审计工具及全部core；不能通过删键逃避源码漂移检查。
    required={p.relative_to(ROOT).as_posix() for p in experiment.ROOT.joinpath('src/human_fall_detection/core').glob('*.py')}
    required.update(['tools/range_experiment.py','tools/sync_audit.py'])
    provided={p.replace('\\','/') for p in report['binding']['audit_sources']}
    require(required<=provided,'incomplete audit source manifest')
    for key,name in [('source_rows_sha256','SOURCE_ROWS.jsonl'),('rule_baseline_sha256','RULE_BASELINE.jsonl')]:
        require(file_binding(audit/name)['sha256']==report[key],'audit ledger SHA mismatch')
    for key,name in [('meta.json','meta.json'),('points.bin','points.bin'),('joint.json','joint.json'),
                     ('camera_frames.jsonl','camera_frames.jsonl'),('camera.mjpeg','camera.mjpeg')]:
        require(file_binding(session/name)==report['binding']['source'][key],'audit raw source changed: '+key)
    ground_sha=file_binding(ground_path)['sha256'] if ground_path else None
    require(ground_sha==w2['settings'].get('ground_sha256')==report['binding']['ground_sha256'],'ground must match audit and replay')
    ground=experiment.load_ground(ground_path,identity) if ground_path else None
    for path,expected in report['binding']['ground_files'].items():require(file_binding(Path(path))==expected,'ground/provenance changed')
    tracks=records(replay/'frames.jsonl'); rules=records(audit/'RULE_BASELINE.jsonl'); source=records(audit/'SOURCE_ROWS.jsonl')
    require(len(tracks)==len(rules)==len(source)==w2['frames']==report['frames_processed'],'audit frame count mismatch')
    basis=sc.display_basis(ground['normal']) if ground else np.eye(3)
    offset=ground['offset_m'] if ground else 0.0
    rows=[]; inference=hashlib.sha256()
    with (session/'points.bin').open('rb') as stream:
        for i,(t,r,s) in enumerate(zip(tracks,rules,source)):
            info=meta['frames'][i]; raw=stream.read(info['count_points']*sc.ROW_DTYPE.itemsize)
            raw_sha=hashlib.sha256(raw).hexdigest()
            pure=experiment.inference_serial(t)
            inference.update(pure.encode())
            require(t['frame']==r['frame']==s['frame']==i and r['time_s']==t['time_s'],'frame/time mismatch')
            require(r['input_inference_sha256']==t['inference_sha256'] and r['source_rows']==t['target_source_rows'],'rule target/inference mismatch')
            require(raw_sha==t['raw_sha256']==s['raw_sha256'] and info['offset_points']==t['offset_points']==s['offset_points'],'raw frame binding mismatch')
            require(not r['state']['confirmed_enabled'] and r['state']['new_event'] is None,'confirmed event forbidden')
            chosen=t['target_source_rows']; target=next((v for v in t['tracks'] if v['track_id']==t['target_track_id']),None)
            require((not chosen and target is None) or (chosen and target and target['observed'] is True and target['position_predicted'] is False and target['status']=='tracked' and target['source_rows']==chosen),'target is not measured stable track')
            frame=grid.decode(raw,experiment.binding_tuple(identity))
            require(len(chosen)==len(set(chosen)) and set(chosen)<=set(frame.source_rows[frame.valid].tolist()),'foreign/repeated target rows')
            points=frame.xyz[chosen].astype(float) if chosen else np.empty((0,3))
            display=sc.to_display(points,basis,offset); features=r['features']; heights=features.get('height_m') or {}
            record=dict(i=i,t=t['time_s'],st=r['state']['state'],rs=r['state'].get('reason_codes') or [],
                tid=t['target_track_id'],n=len(chosen),hm=features.get('height_median_m'),ht=heights.get('max'),
                sp=features.get('horizontal_extent_m'),rt=features.get('descent_rate_m_s'),vt=features.get('axis_verticality'),
                bb=sc.quantize(np.stack([display.min(axis=0),display.max(axis=0)])) if chosen else None,
                c=sc.quantize(np.median(display,axis=0)[:2]) if chosen else None,cam=None,bl=None,
                bg=sc.quantize(sc.voxel_pick(sc.to_display(frame.xyz[frame.source_rows[frame.valid]],basis,offset),sc.SCENE_VOXEL_M,sc.SCENE_DISPLAY_POINTS,'scene:%d'%i)),
                tg=sc.quantize(sc.voxel_pick(display,sc.TARGET_VOXEL_M,sc.TARGET_DISPLAY_POINTS,'target:%d'%i)),
                generation=t['generation'],reset_reason=t['reset_reason'],target_reason=t['target_reason'],
                inference_sha256=t['inference_sha256'],target_rows_sha256=digest(chosen))
            rows.append(record)
    require(inference.hexdigest()==w2['inference_output_sha256'],'aggregate inference mismatch')
    return rows,ground,report,w2


def render_html(summary):
    badges=[summary['presentation_mode'],
        '背景非因果' if summary['honesty']['non_causal_background'] else '显式空场前缀 · 因果W2',
        '人体/跌倒真值 UNKNOWN','物理同步 UNKNOWN · confirmed关闭']
    values=dict(TITLE=html.escape(summary['title']),SUBTITLE=html.escape(sc._subtitle(summary)),
        BADGES=''.join('<span class="badge warn">%s</span>'%html.escape(v) for v in badges),
        VERDICT=html.escape(summary['verdict']),NOTES=''.join('<div class="note">%s</div>'%html.escape(v) for v in summary['presentation_notes']),
        MAX_INDEX=str(summary['source']['frames']-1),VIEW=json.dumps(summary['display']['view'],allow_nan=False),
        SENSOR_ORIGIN=json.dumps(summary['display']['sensor_origin_cm']),REPRODUCE=html.escape(summary['reproduce']),
        SUMMARY_JSON=html.escape(json.dumps(summary,ensure_ascii=False,indent=2,allow_nan=False)))
    return re.sub(r'@@([A-Z_]+)@@',lambda m:values[m.group(1)],(HERE/'replay_template.html').read_text(encoding='utf-8'))


def drawable_segment(screen):
    p=np.asarray(screen,dtype=float)
    return bool(np.isfinite(p).all() and (p[:,2]>.25).all() and (np.abs(p[:,:2])<=1e6).all())


def render_preview(rows,path,summary):
    """由同一显示数据绘制点云/相机预览；投影非有限时禁止送入光栅器。"""
    try:
        from PIL import Image,ImageDraw,ImageFont
    except ImportError:return None  # PC可选预览；HTML/账本不依赖Pillow。
    r=next((r for r in rows if r['st']=='suspected' and r['n']),next((r for r in rows if r['n']),rows[0]))
    sheet=Image.new('RGB',(1440,650),(10,13,18)); painter=ImageDraw.Draw(sheet)
    font_path=Path('C:/Windows/Fonts/msyh.ttc')
    font=ImageFont.truetype(str(font_path),18) if font_path.exists() else ImageFont.load_default()
    painter.text((18,10),'OFFLINE DATA PREVIEW | '+summary['session']+' | frame %d, %.3fs'%(r['i'],r['t']),font=font,fill='#e8eef7')
    panel=Image.new('RGB',(880,540),(7,10,15)); draw=ImageDraw.Draw(panel)
    v=summary['display']['view']; center=np.array([v['tx'],v['ty'],v['tz']]);
    eye=center+v['dist']*np.array([math.cos(v['pitch'])*math.cos(v['yaw']),math.cos(v['pitch'])*math.sin(v['yaw']),math.sin(v['pitch'])])
    forward=center-eye;forward/=np.linalg.norm(forward);right=np.cross(forward,[0,0,1]);right/=np.linalg.norm(right);up=np.cross(right,forward)
    def project(points):return sc._project(points,eye,right,up,forward,510,440,270)
    def line(points,colour,width=1):
        p=project(points)
        if drawable_segment(p):draw.line([tuple(p[0,:2]),tuple(p[1,:2])],fill=colour,width=width)
    for x in np.arange(-1,6.01,.5):line([[x,-4,0],[x,4,0]],(38,50,66))
    for y in np.arange(-4,4.01,.5):line([[-1,y,0],[6,y,0]],(38,50,66))
    for key,colour,size in [('bg',(54,66,84),2),('tg',(53,255,122),3)]:
        p=project(np.asarray(r[key],dtype=float).reshape(-1,3)/100)
        for a in p[np.argsort(-p[:,2])]:
            if np.isfinite(a).all() and a[2]>.25 and 0<=a[0]<880 and 0<=a[1]<540:
                draw.rectangle([a[0],a[1],a[0]+size,a[1]+size],fill=colour)
    if r['bb']:
        a,b,c,d,e,f=np.asarray(r['bb'])/100
        corners=[[a,b,c],[d,b,c],[d,e,c],[a,e,c],[a,b,f],[d,b,f],[d,e,f],[a,e,f]]
        for i,j in [(0,1),(1,2),(2,3),(3,0),(4,5),(5,6),(6,7),(7,4),(0,4),(1,5),(2,6),(3,7)]:line([corners[i],corners[j]],(53,255,122),2)
    sheet.paste(panel,(16,50))
    if r['cam_status']=='nearby':
        camera=path.parent/'camera'/('c%03d.jpg'%r['cam'][0])
        with Image.open(camera) as source:
            picture=source.convert('RGB');picture.thumbnail((512,384));sheet.paste(picture,(912,50))
    painter.text((912,445),'state: '+r['st']+' | measured n=%d'%r['n'],font=font,fill='#ffb84d')
    painter.text((912,480),'height: '+('UNKNOWN' if r['hm'] is None else '%.3f m'%r['hm']),font=font,fill='#e8eef7')
    painter.text((912,515),'camera: '+r['cam_status']+' | sync UNKNOWN',font=font,fill='#93a1b5')
    painter.text((18,608),'Same display data; not a browser screenshot. GT UNKNOWN; confirmed disabled.',font=font,fill='#93a1b5')
    sheet.save(path);return path


def build(session,out,*,saved=None,replay=None,audit=None,ground=None,preview=True,title=None):
    session=Path(session).resolve(); out=Path(out).resolve()
    saved=Path(saved).resolve() if saved else None; replay=Path(replay).resolve() if replay else None
    audit=Path(audit).resolve() if audit else None; ground=Path(ground).resolve() if ground else None
    require(bool(saved) != bool(replay),'choose exactly one of saved view or audited replay')
    require(bool(audit)==bool(replay) and (not saved or not ground),'audited replay requires audit; saved view needs no ground override')
    for p in (session,ROOT/'data',ROOT/'captures',saved,replay,audit):
        if p is None:continue
        p=p.resolve(); require(not(out==p or p in out.parents or out in p.parents),'output overlaps an input/data path')
    require(not out.exists(),'output already exists')
    paths=current_sources()+[session/name for name in FILES]
    if saved:paths.extend(p for p in saved.rglob('*') if p.is_file())
    if replay:paths.extend(replay/name for name in ('SUMMARY.json','CONFIG.json','frames.jsonl'))
    if audit:paths.extend(audit/name for name in ('SUMMARY.json','SOURCE_ROWS.jsonl','RULE_BASELINE.jsonl','SYNC_AUDIT.json'))
    if ground:
        paths.extend([ground,Path(read_json(ground)['provenance']['source'])])
    bindings=pin(paths)
    meta,meta_sha=sc.session_meta(session); grid=sc.load_grid()
    identity=sc.source_binding(session,meta,meta_sha,file_binding(session/'points.bin')['sha256'],grid)
    identity.update(azimuth_sha256=file_binding(sc.CALIBRATION/'ifw192s_azimuth_192x256.csv')['sha256'],elevation_sha256=file_binding(sc.CALIBRATION/'ifw192s_elevation_192x256.csv')['sha256'])
    require((session/'camera.mjpeg').exists()==(session/'camera_frames.jsonl').exists(),'incomplete camera input pair')
    camera=sc.read_camera(session)
    if saved:
        summary,rows,plane=saved_view(saved,identity)
        require(summary['source']['camera_sha256']==(bindings[str((session/'camera.mjpeg').resolve())] or {}).get('sha256'),'saved camera SHA mismatch')
        require(summary['source']['camera_index_sha256']==(bindings[str((session/'camera_frames.jsonl').resolve())] or {}).get('sha256'),'saved camera index SHA mismatch')
        summary['presentation_mode']='已保存离线样例（未重跑算法）'
        summary['row_provenance']='UNAVAILABLE_IN_LEGACY_DISPLAY; not a W2 audit'
    else:
        rows,plane,report,w2=audited_view(session,replay,audit,identity,meta,grid,ground)
        summary=dict(session=session.name,source=dict(frames=len(rows),camera_frames=len(camera[0]) if camera else 0,
            duration_sec=rows[-1]['t']-rows[0]['t'],meta_sha256=meta_sha,points_sha256=identity['points_sha256']),
            source_binding=identity,ground=plane,foreground=w2['settings'],tracking=dict(selected_tracks=dict(Counter(r['tid'] for r in rows if r['tid'])),frames_with_target=sum(r['n']>0 for r in rows)),
            fall=dict(states=dict(Counter(r['st'] for r in rows)),confirmed_enabled=False,events=[]),
            honesty=dict(non_causal_background=False,human_gt='UNKNOWN',fall_gt='UNKNOWN',physical_verified=False,runtime_eligible=False,deployed=False),
            presentation_mode='已审计因果W2回放',row_provenance='current measured source rows verified',
            input_inference_sha256=w2['inference_output_sha256'],input_audit_content_sha256=report['content_sha256'])
    validate_display(rows)
    for r in rows:
        r['cam']=camera_link(camera,meta['frames'][r['i']].get('bag_time_sec'))
        r['cam_status']='missing' if r['cam'] is None else ('nearby' if abs(r['cam'][1])<=CAMERA_MAX_DELTA_S else 'stale')
    target=[r for r in rows if r['n']]; alarms=[r['i'] for r in rows if r['st']=='suspected' and r['n']]
    centres=np.asarray([r['c'] for r in target])/100 if target else np.empty((0,2))
    summary['schema']='range_compare_view_v1'; summary['title']=title or '点云绿框与相机 · '+session.name
    summary['generated_utc']=datetime.now(timezone.utc).isoformat()
    summary['camera_pairing']=dict(method='nearest receipt vs stored bag wall clock; preview only',hardware_sync=False,extrinsics=None,
        physical_sync='UNKNOWN',display_max_delta_s=CAMERA_MAX_DELTA_S,statuses=dict(Counter(r['cam_status'] for r in rows)))
    summary['display']=dict(view=dict(yaw=-1.08,pitch=.42,dist=4.8,tx=float(np.median(centres[:,0])) if target else 2.0,
        ty=float(np.median(centres[:,1])) if target else 0.0,tz=.9),sensor_origin_cm=[0,0,int(round(100*plane['offset_m'])) if plane else 0],
        coordinate='ground-aligned display' if plane else 'RAW; reference grid is not a physical floor',sampling='display only; algorithms unchanged')
    summary['verdict']='实测目标绿框 %d/%d 帧；%s'%(len(target),len(rows),
        ('首个跌倒嫌疑 %.2f s，共%d个实测帧'%(rows[alarms[0]]['t'],len(alarms))) if alarms else '本段无实测跌倒候选（不代表效果通过）')
    summary['presentation_notes']=[
        '绿框仅来自当前实测目标；失锁/预测/歧义时不延续绿框或高度。显示抽样不进入算法，框使用全部目标测量。',
        '历史样例使用既有整段p98背景，非因果；本轮只重绘已保存结果。' if saved else '直接展示已绑定的因果W2与规则账本；本轮不重算背景、跟踪、规则或拟合。',
        '使用已有绑定地面，物理资格UNKNOWN。' if plane else '地面不可用，高度UNKNOWN；网格为RAW参考面。',
        '相机按接收近邻展示，0.20s仅为画面预算；超时/加载失败隐藏。无物理同步/外参，不投影点云。',
        '人体/身份/真实跌倒/浴室效果UNKNOWN；confirmed关闭，疑似不是确认。']
    summary['reproduce']='python -B -W error pc_apps/range_fall/replay_compare.py --session '+str(session)+' '+(
        '--saved-view '+str(saved) if saved else '--replay-run '+str(replay)+' --audit-run '+str(audit)+(' --ground '+str(ground) if ground else ''))+' --out <new_directory>'
    summary['input_and_source_bindings']=bindings
    verify(bindings)
    out.mkdir(parents=True,exist_ok=False); (out/'data').mkdir(); (out/'camera').mkdir()
    for i in sorted({r['cam'][0] for r in rows if r['cam_status']=='nearby'}):
        info=camera[0][i]; (out/'camera'/('c%03d.jpg'%i)).write_bytes(camera[1][info['offset']:info['offset']+info['length']])
    (out/'data/frames.js').write_text('window.FRAMES='+json.dumps(rows,ensure_ascii=False,separators=(',',':'),allow_nan=False)+';\n',encoding='utf-8')
    with (out/'FRAMES.jsonl').open('x',encoding='utf-8') as f:
        for r in rows:f.write(json.dumps({k:v for k,v in r.items() if k not in ('bg','tg')},sort_keys=True,allow_nan=False)+'\n')
    (out/'index.html').write_text(render_html(summary),encoding='utf-8')
    if preview:render_preview(rows,out/'PREVIEW.png',summary)
    verify(bindings)
    summary['outputs']={p.relative_to(out).as_posix():file_binding(p) for p in out.rglob('*') if p.is_file()}
    summary['content_sha256']=digest(summary)
    with (out/'SUMMARY.json').open('x',encoding='utf-8') as f:json.dump(summary,f,ensure_ascii=False,indent=2,allow_nan=False)
    return summary


def main():
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('--session',required=True,type=Path);p.add_argument('--out',required=True,type=Path)
    mode=p.add_mutually_exclusive_group(required=True);mode.add_argument('--saved-view',type=Path);mode.add_argument('--replay-run',type=Path)
    p.add_argument('--audit-run',type=Path);p.add_argument('--ground',type=Path);p.add_argument('--title');p.add_argument('--no-preview',action='store_true')
    a=p.parse_args(); s=build(a.session,a.out,saved=a.saved_view,replay=a.replay_run,audit=a.audit_run,ground=a.ground,preview=not a.no_preview,title=a.title)
    print(json.dumps(dict(output=str(a.out),mode=s['presentation_mode'],frames=s['source']['frames']),ensure_ascii=False))


if __name__=='__main__':main()
