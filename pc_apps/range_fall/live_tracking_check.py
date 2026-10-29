"""Existing sessions -> ROS1 driver bytes -> live engine -> sealed frame comparison."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

import numpy as np

from live_engine import LiveEngine
from live_replay_check import driver_message,ROOT
from core.range_image import ScanGrid
from core.capture_input import ROW_DTYPE
from core.range_contract import load_ground


def wire_message(msg):
    import struct
    def text(value):
        raw=value.encode();return struct.pack('<I',len(raw))+raw
    h=msg.header
    fields=b''.join(text(f.name)+struct.pack('<IBI',f.offset,f.datatype,f.count) for f in msg.fields)
    return (struct.pack('<III',h.seq,h.stamp.secs,h.stamp.nsecs)+text(h.frame_id)
        +struct.pack('<III',msg.height,msg.width,len(msg.fields))+fields
        +struct.pack('<?III',msg.is_bigendian,msg.point_step,msg.row_step,len(msg.data))+msg.data+b'\x00')


def run(session,reference,ground,out):
    session,reference,out=Path(session),Path(reference),Path(out)
    for protected in (ROOT/'data',ROOT/'captures'):
        if protected.resolve() in out.resolve().parents:raise ValueError('output must be outside data')
    meta=json.loads((session/'meta.json').read_text('utf8'));doc=json.loads(reference.read_text('utf8'))
    from analysis import AnalysisStore,sha_file
    import live_engine
    sources=[Path(__file__),Path(live_engine.__file__),ROOT/'pc_apps/annotator_v2/body_branches.py',
             ROOT/'pc_apps/range_fall/depth.py',*sorted((ROOT/'src/human_fall_detection/core').rglob('*.py'))]
    pinned={str(p.relative_to(ROOT)):sha_file(p) for p in sources}
    AnalysisStore.validate(doc)
    if sha_file(session/'meta.json')!=doc['metaSha256'] or sha_file(session/'points.bin')!=doc['pointsSha256']:
        raise ValueError('reference source mismatch')
    tables=ROOT/'src/inno_lidar_ros/config/ifw192s'
    grid=ScanGrid.from_csv(tables/'ifw192s_azimuth_192x256.csv',tables/'ifw192s_elevation_192x256.csv')
    identity=doc['sourceBinding'];plane=load_ground(ground,identity) if ground else None
    engine=LiveEngine(grid,meta['sensor']['frame_id'],identity,empty_prefix_frames=50,ground=plane,body=True)
    expected={r['frameIndex']:r for r in doc['frames']};differences=[];active=[];processed=0
    out.mkdir(parents=True,exist_ok=False)
    with (session/'points.bin').open('rb') as stream,(out/'frames.jsonl').open('x',encoding='utf8') as ledger:
        for index,info in enumerate(meta['frames']):
            stream.seek(info['offset_points']*28);raw=stream.read(info['count_points']*28)
            wire=wire_message(driver_message(np.frombuffer(raw,ROW_DTYPE),info,meta['sensor']['frame_id']))
            state=engine.process(wire);row=expected[index];bundle=state.get('local_range') or {}
            changed=[]
            for key,actual in [('sourceRows',state['target_source_rows']),('trackId',state['track_id']),
                               ('heightMedianM',bundle.get('heightMedianM')),('state',state['fall_status'])]:
                if row[key]!=actual:changed.append(key)
            if bundle.get('depth',{}).get('previewSha256')!=row['depth']['preview']['sha256']:changed.append('previewSHA')
            alert=bundle.get('groundAlert',{})
            if alert.get('active')!=row['groundAlert']['active'] or alert.get('triggerFrame')!=row['groundAlert']['triggerFrame']:
                changed.append('causalGroundAlert')
            actual_body={p['part']:p['sourceRows'] for p in (bundle.get('bodyCandidates') or {}).get('parts',[])}
            expected_body={p['part']:p['sourceRows'] for p in row['bodyCandidates']['parts']}
            if actual_body!=expected_body:changed.append('bodySourceRows')
            if changed:differences.append(dict(frame=index,fields=changed,reason=state['acquisition']['reason']))
            if alert.get('active'):active.append(index)
            processed+=bool(bundle)
            ledger.write(json.dumps(dict(frame=index,source=state.get('source'),targetCount=len(state['target_source_rows']),
                targetRowsSha256=hashlib.sha256(json.dumps(state['target_source_rows']).encode()).hexdigest(),
                heightMedianM=bundle.get('heightMedianM'),fallState=state['fall_status'],
                groundAlert=alert,groundAlertCandidate=bundle.get('groundAlertCandidate'),posture=bundle.get('posture'),
                bodyCounts={k:len(v) for k,v in actual_body.items()},performance=state.get('performance'),differences=changed))+'\n')
    summary=dict(frames=len(meta['frames']),processed=processed,differences=differences,activeFrames=active,
        scope='offline recorded input repackaged as ROS1 messages; not a real live device or human GT test',
        source=dict(meta=doc['metaSha256'],points=doc['pointsSha256']),sourceSha256=pinned,
        referenceSha256=sha_file(reference),semantic='UNKNOWN',confirmedEnabled=False)
    if any(sha_file(ROOT/name)!=sha for name,sha in pinned.items()):raise ValueError('source changed during live replay check')
    (out/'SUMMARY.json').write_text(json.dumps(summary,indent=2),'utf8');print(json.dumps({k:v for k,v in summary.items() if k!='activeFrames'}))
    if differences:raise AssertionError('live/offline differences')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--session',type=Path,required=True);p.add_argument('--reference',type=Path,required=True)
    p.add_argument('--ground',type=Path);p.add_argument('--out',type=Path,required=True);a=p.parse_args();run(a.session,a.reference,a.ground,a.out)
