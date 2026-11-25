import asyncio
import json
from pathlib import Path
import sys
import tempfile
import unittest

import aiohttp
from aiohttp import web

STUDIO_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = STUDIO_DIR.parents[1]
if str(STUDIO_DIR) not in sys.path:
    sys.path.insert(0, str(STUDIO_DIR))

from camera_hub import LiveCameraHub, ReplayCameraIndex  # noqa: E402


def _make_fake_jpeg(tag: bytes) -> bytes:
    return b"\xff\xd8\xff\xe0" + tag + b"\xff\xd9"


class TestCameraHub(unittest.TestCase):
    def test_250ms_alignment_boundaries(self):
        with tempfile.TemporaryDirectory() as tmp:
            sdir = Path(tmp)
            jpg0 = _make_fake_jpeg(b"frame0")
            jpg1 = _make_fake_jpeg(b"frame1")
            (sdir / "camera.mjpeg").write_bytes(jpg0 + jpg1)

            base_ns = 1_700_000_000_000_000_000
            rows = [
                {"offset": 0, "length": len(jpg0), "recv_unix_ns": base_ns},
                {"offset": len(jpg0), "length": len(jpg1), "recv_unix_ns": base_ns + 1_000_000_000},
            ]
            (sdir / "camera_frames.jsonl").write_text(
                "\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8"
            )

            with ReplayCameraIndex(sdir) as idx:
                self.assertTrue(idx.available)
                # 精确 +250.0 ms 边界应命中
                data, info = idx.match((base_ns - 250_000_000) / 1e9)
                self.assertEqual(info["state"], "ready")
                self.assertAlmostEqual(info["deltaMs"], 250.0, places=3)
                self.assertEqual(data, jpg0)

                # 精确 -250.0 ms 边界应命中
                data, info = idx.match((base_ns + 250_000_000) / 1e9)
                self.assertEqual(info["state"], "ready")
                self.assertAlmostEqual(info["deltaMs"], -250.0, places=3)
                self.assertEqual(data, jpg0)

                # -250.5 ms 与 +250.5 ms 超界均判 outside 且不返图
                data, info = idx.match((base_ns + 250_500_000) / 1e9)
                self.assertIsNone(data)
                self.assertEqual(info["state"], "outside")

                data, info = idx.match((base_ns + 1_000_000_000 - 250_500_000) / 1e9)
                self.assertIsNone(data)
                self.assertEqual(info["state"], "outside")

                # 无效时间戳
                data, info = idx.match(None)
                self.assertIsNone(data)
                self.assertEqual(info["state"], "outside")

    def test_no_camera_session_and_corrupt_rejection(self):
        with tempfile.TemporaryDirectory() as tmp:
            sdir = Path(tmp)
            with ReplayCameraIndex(sdir) as idx:
                self.assertFalse(idx.available)
                jpg, info = idx.match(100.0)
                self.assertIsNone(jpg)
                self.assertEqual(info["state"], "unavailable")

            # 只有 index 没有 mjpeg 应拒绝
            (sdir / "camera_frames.jsonl").write_text('{"offset":0,"length":10,"recv_unix_ns":100}\n', encoding="utf-8")
            with self.assertRaises(ValueError):
                ReplayCameraIndex(sdir)

            # 坏 JPEG SOI/EOI 应拒绝
            (sdir / "camera.mjpeg").write_bytes(b"NOT_A_JPEG")
            with self.assertRaises(ValueError):
                ReplayCameraIndex(sdir)

            # 非递增时间戳应拒绝
            jpg = _make_fake_jpeg(b"ok")
            (sdir / "camera.mjpeg").write_bytes(jpg + jpg)
            (sdir / "camera_frames.jsonl").write_text(
                json.dumps({"offset": 0, "length": len(jpg), "recv_unix_ns": 1000}) + "\n"
                + json.dumps({"offset": len(jpg), "length": len(jpg), "recv_unix_ns": 999}) + "\n",
                encoding="utf-8",
            )
            with self.assertRaises(ValueError):
                ReplayCameraIndex(sdir)

    def test_real_six_camera_sessions(self):
        sids = [
            "cap_20261028_houdao",
            "cap_20261028_qiandao",
            "cap_20261028_huanmandiedao",
            "cap_20261028_jixiedaiwanyao",
            "cap_20261023_221125",
            "cap_20261015_224823",
        ]
        for sid in sids:
            sdir = REPO_ROOT / "data" / "sessions" / sid
            if not sdir.is_dir():
                self.skipTest(f"missing data session {sid}")
            meta = json.loads((sdir / "meta.json").read_text(encoding="utf-8"))
            with ReplayCameraIndex(sdir) as idx:
                self.assertTrue(idx.available, sid)
                for f in (meta["frames"][0], meta["frames"][len(meta["frames"]) // 2], meta["frames"][-1]):
                    jpg, info = idx.match(f["bag_time_sec"])
                    self.assertEqual(info["state"], "ready", f"{sid}: {info}")
                    self.assertIsNotNone(jpg)
                    self.assertTrue(jpg.startswith(b"\xff\xd8") and jpg.endswith(b"\xff\xd9"))

    def test_live_camera_hub_single_upstream_fanout(self):
        async def run():
            upstream_connections = 0
            jpg_a = _make_fake_jpeg(b"streamA" * 20)
            jpg_b = _make_fake_jpeg(b"streamB" * 20)

            async def mjpeg_handler(request):
                nonlocal upstream_connections
                upstream_connections += 1
                resp = web.StreamResponse(
                    status=200,
                    headers={"Content-Type": "multipart/x-mixed-replace; boundary=frame"},
                )
                await resp.prepare(request)
                try:
                    for frame in (jpg_a, jpg_b):
                        await resp.write(
                            b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + frame + b"\r\n"
                        )
                        await asyncio.sleep(0.03)
                    while True:
                        await resp.write(
                            b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + jpg_b + b"\r\n"
                        )
                        await asyncio.sleep(0.05)
                except (asyncio.CancelledError, ConnectionResetError):
                    pass
                return resp

            app = web.Application()
            app.router.add_get("/stream", mjpeg_handler)
            runner = web.AppRunner(app)
            await runner.setup()
            site = web.TCPSite(runner, "127.0.0.1", 0)
            await site.start()
            port = site._server.sockets[0].getsockname()[1]

            hub = LiveCameraHub(f"http://127.0.0.1:{port}/stream")
            try:
                q1 = await hub.subscribe()
                q2 = await hub.subscribe()
                f1 = await asyncio.wait_for(q1.get(), timeout=2.0)
                f2 = await asyncio.wait_for(q2.get(), timeout=2.0)
                self.assertIn(f1, (jpg_a, jpg_b))
                self.assertIn(f2, (jpg_a, jpg_b))
                # 验证无论多少前端订阅者，板端上游只建立 1 条连接
                self.assertEqual(upstream_connections, 1)
                self.assertEqual(hub.status()["subscribers"], 2)

                await hub.unsubscribe(q1)
                await hub.unsubscribe(q2)
                await asyncio.sleep(0.05)
                self.assertEqual(hub.status()["subscribers"], 0)
                self.assertEqual(hub.status()["state"], "idle")
            finally:
                await hub.close()
                await runner.cleanup()

        asyncio.run(run())


if __name__ == "__main__":
    unittest.main()
