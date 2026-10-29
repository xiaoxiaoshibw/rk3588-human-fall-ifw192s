"""Native application integration on real read-only input and loopback fake devices."""
import base64
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import re
import os
from pathlib import Path
import socketserver
import struct
import subprocess
import threading
import time
import unittest
import uuid

ROOT=Path(__file__).resolve().parents[2]
APP=ROOT/'console_v2'
SDK=APP/'.tools/dotnet/dotnet.exe'
DLL=Path(os.environ.get('FALL_APP_DLL',str(APP/'app/service/bin/Release/net8.0-windows/AppService.dll')))
HOST=Path(os.environ.get('FALL_APP_HOST',str(APP/'app/runtime/ConsoleV2.exe')))
SESSION=Path(os.environ.get('FALL_SESSION',str(ROOT/'data/sessions/cap_20261018_110029')))
ANALYSIS=Path(os.environ.get('FALL_ANALYSIS',str(ROOT/'docs/evidence/2026-10-25_fall_integration/analysis386.json')))


def text(s):
    b=s.encode();return struct.pack('<I',len(b))+b


def ws_frame(op,payload):
    n=len(payload)
    return bytes([128|op])+(bytes([n]) if n<126 else b'\x7e'+struct.pack('>H',n) if n<65536 else b'\x7f'+struct.pack('>Q',n))+payload


def cloud_message(raw,meta,index,seq=77):
    info=meta['frames'][index];frame=meta['sensor']['frame_id']
    header=struct.pack('<III',seq,info['stamp_sec'],info['stamp_nanosec'])+text(frame)
    fields=b''.join(text(name)+struct.pack('<IBI',offset,7,1) for name,offset in [('x',0),('y',4),('z',8),('intensity',12)])
    return header+struct.pack('<III',1,info['count_points'],4)+fields+b'\x00'+struct.pack('<III',28,len(raw),len(raw))+raw+b'\x00'


class TestApp(unittest.TestCase):
    def setUp(self):
        self.out=APP/'.tools/app-evidence'/('test_'+uuid.uuid4().hex)
        self.out.mkdir(parents=True)
        print('NATIVE_TEST_OUTPUT '+str(self.out),flush=True)

    def run_service(self,extra,analysis=ANALYSIS,expect=0):
        args=[str(SDK),str(DLL),'--session',str(SESSION),'--host',str(HOST),'--report',str(self.out/'run.json'),
              '--analysis',str(analysis)]+list(extra)
        result=subprocess.run(args,cwd=ROOT,capture_output=True,timeout=90)
        (self.out/'stdout.txt').write_bytes(result.stdout);(self.out/'stderr.txt').write_bytes(result.stderr)
        self.assertEqual(result.returncode,expect,result.stderr.decode(errors='replace'))
        return json.loads((self.out/'run.json').read_text())

    def test_all_real_frames_zero_tolerance_xyz_target(self):
        report=self.run_service(['--check'])
        doc=json.loads(ANALYSIS.read_text());results={f['frameIndex']:f for f in doc['frames']}
        meta=json.loads((SESSION/'meta.json').read_text())
        decoded=[r['info'] for r in report['log'] if r['eventType']=='decoded']
        self.assertEqual(len(decoded),len(meta['frames']))
        with (SESSION/'points.bin').open('rb') as points:
            for info,fr in zip(decoded,meta['frames']):
                points.seek(fr['offset_points']*28);raw=points.read(fr['count_points']*28)
                xyz=b''.join(raw[i:i+12] for i in range(0,len(raw),28) if all(__import__('math').isfinite(v) for v in struct.unpack_from('<fff',raw,i)))
                expected=results[info['frameIndex']]
                target=b''.join(raw[i*28:i*28+12] for i in expected['sourceRows'])
                intensity=b''.join(raw[i+12:i+16] for i in range(0,len(raw),28) if all(__import__('math').isfinite(v) for v in struct.unpack_from('<fff',raw,i)))
                self.assertEqual(info['rawSha256'],hashlib.sha256(raw).hexdigest())
                self.assertEqual(info['xyzSha256'],hashlib.sha256(xyz).hexdigest())
                self.assertEqual(info['targetSha256'],hashlib.sha256(target).hexdigest())
                self.assertTrue(info['intensityAvailable'])
                self.assertEqual(info['intensitySha256'],hashlib.sha256(intensity).hexdigest())
                self.assertEqual(info['result']['state'],expected['state'])
                if 'depth' in expected:
                    self.assertEqual(info['depth']['previewSha256'],expected['depth']['preview']['sha256'])
                    self.assertEqual(info['result']['posture'],expected['posture'])
        self.assertEqual(report['jointMutationRequests'],0)
        self.assertEqual(report['directBoardCalls'],0)

    def test_native_replay_copy_seek_and_pause(self):
        report=self.run_service(['--smoke','--smoke-depth','--screenshot',str(self.out/'window.png')])
        published=[r for r in report['log'] if r['eventType']=='published']
        # command 记录为原始 JSON 文本（服务端不把 JsonElement 留到报告序列化）
        commands=[json.loads(r['command']) for r in report['log'] if r['eventType']=='command']
        acks=[c for c in commands if c['op']=='ack']
        self.assertEqual(len(published),len(acks))
        self.assertTrue(any(r['info']['frameIndex']==104 for r in published))
        self.assertEqual(published[-1]['info']['frameIndex'],105)
        seek_commands=[c for c in commands if c['op']=='seek']
        self.assertEqual(len(seek_commands),501)
        self.assertTrue(any(ack.get('seekBurstEnqueueMs',-1)>=0 for ack in acks))
        for sent,ack in zip(published,acks):
            self.assertEqual(sent['submissionId'],ack['submissionId'])
            self.assertEqual(sent['info']['xyzSha256'],ack['xyzSha256'])
            self.assertEqual(sent['info']['targetSha256'],ack['targetSha256'])
            self.assertEqual(sent['info']['intensitySha256'],ack['intensitySha256'])
            if sent['info'].get('depth'):
                self.assertEqual(sent['info']['depth']['previewSha256'],ack['depthSha256'])
        self.assertTrue((self.out/'window.png').is_file())
        self.assertEqual(report['jointMutationRequests'],0)

    def test_native_live_and_joint_with_fake_devices(self):
        meta=json.loads((SESSION/'meta.json').read_text());analysis=json.loads(ANALYSIS.read_text())
        chosen=next(f for f in analysis['frames'] if f['frameIndex']==105)
        fr=meta['frames'][105]
        with (SESSION/'points.bin').open('rb') as f:
            f.seek(fr['offset_points']*28);raw=f.read(fr['count_points']*28)
        cloud=cloud_message(raw,meta,105)
        source=dict(seq=77,stamp_secs=fr['stamp_sec'],stamp_nsecs=fr['stamp_nanosec'],frame_id=meta['sensor']['frame_id'])
        state=dict(schema_version=1,kind='target_state',session_id='mock_live',time_epoch=0,selection_version=0,
            source=source,target_mode='automatic',track_id='mock_T1',track_status='locked',observability='valid',
            bbox_observed=True,position_predicted=False,target_source_rows=chosen['sourceRows'],fall_status='unknown')
        calls=[]
        class FakeFoxglove(socketserver.BaseRequestHandler):
            def handle(self):
                try:
                    self.request.settimeout(5)
                    header=b''
                    while b'\r\n\r\n' not in header:header+=self.request.recv(8192)
                    key=next(s.split(b':',1)[1].strip() for s in header.split(b'\r\n') if s.lower().startswith(b'sec-websocket-key:'))
                    accept=base64.b64encode(hashlib.sha1(key+b'258EAFA5-E914-47DA-95CA-C5AB0DC85B11').digest())
                    self.request.sendall(b'HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Accept: '+accept+b'\r\nSec-WebSocket-Protocol: foxglove.websocket.v1\r\n\r\n')
                    channels=[dict(id=1,topic='/innolidar_points',encoding='ros1',schemaName='sensor_msgs/PointCloud2'),
                        dict(id=2,topic='/single_target_live/state',encoding='ros1',schemaName='std_msgs/String')]
                    self.request.sendall(ws_frame(1,json.dumps(dict(op='advertise',channels=channels)).encode()))
                    time.sleep(.08)
                    def send(subscription,payload):
                        self.request.sendall(ws_frame(2,struct.pack('<BIQ',1,subscription,0)+payload))
                    send(2,text(json.dumps({**state,'source':None}))) # legal startup UNKNOWN, must not disconnect
                    wrong={**state,'source':{**source,'stamp_nsecs':(source['stamp_nsecs']+1)%1000000000}}
                    send(1,cloud);send(2,text(json.dumps(wrong))) # same seq, wrong timestamp must not bind
                    time.sleep(.1)
                    send(2,text(json.dumps(state)))
                    time.sleep(.12)
                    send(1,cloud);send(2,text(json.dumps(state)))
                    # Leave connection open and silent: the service must invalidate after TTL.
                    time.sleep(3)
                except (OSError,StopIteration):pass
        class FakeJoint(BaseHTTPRequestHandler):
            phase='idle'
            def log_message(self,*args):pass
            def reply(self):
                payload=json.dumps(dict(state=self.phase,radar_frames=12,camera_frames=14,path='mock-only')).encode()
                self.send_response(200);self.send_header('Content-Length',str(len(payload)));self.end_headers();self.wfile.write(payload)
            def do_GET(self):calls.append(('GET',self.path));self.reply()
            def do_POST(self):
                body=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                calls.append(('POST',self.path,body))
                self.__class__.phase='recording' if self.path=='/api/start' else 'completed';self.reply()
        ws=socketserver.ThreadingTCPServer(('127.0.0.1',0),FakeFoxglove);ws.daemon_threads=True
        joint=ThreadingHTTPServer(('127.0.0.1',0),FakeJoint)
        for server in (ws,joint):threading.Thread(target=server.serve_forever,daemon=True).start()
        try:
            report=self.run_service(['--smoke','--smoke-live',f'ws://127.0.0.1:{ws.server_address[1]}',
                '--joint-url',f'http://127.0.0.1:{joint.server_port}/','--smoke-joint','--screenshot',str(self.out/'window.png')])
            frames=[r['info'] for r in report['log'] if r['eventType']=='published' and r['info']['mode']=='live']
            self.assertTrue(frames,'No live frames reached Qt')
            self.assertTrue(any(f['targetCount']==len(chosen['sourceRows']) and f['targetMode']=='automatic' for f in frames))
            live_intensity=b''.join(raw[i+12:i+16] for i in range(0,len(raw),28) if all(__import__('math').isfinite(v) for v in struct.unpack_from('<fff',raw,i)))
            self.assertTrue(any(f['intensityAvailable'] and f['intensitySha256']==hashlib.sha256(live_intensity).hexdigest() for f in frames))
            self.assertTrue(any(r['eventType']=='liveStatus' and 'stale' in r['message'] and r['clearTarget'] for r in report['log']))
            self.assertEqual([(r[0],r[1]) for r in calls],[('GET','/api/status'),('POST','/api/start'),('POST','/api/stop'),('GET','/api/status')])
            self.assertEqual(report['jointMutationRequests'],2) # fake local start/stop, no real device calls
            self.assertEqual(report['directBoardCalls'],0)
            self.assertTrue(any(r['eventType']=='modeCleared' and r['clearTarget'] for r in report['log']))
            self.assertTrue(all(f.get('depth') is None for f in frames))
        finally:
            for server in (ws,joint):server.shutdown();server.server_close()

    def test_native_smoke_pick_selects_points(self):
        """--smoke-pick：QML 相机标定 + 视锥框选必须选中当前帧点（退出码 0）。"""
        self.run_service(['--smoke','--smoke-pick'])

    def test_skeleton_requires_current_target_support_and_position(self):
        import copy
        import sys
        sys.path.insert(0,str(ROOT/'pc_apps/range_fall'))
        from analysis import content_sha
        original=json.loads(ANALYSIS.read_text('utf-8'))
        if not any(r.get('skeleton',{}).get('nodes') for r in original['frames']):
            self.skipTest('analysis has no skeleton')
        base=self.out
        for kind in ('support','position'):
            self.out=base/kind;self.out.mkdir()
            doc=copy.deepcopy(original)
            for r in doc['frames']:r.pop('depth',None)
            row=next(r for r in doc['frames'] if r.get('skeleton',{}).get('nodes'))
            node=next(iter(row['skeleton']['nodes'].values()))
            if kind=='support':node['sourceRows'][0]=500000
            else:node['xyz'][0]+=.2
            doc['contentSha256']=content_sha({k:v for k,v in doc.items() if k!='contentSha256'})
            path=self.out/'bad.json';path.write_text(json.dumps(doc,separators=(',',':')), 'utf-8')
            self.run_service(['--check'],analysis=path,expect=2)
            self.assertIn('Skeleton', (self.out/'stderr.txt').read_text('utf-8'))

    def _run_plain(self,extra,session,expect=0):
        """无 --analysis 起服务（删除测试用独立临时会话目录）。"""
        args=[str(SDK),str(DLL),'--session',str(session),'--host',str(HOST),
              '--report',str(self.out/'run.json')]+list(extra)
        result=subprocess.run(args,cwd=ROOT,capture_output=True,timeout=90)
        (self.out/'stdout.txt').write_bytes(result.stdout);(self.out/'stderr.txt').write_bytes(result.stderr)
        self.assertEqual(result.returncode,expect,result.stderr.decode(errors='replace'))
        return json.loads((self.out/'run.json').read_text())

    def _delete_workdir(self,sids):
        """合法最小会话：meta.json 契约可被 SessionReader 校验（stride28/帧界/单调时间）。"""
        import json as _json
        work=self.out/'sessions';work.mkdir()
        for i,sid in enumerate(sids):
            d=work/sid;d.mkdir()
            (d/'points.bin').write_bytes(bytes(28*3))
            meta=dict(point_file='points.bin',
                      point_layout=dict(stride_bytes=28,dtypes=[],fields=[],pad_offsets_bytes=[],endian='little'),
                      frames=[dict(offset_points=0,count_points=1,stamp_sec=1.0+i,stamp_nanosec=0),
                              dict(offset_points=1,count_points=2,stamp_sec=2.0+i,stamp_nanosec=0)],
                      total_points=3)
            (d/'meta.json').write_text(_json.dumps(meta))
        return work

    def test_delete_session_local_and_board(self):
        """deleteProbe 出清单 → 确认摘要比对 → 先板端(假)后本地删除；打开中的会话回退到剩余会话。"""
        work=self._delete_workdir(['del_target_001','del_keep_002'])
        calls=[]
        class FakeBoard(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def do_DELETE(self):
                calls.append(self.path)
                payload=b'{"deleted":true}'
                self.send_response(200);self.send_header('Content-Length',str(len(payload)));self.end_headers()
                self.wfile.write(payload)
        board=ThreadingHTTPServer(('127.0.0.1',0),FakeBoard)
        threading.Thread(target=board.serve_forever,daemon=True).start()
        try:
            report=self._run_plain(['--smoke-delete','del_target_001,probe,%d' % board.server_port],work/'del_target_001')
            self.assertEqual(calls,['/api/v1/sessions/del_target_001'])
            self.assertFalse((work/'del_target_001').exists())
            self.assertTrue((work/'del_keep_002').exists())
            deleted=[l for l in report['log'] if l['eventType']=='sessionDeleted']
            self.assertEqual(len(deleted),1)
            self.assertTrue(deleted[0]['board'])
            self.assertEqual(deleted[0]['bytes'],
                         sum(f.stat().st_size for f in (work/'del_keep_002').iterdir()) + sum(f.stat().st_size for f in []))
            probes=[l for l in report['log'] if l['eventType']=='deleteProbe']
            self.assertEqual(len(probes),1)
            self.assertEqual(probes[0]['fileCount'],2)
        finally:
            board.shutdown();board.server_close()

    def test_delete_confirm_rejects_manifest_drift(self):
        """确认时摘要与探测不一致 → 拒绝删除、不触板端、目录原样。"""
        import hashlib as _hashlib
        work=self._delete_workdir(['drift_001','drift_keep'])
        report=self._run_plain(['--smoke-delete','drift_001,bad,0'],work/'drift_001')
        self.assertTrue((work/'drift_001').exists())
        errors=[l for l in report['log'] if l['eventType']=='commandError']
        self.assertTrue(any('变化' in l['message'] for l in errors))
        probes=[l for l in report['log'] if l['eventType']=='deleteProbe']
        self.assertEqual(len(probes),1)
        self.assertTrue(re.fullmatch(r'[0-9a-f]{64}', probes[0]['sha256']))
        for entry in probes[0]['files']:
            disk=(work/'drift_001'/entry['name']).read_bytes()
            self.assertEqual(entry['sha256'], hashlib.sha256(disk).hexdigest())
            self.assertEqual(entry['bytes'], len(disk))

    def test_delete_refuses_last_local_session(self):
        """只剩一个本地会话时拒绝删除（服务无法脱离会话运行）。"""
        work=self._delete_workdir(['lonely_001'])
        report=self._run_plain(['--smoke-delete','lonely_001,probe,0'],work/'lonely_001')
        self.assertTrue((work/'lonely_001').exists())
        errors=[l for l in report['log'] if l['eventType']=='commandError']
        self.assertTrue(any('最后一个' in l['message'] for l in errors))

    def test_depth_bad_path_binding_and_checksum_rejected(self):
        import copy
        import sys
        sys.path.insert(0,str(ROOT/'pc_apps/range_fall'))
        from analysis import content_sha
        original=json.loads(ANALYSIS.read_text())
        if 'depth' not in original['frames'][0]:self.skipTest('legacy result has no depth')
        base=self.out
        for kind in ('path','binding','checksum'):
            self.out=base/kind;self.out.mkdir()
            doc=copy.deepcopy(original)
            d=doc['frames'][0]['depth']
            if kind=='path':d['preview']['path']='../outside.png'
            elif kind=='binding':d['gridSha256']='0'*64
            else:
                d['preview']['path']='bad.png';(self.out/'bad.png').write_bytes(b'corrupt')
            doc.pop('contentSha256');doc['contentSha256']=content_sha(doc)
            path=self.out/'bad_analysis.json';path.write_text(json.dumps(doc,ensure_ascii=False),'utf-8')
            report=self.run_service(['--check'],path,2)
            self.assertEqual(report['status'],'FAIL')
            self.assertTrue(any(r['eventType']=='failed' and 'depth' in r['error'].lower() for r in report['log']))

    def test_missing_or_bad_ack_fails_instead_of_waiting_forever(self):
        base=self.out
        for fault in ('bad','missing'):
            self.out=base/fault;self.out.mkdir()
            report=self.run_service(['--ack-fault',fault],expect=2)
            errors=[r['error'] for r in report['log'] if r['eventType']=='failed']
            self.assertTrue(any('acknowledgement' in e.lower() for e in errors))


if __name__=='__main__':unittest.main()
