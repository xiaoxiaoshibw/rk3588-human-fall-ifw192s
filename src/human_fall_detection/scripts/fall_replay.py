#!/usr/bin/env python3
"""Deterministic offline replay of the HF-04..06 geometry/fall chain. Read-only.

Runs on a numeric frame recording (.npz with ``frames`` or a single ``points``
array plus an optional ``times`` vector) and an optional HF-03 geometry
artifact. No ROS, no network, no device, no vehicle command. Output is strict
JSON, so the same input replays byte-identically.
"""

import argparse
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                "scripts"))

from core.pipeline import ReplayPipeline  # noqa: E402
from sensor_health import dumps_strict, load_config, save_json  # noqa: E402

KIND = "fall_replay"
SCHEMA_VERSION = 1


def _load_ground(path):
    if path is None:
        return None
    with open(path, encoding="utf-8") as handle:
        artifact = json.load(handle)
    if isinstance(artifact, dict) and "ground" in artifact:
        return artifact["ground"]
    return artifact


def _load_frames(path):
    data = np.load(path, allow_pickle=True)
    if "frames" in data:
        frames = data["frames"]
        if frames.dtype == object:
            # ragged per-frame clouds (e.g. LI-DATA converted scans); keep as list
            frames = [np.asarray(f, dtype=np.float64) for f in frames]
        else:
            frames = np.asarray(frames, dtype=np.float64)
    elif "points" in data:
        frames = np.asarray(data["points"], dtype=np.float64)[None, ...]
    else:
        raise ValueError("npz must contain 'frames' or 'points'")
    times = np.asarray(data["times"], dtype=np.float64) if "times" in data else None
    if times is not None and len(times) != len(frames):
        raise ValueError("times length must match frames")
    return frames, times


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frames", required=True, help=".npz with frames/points and optional times")
    parser.add_argument("--ground", default=None, help="optional geometry-calibration JSON")
    parser.add_argument("--baseline", default=None, help="optional target stance baseline JSON")
    parser.add_argument("--config", default=None, help="perception.yaml sections")
    parser.add_argument("--session-id", default="fall_replay")
    parser.add_argument("--epoch", type=int, default=0)
    parser.add_argument("--select-candidate", default=None,
                        help="explicit initial candidate_id (operator-style)")
    parser.add_argument("--auto-select", action="store_true",
                        help="TEST FIXTURE ONLY: auto-lock the largest first-frame candidate")
    parser.add_argument("--output", default=None)
    args = parser.parse_args(argv)

    settings = load_config(args.config) if args.config else {}
    baseline = None
    if args.baseline:
        with open(args.baseline, encoding="utf-8") as handle:
            baseline = json.load(handle)
    frames, times = _load_frames(args.frames)
    pipeline = ReplayPipeline(args.session_id, settings, baseline=baseline,
                              auto_select=args.auto_select,
                              initial_candidate_id=args.select_candidate)
    pipeline.ground = _load_ground(args.ground)
    outputs = pipeline.run(frames, times, args.epoch)
    report = {"kind": KIND, "schema_version": SCHEMA_VERSION,
              "session_id": args.session_id, "frame_count": int(len(frames)),
              "ground_available": pipeline.ground is not None,
              "selection_source": pipeline.initial_selection_source,
              "outputs": outputs}
    text = dumps_strict(report)
    if args.output:
        save_json(args.output, report)
        print("wrote " + os.path.abspath(args.output))
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
