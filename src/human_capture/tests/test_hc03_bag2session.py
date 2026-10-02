"""HC-03 X3/X5：抽取损坏兜底 + NaN 过滤记账。

X1/X2/X4/X6/X7 板上已实测；这里只做可移植的纯 Python 兜底断言，不依赖 rosbag。
"""

import json
import os
import shutil
import sys
import tempfile
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
_PKG = os.path.dirname(_HERE)
if _PKG not in sys.path:
    sys.path.insert(0, _PKG)

from core.bag2session import ExtractError, extract, POINT_STRIDE_BYTES


class TestExtractBadInputs(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="hc03_")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_missing_bag_raises_extract_error(self):
        with self.assertRaises(ExtractError) as ctx:
            extract(os.path.join(self.tmp, "nope.bag"),
                    os.path.join(self.tmp, "dest"), "cap_x")
        self.assertIn("bag 不存在", str(ctx.exception))

    def test_corrupt_bag_path_is_not_bag(self):
        # 写一个根本不是 bag 的文件
        fake = os.path.join(self.tmp, "fake.bag")
        with open(fake, "wb") as fh:
            fh.write(b"this is not a rosbag")
        with self.assertRaises(ExtractError):
            extract(fake, os.path.join(self.tmp, "dest"), "cap_fake")


class TestLayoutConstants(unittest.TestCase):
    def test_stride(self):
        self.assertEqual(POINT_STRIDE_BYTES, 28)


class TestExtractSkippedWhenModuleMissing(unittest.TestCase):
    """板上 rosbag 一定在；Windows 单测缺 rosbag 时，extract 起 ExtractError。"""

    def test_rosbag_absent_raises_extract_error(self):
        if self._has_rosbag():
            self.skipTest("本机有 rosbag，跳过此路径")
        with tempfile.TemporaryDirectory() as tmp:
            src = os.path.join(tmp, "x.bag")
            open(src, "wb").write(b"#ROSBAG V2.0\n")
            with self.assertRaises(ExtractError) as ctx:
                extract(src, os.path.join(tmp, "dest"), "cap_x")
            self.assertIn("rosbag", str(ctx.exception).lower())

    @staticmethod
    def _has_rosbag():
        try:
            import rosbag  # noqa: F401
            return True
        except ImportError:
            return False


if __name__ == "__main__":
    unittest.main()
