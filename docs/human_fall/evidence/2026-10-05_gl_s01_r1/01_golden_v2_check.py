"""GL-S01 real-data check: production v2 entry on 223757 + three in-scope sessions."""
import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "pc_apps" / "human_replay"))

from floor_detector import detect_floor_regions  # noqa: E402
from floor_sheet import detect_floor_regions_v2  # noqa: E402

SIDS = ("cap_20261002_223757", "cap_20261004_203349",
        "cap_20261004_203135", "cap_20261004_202456")
GOLDEN = "cap_20261002_223757"
OUT = Path(__file__).resolve().parent


def load_fit(sid):
    directory = ROOT / "captures" / "remote" / sid
    meta = json.loads((directory / "meta.json").read_text(encoding="utf-8"))
    raw = np.memmap(directory / "points.bin", dtype="u1", mode="r")
    xyz = np.ndarray((meta["total_points"], 3), dtype="<f4", buffer=raw, strides=(28, 4))
    frames = meta["frames"]
    nframes = len(frames)
    excluded = {(nframes - 1) // 3, 2 * (nframes - 1) // 3, nframes - 1}
    chunks, ids = [], []
    for ordinal, frame in enumerate(frames):
        if ordinal in excluded:
            continue
        lo, count = frame["offset_points"], frame["count_points"]
        segment = xyz[lo:lo + count].astype("f8")
        valid = np.isfinite(segment).all(axis=1) & np.any(segment != 0, axis=1)
        chunks.append(segment[valid])
        ids.append(np.full(int(valid.sum()), ordinal, dtype="i4"))
    return np.concatenate(chunks), np.concatenate(ids)


def main():
    results = []
    for sid in SIDS:
        began = time.monotonic()
        points, ids = load_fit(sid)
        entry = {"sid": sid, "fit_points": int(len(points))}
        v1 = v2 = None
        v1_error = v2_error = None
        try:
            v1 = detect_floor_regions(points, ids, 26., 0.)
        except ValueError as exc:
            v1_error = str(exc)
        try:
            v2 = detect_floor_regions_v2(points, ids, 26., 0.)
        except ValueError as exc:
            v2_error = str(exc)
        entry.update(v1_error=v1_error, v2_error=v2_error)
        if sid == GOLDEN:
            entry["expected"] = "v1 floor_regions_invalid -> v2 INSUFFICIENT_CLEAN_ROI_SUPPORT"
            entry["pass"] = bool(v1_error and v1_error.startswith("floor_regions_invalid")
                                 and v2_error and v2_error.startswith("INSUFFICIENT_CLEAN_ROI_SUPPORT"))
        else:
            entry["expected"] = "v2 returns v1 verbatim"
            entry["kind"] = v2["candidate"]["kind"] if v2 else None
            entry["pass"] = bool(v2_error is None and v1 is not None
                                 and v1["regions"] == v2["regions"]
                                 and v1["candidate"] == v2["candidate"])
        entry["seconds"] = round(time.monotonic() - began, 2)
        print("%s pass=%s %s" % (sid, entry["pass"],
                                 entry.get("v2_error") or entry.get("kind")), flush=True)
        results.append(entry)
    (OUT / "03_golden_v2.json").write_text(json.dumps(results, ensure_ascii=False, indent=1),
                                           encoding="utf-8")
    text = "\n".join(json.dumps(entry, ensure_ascii=False) for entry in results)
    (OUT / "02_golden_v2.log").write_text(text + "\n", encoding="utf-8")
    if not all(entry["pass"] for entry in results):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
