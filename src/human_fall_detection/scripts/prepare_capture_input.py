#!/usr/bin/env python3
"""Prepare a traceable numeric NPZ from an existing capture export (GL-I01).

Read-only over ``--source-dir`` (fixed ``meta.json`` + ``points.bin``). Writes a
single immutable adapted NPZ (``points`` + scalar Unicode ``input_manifest``)
via an atomic exclusive hard-link publish. No ground fit, no ROI, no unit or
installation claim is made here.
"""

import argparse
import json
import os
import sys

PACKAGE_DIR = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                           os.pardir))
if PACKAGE_DIR not in sys.path:
    sys.path.insert(0, PACKAGE_DIR)

from core.capture_input import CaptureInputError, prepare_npz


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", required=True,
                        help="existing capture export dir (meta.json + points.bin)")
    parser.add_argument("--frame", required=True,
                        help="declared frame id; must match the source meta")
    parser.add_argument("--units", required=True,
                        help="declared length unit; only 'm' is accepted")
    parser.add_argument("--output", required=True, help="new adapted NPZ path")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    try:
        manifest = prepare_npz(args.source_dir, args.frame, args.units,
                               args.output)
    except CaptureInputError as exc:
        print("capture input refused: " + str(exc), file=sys.stderr)
        return 2
    summary = {
        "output": args.output,
        "points": manifest["points"]["shape"][0],
        "frames": len(manifest["frames"]),
        "frame": manifest["declared"]["frame"],
        "units": manifest["declared"]["units"],
        "time_domain": manifest["declared"]["time_domain"],
        "bin_sha256": manifest["source"]["bin_sha256"],
        "points_sha256": manifest["points"]["sha256"],
        "point_index_domain": manifest["provenance"]["point_index_domain"],
        "physical_verified": manifest["provenance"]["physical_verified"],
    }
    print(json.dumps(summary, allow_nan=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
