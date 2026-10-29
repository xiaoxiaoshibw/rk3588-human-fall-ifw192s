#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""annotator_v2 server.py 单元测试（临时夹具：合成会话 + 临时 GT 存储 + 临时 dist）。

运行：cd pc_apps/annotator_v2 && python -B -W error -m unittest test_server -v
"""
import json
import os
import shutil
import struct
import hashlib
import tempfile
import threading
import unittest
import urllib.request
import urllib.error
from http.server import ThreadingHTTPServer

import server as srv

STRIDE = 28


def make_session(root, sid, n_frames=3, points_per_frame=5):
    d = os.path.join(root, sid)
    os.makedirs(d, exist_ok=True)
    blob = bytearray()
    frames = []
    for fi in range(n_frames):
        offset = len(blob) // STRIDE
        for pi in range(points_per_frame):
            # x,y,z,intensity + ring(u2)+pad + timestamp(f4)+pad → 28B
            blob += struct.pack("<ffffH", fi + pi * 0.1, pi * 0.2, 0.5 + fi, pi / 255.0, pi % 32)
            blob += b"\x00" * 2
            blob += struct.pack("<f", fi * 0.1 + pi * 0.001)
            blob += b"\x00" * 4
        frames.append({
            "count_points": points_per_frame,
            "offset_points": offset,
            "stamp_sec": 100.0 + fi * 0.1,
            "bag_time_sec": 1792764686.0 + fi,
        })
    with open(os.path.join(d, "points.bin"), "wb") as fh:
        fh.write(blob)
    meta = {
        "format": "human_capture_session", "session_id": sid,
        "point_stride_bytes": STRIDE,
        "point_layout": {"fields": ["x", "y", "z", "intensity", "ring", "timestamp"],
                          "dtypes": ["<f4", "<f4", "<f4", "<f4", "<u2", "<f4"],
                          "stride_bytes": STRIDE},
        "frames": frames, "total_points": n_frames * points_per_frame,
        "created_iso": "2026-10-24T00:00:00+08:00",
    }
    with open(os.path.join(d, "meta.json"), "w", encoding="utf-8") as fh:
        json.dump(meta, fh)
    return bytes(blob)


class ServerFixture(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="annotator_v2_test_")
        self.data_root = os.path.join(self.tmp, "sessions")
        self.store_root = os.path.join(self.tmp, "gt_store_v2")
        self.dist = os.path.join(self.tmp, "dist")
        os.makedirs(self.data_root, exist_ok=True)
        os.makedirs(self.dist, exist_ok=True)
        self.blob = make_session(self.data_root, "cap_test_001")
        with open(os.path.join(self.dist, "index.html"), "w", encoding="utf-8") as fh:
            fh.write("<html>ok</html>")
        srv._META_CACHE.clear()
        handler = type("H", (srv.Handler,), {
            "data_root": self.data_root,
            "store_root": self.store_root,
            "dist_root": self.dist,
        })
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self.port = self.httpd.server_address[1]
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()
        self.base = "http://127.0.0.1:%d" % self.port

    def tearDown(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def get(self, path, raw=False):
        req = urllib.request.Request(self.base + path)
        with urllib.request.urlopen(req, timeout=10) as res:
            data = res.read()
            return data if raw else json.loads(data.decode("utf-8"))

    def put(self, path, body):
        req = urllib.request.Request(
            self.base + path, method="PUT",
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=10) as res:
                return res.status, json.loads(res.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read().decode("utf-8"))

    def status_of(self, path):
        try:
            with urllib.request.urlopen(self.base + path, timeout=10) as res:
                return res.status
        except urllib.error.HTTPError as e:
            return e.code


class TestApi(ServerFixture):
    def test_sessions_list(self):
        out = self.get("/api/sessions")
        self.assertEqual(len(out["sessions"]), 1)
        s = out["sessions"][0]
        self.assertEqual(s["sessionId"], "cap_test_001")
        self.assertEqual(s["frameCount"], 3)
        self.assertAlmostEqual(s["durationSec"], 0.2, places=6)
        self.assertEqual(s["totalPoints"], 15)

    def test_meta_and_frame_slice_exact(self):
        meta = self.get("/api/session/cap_test_001/meta")
        self.assertEqual(meta["session_id"], "cap_test_001")
        for i in range(3):
            data = self.get("/api/session/cap_test_001/frame/%d" % i, raw=True)
            expect = self.blob[i * 5 * STRIDE:(i + 1) * 5 * STRIDE]
            self.assertEqual(len(data), 5 * STRIDE)
            self.assertEqual(data, expect)
            x0 = struct.unpack_from("<f", data, 0)[0]
            self.assertAlmostEqual(x0, i, places=6)

    def test_frame_out_of_range_and_bad_sid(self):
        self.assertEqual(self.status_of("/api/session/cap_test_001/frame/99"), 404)
        self.assertEqual(self.status_of("/api/session/..%2f..%2fetc/meta"), 400)
        self.assertEqual(self.status_of("/api/session/no_such/meta"), 404)

    def test_static_index_and_traversal(self):
        self.assertEqual(self.status_of("/"), 200)
        self.assertEqual(self.status_of("/../server.py"), 403)
        self.assertEqual(self.status_of("/nope.js"), 200)  # SPA 回退 index.html


class TestGtApi(ServerFixture):
    def doc(self):
        return {
            "format": "gt_annotate", "formatVersion": 2,
            "sessionId": "cap_test_001", "coordinateFrame": "sensor-IFW192S-raw",
            "units": "m", "frameCount": 3, "annotator": "tester",
            "persons": [{"personId": "P1", "label": None, "color": None}],
            "boxes": [], "intervals": [], "suggestions": [], "savedAtMs": 1,
        }

    def test_draft_lifecycle_and_conflict(self):
        # 空
        out = self.get("/api/gt?sid=cap_test_001")
        self.assertEqual(out, {"version": 0, "doc": None})
        # 首存 baseVersion null
        status, body = self.put("/api/gt?sid=cap_test_001", {"baseVersion": None, "doc": self.doc()})
        self.assertEqual(status, 200)
        self.assertEqual(body["version"], 1)
        # 他人先写 → 409
        status, body = self.put("/api/gt?sid=cap_test_001", {"baseVersion": None, "doc": self.doc()})
        self.assertEqual(status, 409)
        self.assertEqual(body["currentVersion"], 1)
        # 带正确 base → v2
        status, body = self.put("/api/gt?sid=cap_test_001", {"baseVersion": 1, "doc": self.doc()})
        self.assertEqual(status, 200)
        self.assertEqual(body["version"], 2)
        # 读回
        out = self.get("/api/gt?sid=cap_test_001")
        self.assertEqual(out["version"], 2)
        self.assertEqual(out["doc"]["annotator"], "tester")
        # 磁盘上是合法信封且无 tmp 残留
        draft_path = os.path.join(self.store_root, "cap_test_001", "draft.json")
        with open(draft_path, "r", encoding="utf-8") as fh:
            env = json.load(fh)
        self.assertEqual(env["version"], 2)
        leftovers = [f for f in os.listdir(os.path.dirname(draft_path)) if f.startswith(".draft-")]
        self.assertEqual(leftovers, [])

    def test_rejects_non_gt_doc(self):
        status, body = self.put("/api/gt?sid=cap_test_001", {"baseVersion": None, "doc": {"format": "other"}})
        self.assertEqual(status, 400)

    def test_bad_payload(self):
        status, _ = self.put("/api/gt?sid=cap_test_001", {"baseVersion": None, "doc": 42})
        self.assertEqual(status, 400)
        self.assertEqual(self.status_of("/api/gt?sid=bad/sid"), 400)


class TestAnalysisApi(ServerFixture):
    def test_depth_routes_reject_changed_calibration_bytes_and_paths(self):
        from analysis import AnalysisStore, content_sha, sha_file
        import zlib
        def chunk(kind,data):
            return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data)&0xffffffff)
        raw=(b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',256,192,8,2,0,0,0))
             +chunk(b'IDAT',zlib.compress(bytes(192*(1+256*3))))+chunk(b'IEND',b''))
        with open(os.path.join(self.tmp,'preview.png'),'wb') as f:f.write(raw)
        binding={'grid_sha256':'f'*64}
        d=dict(format='lidar_range_image',version=1,width=256,height=192,sessionId='cap_test_001',frameIndex=1,
               stampSec=100.1,rawSha256=hashlib.sha256(self.blob[140:280]).hexdigest(),sourceBinding=binding,
               gridSha256='f'*64,quantity='radial_range',units='m',scaleM=.001,invalidValue=0,overflowValue=65535,
               orientation='row=ring,column=calibration_native_order',interpolation=False,
               preview={'path':'preview.png','bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()})
        row=dict(frameIndex=1,stampSec=100.1,rawSha256=d['rawSha256'],sourceRows=[],box=None,measured=False,
                 state='unknown',depth=d,trackId=None,generation=0,observationGap=False)
        session=os.path.join(self.data_root,'cap_test_001')
        doc=dict(format='range_fall_analysis',version=1,sessionId='cap_test_001',coordinateFrame='sensor-IFW192S-raw',
                 units='m',sourceFrameCount=3,confirmedEnabled=False,semantic='UNKNOWN',frames=[row],intervals=[],
                 sourceBinding=binding,metaSha256=sha_file(os.path.join(session,'meta.json')),
                 pointsSha256=sha_file(os.path.join(session,'points.bin')))
        doc['contentSha256']=content_sha(doc)
        path=os.path.join(self.tmp,'analysis.json')
        with open(path,'w',encoding='utf-8') as f:json.dump(doc,f)
        store=AnalysisStore([path],self.data_root);self.httpd.RequestHandlerClass.analysis_store=store
        endpoint='/api/session/cap_test_001/depth/1/preview'
        self.assertEqual(self.get(endpoint,raw=True),raw)
        self.assertEqual(self.status_of('/api/session/cap_test_001/depth/0/preview'),404)
        self.assertEqual(self.status_of('/api/session/cap_test_001/depth/1/other'),404)
        depth=store.documents['cap_test_001']['frames'][0]['depth']
        depth['gridSha256']='0'*64;self.assertEqual(self.status_of(endpoint),409)
        depth['gridSha256']='f'*64
        depth['preview']['path']='../secret';self.assertEqual(self.status_of(endpoint),409)
        depth['preview']['path']='preview.png'
        with open(os.path.join(self.tmp,'preview.png'),'wb') as f:f.write(b'changed')
        self.assertEqual(self.status_of(endpoint),409)

    def test_source_bound_result_and_mutation_rejection(self):
        from analysis import content_sha, sha_file, suspected_intervals, AnalysisStore
        session=os.path.join(self.data_root,'cap_test_001')
        frames=[]
        for i in range(3):
            frames.append(dict(frameIndex=i,stampSec=100+i*.1,state='unknown',measured=False,
                sourceRows=[],box=None,trackId=None,generation=0,observationGap=False,
                rawSha256=hashlib.sha256(self.blob[i*140:(i+1)*140]).hexdigest()))
        doc=dict(format='range_fall_analysis',version=1,sessionId='cap_test_001',
            coordinateFrame='sensor-IFW192S-raw',units='m',sourceFrameCount=3,
            confirmedEnabled=False,semantic='UNKNOWN',frames=frames,intervals=suspected_intervals(frames),
            metaSha256=sha_file(os.path.join(session,'meta.json')),pointsSha256=sha_file(os.path.join(session,'points.bin')))
        doc['contentSha256']=content_sha(doc)
        path=os.path.join(self.tmp,'analysis.json')
        with open(path,'w',encoding='utf-8') as out:json.dump(doc,out)
        self.httpd.RequestHandlerClass.analysis_store=AnalysisStore([path],self.data_root)
        packet=self.get('/api/session/cap_test_001/analysis?frame=1')
        self.assertEqual(packet['frame']['frameIndex'],1)
        self.assertEqual(self.status_of('/api/session/cap_test_001/analysis?frame=-1'),400)
        self.assertEqual(self.status_of('/api/session/cap_test_001/analysis?frame=99'),404)
        self.assertEqual(self.status_of('/api/session/no_such/analysis?frame=0'),404)
        self.assertEqual(self.status_of('/api/unknown'),404)
        with open(os.path.join(session,'points.bin'),'r+b') as points:
            points.write(b'bad!')
        self.assertEqual(self.status_of('/api/session/cap_test_001/analysis?frame=0'),409)


if __name__ == "__main__":
    unittest.main()
