#!/usr/bin/env python3
"""GL-00 R2: layout / endianness / illegal-point / source-index check (read-only).

Validates the PointCloud2 decode assumptions against the real bag:
  - field layout, point_step/row_step/data length consistency, is_bigendian
  - header stamp == first point timestamp (proves the offset-18 float64 decode)
  - little-endian vs big-endian read of the first x value
  - zero ("black hole") / non-finite counts on sampled frames
  - source-index reproducibility: same (frame seq, in-frame index) decodes to
    the same XYZ on a second pass, so exported ROI indices are replayable.
Writes only the requested JSON. usage:
  python3 gl00_r2_layout_check.py BAG OUT_JSON
"""
import json
import sys

import numpy as np
import rosbag

TOPIC = "/innolidar_points"
DT_XYZ = np.dtype({"names": ["x", "y", "z"],
                   "formats": ["<f4", "<f4", "<f4"],
                   "offsets": [0, 4, 8], "itemsize": 26})
DT_TS = np.dtype({"names": ["ts"], "formats": ["<f8"],
                  "offsets": [18], "itemsize": 26})
DATATYPE_NAMES = {1: "int8", 2: "uint8", 3: "int16", 4: "uint16", 5: "int32",
                  6: "uint32", 7: "float32", 8: "float64"}


def frame_stats(msg):
    arr = np.frombuffer(msg.data, dtype=DT_XYZ)
    xyz = np.column_stack((arr["x"], arr["y"], arr["z"]))
    finite = np.isfinite(xyz).all(axis=1)
    zero = np.abs(xyz).sum(axis=1) == 0.0
    ts = np.frombuffer(msg.data, dtype=DT_TS)["ts"]
    return xyz, finite, zero, ts


def main():
    bag_path, out_json = sys.argv[1], sys.argv[2]
    out = {"bag": bag_path, "topic": TOPIC}
    with rosbag.Bag(bag_path, "r") as bag:
        first = None
        sampled = []
        frames_seen = 0
        for _, msg, _ in bag.read_messages(topics=[TOPIC]):
            frames_seen += 1
            if first is None:
                first = msg
            if frames_seen in (1, 23, 47):
                xyz, finite, zero, ts = frame_stats(msg)
                sampled.append({
                    "seq": int(msg.header.seq),
                    "stamp_s": msg.header.stamp.secs + msg.header.stamp.nsecs * 1e-9,
                    "point_count": int(len(xyz)),
                    "finite_count": int(finite.sum()),
                    "nonfinite_count": int((~finite).sum()),
                    "zero_count": int(zero.sum()),
                    "zero_intensity_mean": float(np.frombuffer(
                        msg.data, dtype=np.dtype({"names": ["i"], "formats": ["<f4"],
                                                  "offsets": [12], "itemsize": 26}))["i"][zero].mean())
                    if zero.any() else None,
                    "header_equals_first_point_ts": bool(
                        abs((msg.header.stamp.secs + msg.header.stamp.nsecs * 1e-9)
                            - float(ts[0])) < 1e-6),
                    "ts_first_s": float(ts[0]), "ts_last_s": float(ts[-1]),
                })

        out["frames_seen"] = frames_seen
        out["fields"] = [[f.name, f.offset, DATATYPE_NAMES.get(f.datatype, str(f.datatype)),
                          f.datatype] for f in first.fields]
        out["point_step"] = first.point_step
        out["row_step"] = first.row_step
        out["width"] = first.width
        out["height"] = first.height
        out["is_bigendian"] = bool(first.is_bigendian)
        out["is_dense"] = bool(first.is_dense)
        out["data_bytes"] = len(first.data)
        out["data_bytes_expected_row_step_x_height"] = first.row_step * first.height
        out["layout_consistent"] = len(first.data) == first.row_step * first.height
        first_x_le = float(np.frombuffer(first.data[0:4], dtype="<f4")[0])
        first_x_be = float(np.frombuffer(first.data[0:4], dtype=">f4")[0])
        out["first_point_x_little_endian"] = first_x_le
        out["first_point_x_big_endian_if_misread"] = first_x_be
        out["first_point_is_zero_return"] = bool(abs(first_x_le) < 1e-9)
        # Endianness probe on a known non-zero return (index 40000, offset 40000*26).
        nz = 26 * 40000
        out["probe_nonzero_index"] = 40000
        out["probe_nonzero_x_le"] = float(np.frombuffer(first.data[nz:nz + 4], dtype="<f4")[0])
        out["probe_nonzero_x_be"] = float(np.frombuffer(first.data[nz:nz + 4], dtype=">f4")[0])
        out["little_endian_read_is_plausible"] = bool(
            abs(out["probe_nonzero_x_le"]) < 100.0 and not (abs(out["probe_nonzero_x_be"]) < 100.0))
        out["sampled_frames"] = sampled

    # source-index reproducibility: pick a frame + fixed indices, decode twice
    target_seq = sampled[0]["seq"]
    probe_indices = [0, 1, 2, 100, 1000, 40000]
    reads = []
    for _pass in range(2):
        with rosbag.Bag(bag_path, "r") as bag:
            for _, msg, _ in bag.read_messages(topics=[TOPIC]):
                if int(msg.header.seq) != target_seq:
                    continue
                arr = np.frombuffer(msg.data, dtype=DT_XYZ)
                xyz = np.column_stack((arr["x"], arr["y"], arr["z"]))
                reads.append({str(i): [float(v) for v in xyz[i]] for i in probe_indices})
                break
    out["source_index_probe_seq"] = target_seq
    out["source_index_probe_indices"] = probe_indices
    out["source_index_pass1"] = reads[0] if reads else None
    out["source_index_pass2"] = reads[1] if len(reads) > 1 else None
    out["source_index_reproducible"] = bool(len(reads) == 2 and reads[0] == reads[1])

    with open(out_json, "w") as handle:
        json.dump(out, handle, indent=1, sort_keys=True)
    print(json.dumps(out, indent=1, sort_keys=True))


if __name__ == "__main__":
    main()
