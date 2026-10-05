#!/usr/bin/env python3
"""Prepare a GL-E02 R1 pending evidence directory from a versioned request."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.ground_evidence import prepare_packet, read_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    try:
        request, sha = read_json(args.request)
        output = Path(args.output).resolve()
        source = Path(args.request).resolve()
        if output == source or output in source.parents:
            raise ValueError("output contains request input")
        result = prepare_packet(request, args.output, Path(__file__).resolve().parents[3])
        print(json.dumps({"request_sha256": sha, "output": args.output,
                          "packet_id": result["packet_id"], "P01": "BLOCKED",
                          "gaps": result["gaps"]}, ensure_ascii=False))
        return 0
    except (ValueError, OSError, KeyError, TypeError, OverflowError) as exc:
        print("ground evidence refused: " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
