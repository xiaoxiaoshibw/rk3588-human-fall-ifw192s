import json
import math
from pathlib import Path
import struct
import subprocess
import sys
import unittest

import numpy as np

STUDIO_DIR = Path(__file__).resolve().parents[1]
if str(STUDIO_DIR) not in sys.path:
    sys.path.insert(0, str(STUDIO_DIR))

from protocol import (  # noqa: E402
    FLAG_FOREGROUND,
    FLAG_RECOVERY_ADDED,
    FLAG_TARGET_CORE,
    HEADER_SIZE,
    HEADER_STRUCT,
    MAGIC,
    pack_frame,
    sanitize_json,
    unpack_frame,
)


class TestProtocol(unittest.TestCase):
    def test_roundtrip_full_and_optional_segments(self):
        xyz = np.array([[1.25, -0.5, 0.3], [2.0, 0.1, -0.2], [3.5, 1.2, 1.1]], dtype=np.float32)
        flags = np.array([FLAG_TARGET_CORE, FLAG_RECOVERY_ADDED, FLAG_FOREGROUND], dtype=np.uint8)
        inten = np.array([120.5, 500.0, 890.25], dtype=np.float32)
        rmm = np.zeros((4, 6), dtype=np.uint16)
        rmm[1, 2] = 1500
        rmm[3, 5] = 4200
        rmask = np.zeros((4, 6), dtype=np.uint8)
        rmask[1, 2] = FLAG_TARGET_CORE
        state = {
            "frame_index": 83,
            "fall_status": "suspected",
            "nan_val": float("nan"),
            "inf_val": float("inf"),
            "nested": {"ok": np.float32(2.5)},
        }

        pkt = pack_frame(
            xyz,
            flags,
            rmm,
            state,
            intensity=inten,
            range_mask=rmask,
            decimation=2,
            is_live=True,
        )
        out = unpack_frame(pkt)
        self.assertEqual(out["version"], 1)
        self.assertEqual(out["decimation"], 2)
        self.assertTrue(out["is_live"])
        np.testing.assert_allclose(out["xyz"], xyz, atol=1e-6)
        np.testing.assert_allclose(out["intensity"], inten, atol=1e-6)
        np.testing.assert_array_equal(out["range_mm"], rmm)
        np.testing.assert_array_equal(out["point_flags"], flags)
        np.testing.assert_array_equal(out["range_mask"], rmask)
        self.assertIsNone(out["state"]["nan_val"])
        self.assertIsNone(out["state"]["inf_val"])
        self.assertAlmostEqual(out["state"]["nested"]["ok"], 2.5)

        # 无 intensity / 无 range_mask / 空点云
        pkt2 = pack_frame(
            np.empty((0, 3), dtype=np.float32),
            np.empty((0,), dtype=np.uint8),
            np.empty((0, 0), dtype=np.uint16),
            {"frame_index": 0},
            decimation=1,
            is_live=False,
        )
        out2 = unpack_frame(pkt2)
        self.assertEqual(out2["xyz"].shape, (0, 3))
        self.assertIsNone(out2["intensity"])
        self.assertIsNone(out2["range_mask"])
        self.assertFalse(out2["is_live"])

    def test_reject_malformed_packets(self):
        xyz = np.array([[1.0, 2.0, 3.0]], dtype=np.float32)
        flags = np.array([1], dtype=np.uint8)
        rmm = np.zeros((2, 2), dtype=np.uint16)
        pkt = pack_frame(xyz, flags, rmm, {"a": 1})

        with self.assertRaises(ValueError):
            unpack_frame(b"LDSF")
        with self.assertRaises(ValueError):
            unpack_frame(b"XXXX" + pkt[4:])
        with self.assertRaises(ValueError):
            unpack_frame(pkt[:-1])
        with self.assertRaises(ValueError):
            unpack_frame(pkt + b"extra")

        # 伪造版本 9
        bad_ver = bytearray(pkt)
        bad_ver[4] = 9
        with self.assertRaises(ValueError):
            unpack_frame(bytes(bad_ver))

        # 构造段长度不自洽头
        bad_hdr = HEADER_STRUCT.pack(MAGIC, 1, 0, 1, 1, 2, 2, 999, 0, 8, 1, 0, 5) + b"{}"
        with self.assertRaises(ValueError):
            unpack_frame(bad_hdr)

    def test_sanitize_json_strict(self):
        cleaned = sanitize_json({"a": float("nan"), "b": [float("-inf"), np.int64(7), np.bool_(True)]})
        self.assertIsNone(cleaned["a"])
        self.assertEqual(cleaned["b"], [None, 7, True])
        dumped = json.dumps(cleaned, allow_nan=False)
        self.assertNotIn("NaN", dumped)

    def test_cross_language_node_decode_parity(self):
        lib_path = STUDIO_DIR / "web" / "studio_lib.js"
        if not lib_path.is_file():
            self.skipTest("studio_lib.js not written yet")
        xyz = np.array([[1.5, -0.25, 0.75], [3.2, 0.4, -0.1]], dtype=np.float32)
        flags = np.array([FLAG_TARGET_CORE, FLAG_RECOVERY_ADDED], dtype=np.uint8)
        inten = np.array([250.0, 910.0], dtype=np.float32)
        rmm = np.array([[0, 1234], [5678, 0]], dtype=np.uint16)
        rmask = np.array([[0, FLAG_TARGET_CORE], [FLAG_RECOVERY_ADDED, 0]], dtype=np.uint8)
        state = {"frame_index": 42, "fall_status": "upright", "human_physical_v1": {"status": "ok"}}
        pkt = pack_frame(xyz, flags, rmm, state, intensity=inten, range_mask=rmask, decimation=3, is_live=True)

        script = (
            "import fs from 'node:fs';\n"
            f"import {{ decodeFramePacket }} from {json.dumps(lib_path.as_uri())};\n"
            "const buf = fs.readFileSync(0);\n"
            "const ab = buf.buffer.slice(buf.byteOffset, buf.byteOffset + buf.byteLength);\n"
            "const f = decodeFramePacket(ab);\n"
            "console.log(JSON.stringify({\n"
            "  version: f.version, decimation: f.decimation, isLive: f.isLive,\n"
            "  pointCount: f.pointCount, width: f.rangeWidth, height: f.rangeHeight,\n"
            "  xyz: Array.from(f.xyz), intensity: Array.from(f.intensity),\n"
            "  rangeMm: Array.from(f.rangeMm), pointFlags: Array.from(f.pointFlags),\n"
            "  rangeMask: Array.from(f.rangeMask), state: f.state\n"
            "}));\n"
        )
        proc = subprocess.run(
            ["node", "--input-type=module", "-e", script],
            input=pkt,
            capture_output=True,
            check=True,
        )
        decoded = json.loads(proc.stdout.decode("utf-8"))
        self.assertEqual(decoded["version"], 1)
        self.assertEqual(decoded["decimation"], 3)
        self.assertTrue(decoded["isLive"])
        self.assertEqual(decoded["pointCount"], 2)
        self.assertEqual((decoded["height"], decoded["width"]), (2, 2))
        self.assertEqual(decoded["xyz"], [1.5, -0.25, 0.75, 3.200000047683716, 0.4000000059604645, -0.10000000149011612])
        self.assertEqual(decoded["intensity"], [250.0, 910.0])
        self.assertEqual(decoded["rangeMm"], [0, 1234, 5678, 0])
        self.assertEqual(decoded["pointFlags"], [FLAG_TARGET_CORE, FLAG_RECOVERY_ADDED])
        self.assertEqual(decoded["rangeMask"], [0, FLAG_TARGET_CORE, FLAG_RECOVERY_ADDED, 0])
        self.assertEqual(decoded["state"], state)


if __name__ == "__main__":
    unittest.main()
