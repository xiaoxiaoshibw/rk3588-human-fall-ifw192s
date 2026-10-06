"""GL-S02 golden: 223757 v3 succeeds; frozen v2 still fails on the same data."""
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "pc_apps" / "human_replay"))

import numpy as np  # noqa: E402
from floor_roi import detect_floor_regions_v3  # noqa: E402
from floor_sheet import detect_floor_regions_v2  # noqa: E402

SID = "cap_20261002_223757"
OUT = Path(__file__).resolve().parent


def load_fit():
    directory = ROOT / "captures" / "remote" / SID
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
    began = time.monotonic()
    points, ids = load_fit()
    record = {"sid": SID, "fit_points": int(len(points)), "fit_frames": int(len(np.unique(ids)))}

    try:
        detect_floor_regions_v2(points, ids, 26., 0.)
        record["v2_result"] = "unexpected_success"
    except ValueError as exc:
        record["v2_result"] = str(exc)

    result = detect_floor_regions_v3(points, ids, 26., 0.)
    candidate = result["candidate"]
    record["v3_regions"] = result["regions"]
    record["v3_kind"] = candidate["kind"]
    record["v3_roi"] = candidate["roi"]
    record["v3_selected_cells"] = candidate["selected_cells"]
    record["v3_sheet"] = {k: v for k, v in candidate["sheet"].items() if k != "gap_pairs"}
    record["seconds"] = round(time.monotonic() - began, 2)

    roi = candidate["roi"]
    record["checks"] = {
        "kind_v3": candidate["kind"] == "lowest_floor_sheet_v3_fine_roi",
        "min_sep_ok": roi["min_sep_m"] >= .5,
        "independent_4": roi["independent_count"] == 4,
        "condition_ok": roi["condition"] >= .1,
        "v2_still_insufficient": str(record["v2_result"]).startswith("INSUFFICIENT_CLEAN_ROI_SUPPORT"),
        "full_height": candidate["full_height_preserved"] is True,
        "no_manual": candidate["uses_manual_reference"] is False,
    }
    record["pass"] = all(record["checks"].values())
    (OUT / "05_golden_223757.json").write_text(json.dumps(record, ensure_ascii=False, indent=1),
                                               encoding="utf-8")
    print(json.dumps(record, ensure_ascii=False, indent=1), flush=True)


if __name__ == "__main__":
    main()
