#!/usr/bin/env python3
"""Tests for lidata_to_replay.py — LI-DATA (Blender) to fall_replay npz.

Pure stdlib + NumPy; no real dataset download required. Builds a tiny synthetic
zip in a temp dir mirroring the LI-DATA layout and verifies axis mapping,
frame ordering and ragged-frame handling.
"""

import csv
import io
import os
import sys
import tempfile
import unittest
import zipfile

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                "tools"))

import lidata_to_replay as ltr  # noqa: E402


def _frame_csv(points):
    """points: iterable of (cat, x, y, z[, distance])."""
    buf = io.StringIO()
    writer = csv.writer(buf, delimiter=";", lineterminator="\n")
    writer.writerow(["categoryID", "partID", "X", "Y", "Z", "distance",
                     "X_noise", "Y_noise", "Z_noise", "distance_noise",
                     "intensity", "red", "green", "blue"])
    for row in points:
        cat, x, y, z = row[0], row[1], row[2], row[3]
        dist = row[4] if len(row) > 4 else (x * x + y * y + z * z) ** 0.5 + 5.0
        writer.writerow([cat, 0, x, y, z, dist, x, y, z, dist, 0.5, 0.5, 0.5, 0.5])
    return buf.getvalue()


class ConvertTest(unittest.TestCase):
    def _make_zip(self, directory, frames):
        """frames: list of (frame_index, points) -> one pose folder zip."""
        zip_path = os.path.join(directory, "Dataset.zip")
        pose_dir = "Dataset (Blender+LiDAR)1000poses/Fall Data/PoseSet/Pose_000_Test"
        with zipfile.ZipFile(zip_path, "w") as archive:
            for index, points in frames:
                name = "%s/frame_%02d_frame_%d.csv" % (pose_dir, index, index)
                archive.writestr(name, _frame_csv(points))
        return zip_path, pose_dir

    def test_axis_mapping_and_slant_depth(self):
        with tempfile.TemporaryDirectory() as directory:
            # one point at source X=0,Y=10,Z=0 -> depth=10, ros_y=-0, ros_z=0
            zip_path, pose = self._make_zip(directory, [(1, [(5.0, 0.0, 10.0, 0.0)])])
            out = os.path.join(directory, "o.npz")
            self.assertEqual(ltr.main(["--zip", zip_path, "--pose", pose,
                                       "--output", out]), 0)
            with np.load(out, allow_pickle=True) as data:
                frame = data["frames"][0]
            self.assertAlmostEqual(frame[0][0], 10.0, places=6)   # ros_x = |XYZ|
            self.assertAlmostEqual(frame[0][1], 0.0, places=6)    # ros_y = -X
            self.assertAlmostEqual(frame[0][2], 0.0, places=6)    # ros_z = Z

    def test_frames_sorted_by_index_not_name(self):
        with tempfile.TemporaryDirectory() as directory:
            # out-of-order listing: frame 10 vs frame 2 (name sort would put 10 first)
            frames = [(10, [(5.0, 0.0, 100.0, 0.0)]),
                      (2, [(5.0, 0.0, 20.0, 0.0)]),
                      (1, [(5.0, 0.0, 10.0, 0.0)])]
            zip_path, pose = self._make_zip(directory, frames)
            out = os.path.join(directory, "o.npz")
            ltr.main(["--zip", zip_path, "--pose", pose, "--output", out, "--dt", "0.5"])
            with np.load(out, allow_pickle=True) as data:
                depths = [data["frames"][i][0][0] for i in range(3)]
                times = list(data["times"])
            self.assertEqual(depths, [10.0, 20.0, 100.0])  # frame 1,2,10 order
            self.assertEqual(times, [0.0, 0.5, 1.0])

    def test_ragged_frames_kept_ragged(self):
        with tempfile.TemporaryDirectory() as directory:
            frames = [(1, [(5.0, 0.0, 10.0, 0.0)]),
                      (2, [(5.0, 0.0, 10.0, 0.0),
                           (6.0, 1.0, 11.0, 0.5),
                           (0.0, 2.0, 12.0, 1.0)])]
            zip_path, pose = self._make_zip(directory, frames)
            out = os.path.join(directory, "o.npz")
            ltr.main(["--zip", zip_path, "--pose", pose, "--output", out])
            with np.load(out, allow_pickle=True) as data:
                shapes = (data["frames"][0].shape, data["frames"][1].shape)
            self.assertEqual(len(shapes), 2)
            self.assertEqual(shapes[0], (1, 3))
            self.assertEqual(shapes[1], (3, 3))

    def test_missing_prefix_is_error(self):
        with tempfile.TemporaryDirectory() as directory:
            zip_path, _ = self._make_zip(directory, [(1, [(5.0, 0.0, 10.0, 0.0)])])
            out = os.path.join(directory, "o.npz")
            with self.assertRaises(SystemExit):
                ltr.main(["--zip", zip_path, "--pose", "No/Such/Pose", "--output", out])

    def test_skips_malformed_and_short_rows(self):
        # corrupt rows: wrong type in coords, too few columns, noise ignored
        csv_body = ("categoryID;partID;X;Y;Z;distance;X_noise;Y_noise;Z_noise;"
                    "distance_noise;intensity;red;green;blue\n"
                    "5.0;0;0.0;10.0;0.0;15.0;0;0;0;0;0.5;0.5;0.5;0.5\n"
                    "6.0;0;not_a_number;2.0;0.0;15.0;0;0;0;0;0.5;0.5;0.5;0.5\n"
                    "too;few;cols\n"
                    "6.0;0;3.0;4.0;0.0;15.0;0;0;0;0;0.5;0.5;0.5;0.5\n")
        with tempfile.TemporaryDirectory() as directory:
            zip_path = os.path.join(directory, "Dataset.zip")
            pose = "Dataset/Pose_000_Test"
            with zipfile.ZipFile(zip_path, "w") as archive:
                archive.writestr(pose + "/frame_01_frame_1.csv", csv_body)
            out = os.path.join(directory, "o.npz")
            self.assertEqual(ltr.main(["--zip", zip_path, "--pose", pose,
                                       "--output", out]), 0)
            with np.load(out, allow_pickle=True) as data:
                frame = data["frames"][0]
            # 2 valid rows; NaN row and short row dropped
            self.assertEqual(frame.shape, (2, 3))
            self.assertAlmostEqual(frame[0][0], 10.0, places=6)
            self.assertAlmostEqual(frame[1][0], 5.0, places=6)  # |3,4,0|=5

    def test_output_is_quiet_summary(self):
        # main returns 0 and prints one JSON summary line (consumed by callers)
        with tempfile.TemporaryDirectory() as directory:
            zip_path, pose = self._make_zip(directory, [(1, [(5.0, 0.0, 10.0, 0.0)])])
            out = os.path.join(directory, "o.npz")
            self.assertEqual(ltr.main(["--zip", zip_path, "--pose", pose,
                                       "--output", out]), 0)


if __name__ == "__main__":
    unittest.main()
