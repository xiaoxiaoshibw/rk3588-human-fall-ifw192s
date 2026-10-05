"""GL-W01: numeric, provenance, immutable export and actual HTTP integration checks."""
import copy
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
import urllib.error
import urllib.request
import zipfile

import numpy as np
import leveling as W
import leveling_quality as Q
import human_replay_lib as H


def fixture(root):
    sid = "cap_20990101_000001"
    directory = Path(root) / sid
    directory.mkdir()
    rng = np.random.RandomState(42)
    rectangles = [[.5,1.3,-1,-.2],[1.7,2.5,-1,-.2],[.5,1.3,.2,1],[1.7,2.5,.2,1]]
    R, t = Q.rotation(26, -1), np.array([0, 0, 1.3])
    records, frames, offset = [], [], 0
    for ordinal in range(6):
        chunks = []
        for xl, xh, yl, yh in rectangles:
            display = np.column_stack([rng.uniform(xl+.08,xh-.08,80), rng.uniform(yl+.08,yh-.08,80), rng.normal(0,.002,80)])
            chunks.append((display - t) @ R)
        points = np.vstack(chunks)
        # Preserve invalid records, and every opaque slot byte, through export.
        points = np.vstack([points, [[0,0,0], [np.nan,1,2], [8,4,2]]])
        block = rng.randint(0, 256, (len(points), 28)).astype("u1")
        xyz = np.ndarray((len(points),3),dtype="<f4",buffer=block,strides=(28,4)); xyz[:] = points
        records.append(block)
        frames.append({"offset_points":offset,"count_points":len(points),"seq":100+ordinal,"stamp_sec":ordinal,"stamp_nanosec":0})
        offset += len(points)
    np.vstack(records).tofile(directory / "points.bin")
    meta = {"format":"human_capture_session","format_version":1,"session_id":sid,"sensor":{"frame_id":"innolidar"},
            "point_file":"points.bin","point_stride_bytes":28,"total_points":offset,"frames":frames,
            "point_layout":{"endian":"little","fields":["x","y","z"],"dtypes":["<f4"]*3},
            "human_annotations":[{"box":{"center":[1,2,3]},"source":"human"}]}
    W.dump(directory / "meta.json",meta)
    _,_,binding = W.source(root,sid)
    request = {"schema":1,"sid":sid,"source":binding,"config":{"pitch_deg":26,"roll_deg":-1,"physical_height_m":1.14,
                "regions":rectangles,"ground_confirmed":True,"basis":"synthetic independently defined ground rectangles"}}
    return directory, meta, request


class WorkbenchTest(unittest.TestCase):
    def test_transform_export_and_frozen_disjoint_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)/"remote";root.mkdir()
            directory,meta,req = fixture(root)
            before = {n:W.sha(directory/n) for n in ("meta.json","points.bin")}
            report,artifacts = W.run_job(root,Path(tmp)/"leveled",req,"a"*32,lambda m:None)
            self.assertEqual(set(artifacts),{"tls","svd","ransac"})
            self.assertEqual(report["consensus"],"GOOD")
            self.assertEqual(report["holdout_ordinals"],[1,3,5])
            self.assertEqual(report["fit_frame_count"],3)
            self.assertFalse(report["physical_verified"])
            output = Path(tmp)/"leveled"/("a"*32)
            with np.load(output/"domain.npz") as domain:
                self.assertFalse(set(domain["source_rows"]) & set(domain["holdout_rows"]))
                self.assertEqual(set(domain["frame_ordinals"]),{0,2,4})
                self.assertEqual(len(np.unique(domain["source_rows"])),len(domain["source_rows"]))
            raw = np.fromfile(directory/"points.bin",dtype="u1").reshape(-1,28)
            xyz = np.ndarray((len(raw),3),dtype="<f4",buffer=raw,strides=(28,4))
            valid = np.isfinite(xyz).all(axis=1)&np.any(xyz!=0,axis=1)
            for method in artifacts:
                data = np.fromfile(output/method/"points.bin",dtype="u1").reshape(-1,28)
                mapped = np.ndarray((len(data),3),dtype="<f4",buffer=data,strides=(28,4))
                model = report["estimators"][method];R=np.array(model["R"]);t=np.array(model["t"])
                self.assertTrue(np.array_equal(raw[:,12:],data[:,12:]))
                self.assertTrue(np.array_equal(raw[~valid],data[~valid]))
                np.testing.assert_allclose(mapped[valid],xyz[valid].astype(float)@R.T+t,atol=1e-6)
                np.testing.assert_allclose((mapped[valid]-t)@R,xyz[valid],atol=1e-6)
                self.assertAlmostEqual(np.linalg.det(R),1.,places=10)
                self.assertAlmostEqual(model["pitch_deg"],26,delta=.2)
                self.assertAlmostEqual(model["offset_source_m"],1.3,delta=.01)
                derived=json.loads((output/method/"meta.json").read_text("utf-8"))
                self.assertEqual(derived["frames"],meta["frames"])
                self.assertEqual(derived["human_annotations"],[])
                self.assertEqual(derived["source_annotations"],meta["human_annotations"])
                self.assertFalse(derived["leveling"]["runtime_eligible"])
                with zipfile.ZipFile(output/method/"dataset.zip") as z:
                    self.assertIn("domain.npz",z.namelist());self.assertEqual(z.read("points.bin"),data.tobytes())
            self.assertEqual(before,{n:W.sha(directory/n) for n in before})
            with self.assertRaises(FileExistsError):
                W.run_job(root,Path(tmp)/"leveled",req,"a"*32,lambda m:None)

    def test_request_boundary_source_drift_and_owned_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/"remote";root.mkdir();directory,meta,req=fixture(root)
            owned=W.validate_request(req);req["config"]["regions"][0][0]=-.3
            self.assertEqual(owned["config"]["regions"][0][0],.5)
            for field,value in (("schema",True),("schema",2),("config",[])):
                bad=copy.deepcopy(owned);bad[field]=value
                with self.assertRaises(ValueError):W.validate_request(bad)
            for value in (True,"26",float("nan"),float("inf"),76):
                bad=copy.deepcopy(owned);bad["config"]["pitch_deg"]=value
                with self.assertRaises(ValueError):W.validate_request(bad)
            bad=copy.deepcopy(owned);bad["config"]["regions"][1]=bad["config"]["regions"][0]
            with self.assertRaises(ValueError):W.validate_request(bad)
            with self.assertRaises(ValueError):W.session_path(root,"../remote")
            # Same session ID, different metadata must fail before output is made.
            with (directory/"meta.json").open("a") as f:f.write(" ")
            with self.assertRaisesRegex(ValueError,"源数据已变化"):
                W.run_job(root,Path(tmp)/"leveled",owned,"b"*32,lambda m:None)
            self.assertFalse((Path(tmp)/"leveled").exists())
            meta["frames"][1]["offset_points"]=0
            (directory/"meta.json").write_text(json.dumps(meta),encoding="utf-8")
            with self.assertRaisesRegex(ValueError,"连续且互斥"):W.source(root,owned["sid"])
            for broken in ([], {"sensor":None,"point_layout":{}}, {"sensor":{},"point_layout":None}):
                (directory/"meta.json").write_text(json.dumps(broken),encoding="utf-8")
                with self.assertRaisesRegex(ValueError,"必须是object"):W.source(root,owned["sid"])

    def test_line_domain_and_ls_majority_cannot_override_conflict(self):
        rng=np.random.RandomState(21)
        points=np.column_stack([rng.uniform(-.3,.3,400),rng.uniform(-.3,.3,400),np.full(400,-1.3)])
        codes=np.tile(np.arange(1,5,dtype=np.uint8),100)
        held=[{"ordinal":i,"points":points.copy(),"regions":codes.copy()} for i in [1,2,3]]
        normal=Q.rotation(3,0)[2];offset=-float(normal@points.mean(axis=0))
        with patch.dict(Q.ESTIMATORS,{"ransac":lambda p:(normal,offset)}):
            result=Q.compare(points,codes,held,np.array([0,0,1.]))
        self.assertTrue(all(r["valid"] for r in result["estimators"].values()))
        self.assertIsNone(result["recommended"])
        self.assertEqual(result["consensus"],"NO_RECOMMENDATION")
        line=np.column_stack([np.linspace(-1,1,400),np.zeros(400),np.full(400,-1.3)])
        bad=Q.compare(line,codes,held,np.array([0,0,1.]))
        self.assertFalse(any(r["valid"] for r in bad["estimators"].values()))

    def test_actual_http_job_failures_concurrency_download_and_no_board(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/"remote";root.mkdir();_,meta,req=fixture(root)
            with patch.object(H.C,"DEST_ROOT",str(root)),patch.object(H,"_board_get",side_effect=AssertionError("board forbidden")):
                server=H.ThreadingHTTPServer(("127.0.0.1",0),H.Handler)
                thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
                base="http://127.0.0.1:"+str(server.server_address[1])
                def get(path):return json.load(urllib.request.urlopen(base+path,timeout=20))
                def post(body,origin=None):
                    headers={"Content-Type":"application/json"}
                    if origin:headers["Origin"]=origin
                    request=urllib.request.Request(base+"/api/leveling/run",json.dumps(body).encode(),headers)
                    return json.load(urllib.request.urlopen(request,timeout=20))
                try:
                    self.assertEqual(get("/api/leveling/sessions")["sessions"][0]["sid"],req["sid"])
                    self.assertEqual(get("/api/leveling/source?sid="+req["sid"])["source"],req["source"])
                    with self.assertRaises(urllib.error.HTTPError) as cm:post(req,"https://external.invalid")
                    self.assertEqual(cm.exception.code,400);cm.exception.close()
                    W._writer_lock.acquire()
                    try:
                        with self.assertRaises(urllib.error.HTTPError) as cm:post(req)
                        self.assertEqual(cm.exception.code,409);cm.exception.close()
                    finally:W._writer_lock.release()
                    job_id=post(req)["job_id"]
                    for _ in range(100):
                        job=get("/api/leveling/job?id="+job_id)
                        if job["state"]!="running":break
                        time.sleep(.1)
                    self.assertEqual(job["state"],"ready",job)
                    url=base+"/api/leveling/artifact?id="+job_id+"&method=tls&name=dataset.zip"
                    with urllib.request.urlopen(url) as response:
                        data=response.read();self.assertEqual(len(data),int(response.headers["Content-Length"]))
                    self.assertTrue(data.startswith(b"PK"))
                    with self.assertRaises(ValueError):W.artifact_path(Path(tmp)/"leveled",job_id,"tls","../meta.json")
                    model_file=Path(tmp)/"leveled"/job_id/"tls"/"transform.json"
                    with model_file.open("a") as stream:stream.write(" ")
                    with self.assertRaisesRegex(ValueError,"SHA已变化"):
                        W.artifact_path(Path(tmp)/"leveled",job_id,"tls","transform.json")
                    wrong=copy.deepcopy(req);wrong["source"]["bin_sha256"]="0"*64
                    failed_id=post(wrong)["job_id"]
                    for _ in range(100):
                        failed=get("/api/leveling/job?id="+failed_id)
                        if failed["state"]!="running":break
                        time.sleep(.02)
                    self.assertEqual(failed["state"],"failed")
                    with self.assertRaises(ValueError):W.artifact_path(Path(tmp)/"leveled",failed_id,"report","report.json")
                    # Sparse separated patches no longer establish a connected unobstructed floor.
                    auto_req = {"schema":1,"sid":req["sid"],"source":req["source"],
                                "config":{"pitch_deg":26,"roll_deg":-1,"physical_height_m":1.14,"mode":"auto"}}
                    auto_job_id = post(auto_req)["job_id"]
                    for _ in range(100):
                        auto_job = get("/api/leveling/job?id="+auto_job_id)
                        if auto_job["state"]!="running":break
                        time.sleep(.1)
                    self.assertEqual(auto_job["state"],"failed",auto_job)
                    self.assertIn("floor_regions_invalid",auto_job["error"])
                    # Positive auto path: dense continuous floor plus a much denser table/person.
                    from floor_detector_test import scene
                    source_points,frame_ids,_=scene()
                    auto_sid="cap_20990101_000002";auto_dir=root/auto_sid;auto_dir.mkdir()
                    records=np.zeros((len(source_points)*2,28),dtype="u1")
                    np.ndarray((len(records),3),dtype="<f4",buffer=records,strides=(28,4))[:]=np.vstack([source_points,source_points])
                    records.tofile(auto_dir/"points.bin")
                    auto_meta=copy.deepcopy(meta);auto_meta["session_id"]=auto_sid;auto_meta["total_points"]=len(records)
                    count=len(source_points)//3
                    auto_meta["frames"]=[{"seq":800+i,"offset_points":i*count,"count_points":count,"stamp_sec":i,"stamp_nanosec":0} for i in range(6)]
                    W.dump(auto_dir/"meta.json",auto_meta)
                    auto_req["sid"]=auto_sid;auto_req["source"]=W.source(root,auto_sid)[2]
                    auto_job_id=post(auto_req)["job_id"]
                    for _ in range(200):
                        auto_job=get("/api/leveling/job?id="+auto_job_id)
                        if auto_job["state"]!="running":break
                        time.sleep(.05)
                    self.assertEqual(auto_job["state"],"ready",auto_job)
                    self.assertEqual(auto_job["report"]["config"]["mode"],"auto")
                    self.assertEqual(auto_job["report"]["config"]["ground_confirmed"],False)
                    self.assertEqual(auto_job["report"]["config"]["ground_identification"],"algorithm_candidate")
                    self.assertTrue(auto_job["report"]["config"]["basis"].startswith("auto:"))
                    lv=get("/api/leveling/leveled_latest?sid="+auto_sid)
                    self.assertTrue(lv["ok"]);self.assertEqual(lv["transform"]["estimator"],"tls")
                    self.assertAlmostEqual(lv["transform"]["pitch_deg"],26,delta=.5)
                    self.assertAlmostEqual(lv["transform"]["roll_deg"],0,delta=.5)
                    with self.assertRaises(urllib.error.HTTPError) as cm:
                        urllib.request.urlopen(base+"/api/leveling/leveled_latest?sid=nonexistent_",timeout=20)
                    self.assertEqual(cm.exception.code,404);cm.exception.close()
                finally:server.shutdown();server.server_close();thread.join()


if __name__ == "__main__":
    unittest.main()
