# -*- coding: utf-8 -*-
"""lidata_load.py — 以流式方式遍历 LI-DATA zip, 按帧返回 (xyz_intensity (N,4), label)。

不开启 zip 到磁盘。65535 个成员全部在内存中 unzip 时大概占 3-5 GB, 不划算。
stride 参数用于抽帧：**不靠 stride 切数据完整性**， 只用于跑得快的 smoke test。
"""
import io
import re
import zipfile
from collections import Counter, defaultdict

import numpy as np

ZIP_PATH = r"D:\Code\ldiar\ML\LI-DATA\Dataset (Blender+LiDAR)1000poses.zip"

LABEL_FALL = 1
LABEL_NO_FALL = 0

# 用 ``label_from_path`` 把每个 csv 路径映射成 0/1
_FALL_RE = re.compile(r"/Fall Data ", re.IGNORECASE)
_NOFALL_RE = re.compile(r"/No Fall Data ", re.IGNORECASE)


def label_from_path(name):
    """返回 LABEL_FALL / LABEL_NO_FALL / None （非 csv 或不在两类目录下）"""
    if not name.lower().endswith(".csv"):
        return None
    if _FALL_RE.search(name):
        return LABEL_FALL
    if _NOFALL_RE.search(name):
        return LABEL_NO_FALL
    return None


def parse_csv_bytes(buf):
    """一个 csv 文本 → (xyz, intensity) 数组 (N,4). 用 ; 分隔。"""
    rows = []
    header_skipped = False
    for line in buf.decode("utf-8", errors="ignore").splitlines():
        if not line or ";" not in line:
            continue
        if not header_skipped:
            header_skipped = True
            continue
        parts = line.split(";")
        if len(parts) < 11:
            continue
        try:
            # X, Y, Z 在第 2..4 列 （零索引）
            x = float(parts[2]); y = float(parts[3]); z = float(parts[4])
            intensity = float(parts[10])
        except (ValueError, IndexError):
            continue
        rows.append((x, y, z, intensity))
    if not rows:
        return np.zeros((0, 4), dtype=np.float32)
    return np.asarray(rows, dtype=np.float32)


class LidarDataLoader:
    """遍历 zip 里全部 csv 的 lazy loader. 不重复读 zip."""

    def __init__(self, zip_path=ZIP_PATH, max_frames_per_class=None, rng_seed=0):
        self.zip_path = zip_path
        self.max_frames_per_class = max_frames_per_class
        self.rng = np.random.default_rng(rng_seed)
        self._z = zipfile.ZipFile(zip_path)

    def list_frames(self):
        """列出 (zip_path_member, class_label) 完整清单， 不读笛内容。"""
        cnt = Counter()
        for n in self._z.namelist():
            lab = label_from_path(n)
            if lab is None:
                continue
            cnt[lab] += 1
        out = []
        remaining = dict(self.max_frames_per_class) if isinstance(self.max_frames_per_class, dict) else None
        for n in self._z.namelist():
            lab = label_from_path(n)
            if lab is None:
                continue
            if remaining is not None and remaining.get(lab, 0) <= 0:
                continue
            out.append((n, lab))
            if remaining is not None:
                remaining[lab] -= 1
        self.rng.shuffle(out)
        return out

    def read_frame(self, path_in_zip):
        """读一帧 → (xyz_intensity (N,4))"""
        with self._z.open(path_in_zip) as fh:
            return parse_csv_bytes(fh.read())

    def iter_frames(self, label_filter=None, max_frames=None):
        """生成器， 按需 yield (xyz_intensity, label, path)"""
        frames = self.list_frames()
        n_yield = 0
        for path, lab in frames:
            if label_filter is not None and lab != label_filter:
                continue
            if max_frames is not None and n_yield >= max_frames:
                break
            xyz = self.read_frame(path)
            n_yield += 1
            yield xyz, lab, path

    def close(self):
        self._z.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


def scan_summary(zip_path=ZIP_PATH):
    """跑一次汇总：总数 / fall / nofall / 平均点数 / 最大最小点数"""
    loader = LidarDataLoader(zip_path)
    pts = []
    n_fall = 0
    n_nofall = 0
    for xyz, lab, _ in loader.iter_frames():
        if lab == LABEL_FALL:
            n_fall += 1
        else:
            n_nofall += 1
        pts.append(len(xyz))
    loader.close()
    return {
        "frames_fall": n_fall,
        "frames_nofall": n_nofall,
        "total": n_fall + n_nofall,
        "pts_mean": float(np.mean(pts)),
        "pts_min": int(np.min(pts)),
        "pts_max": int(np.max(pts)),
    }


if __name__ == "__main__":
    print(scan_summary())
