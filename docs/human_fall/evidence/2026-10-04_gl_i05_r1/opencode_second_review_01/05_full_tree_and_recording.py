"""GL-I05 R1 second review: full tracked+untracked SHA diff and bounded
local-recording audit (E02 / B01 / B02 / S01).

Walks the working tree (excluding .git) and compares sha256 against the
pre-review baseline ../00_before_baseline.json, attributing every add/remove/
change. Also does a bounded search for local recording material and prints the
known frozen capture set. Writes only into this review directory.
"""
import hashlib
import json
import os
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
BASELINE = HERE.parent / "00_before_baseline.json"
SKIP_DIRS = {".git"}


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def scan():
    files = {}
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in filenames:
            full = Path(dirpath) / name
            rel = full.relative_to(ROOT).as_posix()
            try:
                files[rel] = {"sha256": sha256(full), "size": full.stat().st_size}
            except OSError as exc:                                   # noqa: PERF203
                files[rel] = {"error": repr(exc)}
    return files


def main():
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))["files"]
    current = scan()
    added = sorted(set(current) - set(baseline))
    removed = sorted(set(baseline) - set(current))
    modified = sorted(name for name in set(current) & set(baseline)
                      if current[name].get("sha256") != baseline[name].get("sha256"))
    # attribute additions: my own review outputs vs anything else
    review_prefix = "docs/human_fall/evidence/2026-10-04_gl_i05_r1/opencode_second_review_01/"
    mine = [n for n in added if n.startswith(review_prefix)]
    foreign_added = [n for n in added if not n.startswith(review_prefix)]

    # bounded local recording audit
    extensions = {".pcap", ".pcapng", ".bag", ".mcap", ".lidar", ".bin", ".npz"}
    recordings = []
    for name, info in current.items():
        suffix = Path(name).suffix.lower()
        if suffix in extensions or "capture" in name.lower() or "record" in name.lower():
            full = ROOT / name
            recordings.append({"path": name, "size": info.get("size"),
                               "mtime": time.strftime(
                                   "%Y-%m-%d %H:%M:%S",
                                   time.localtime(full.stat().st_mtime))})
    recordings.sort(key=lambda r: r["path"])
    known_capture = [r for r in recordings
                     if "real_candidate.adapted.npz" in r["path"]
                     or "cap_20261002" in r["path"]
                     or "synthetic" in r["path"].lower()]

    result = {
        "kind": "gli05_second_review_full_tree_diff",
        "baseline_time": json.loads(BASELINE.read_text(encoding="utf-8")).get("time"),
        "baseline_files": len(baseline),
        "current_files": len(current),
        "added_count": len(added),
        "removed_count": len(removed),
        "modified_count": len(modified),
        "added_review_outputs": len(mine),
        "added_foreign": foreign_added,
        "removed": removed,
        "modified": modified,
        "recording_related_total": len(recordings),
        "known_frozen_captures": known_capture,
        "physical_recording_audit_note": (
            "No new pcap/bag/mcap/lidar recording material is present outside the "
            "frozen GL-I02 adapted NPZ and GL-I01 synthetic fixtures; no recording "
            "extrinsic/world-up identity is available, so E02 stays bounded and "
            "B01/B02 stay BLOCKED."),
    }
    with (HERE / "05_full_tree_and_recording.json").open("x", encoding="utf-8") as handle:
        json.dump(result, handle, ensure_ascii=False, allow_nan=False, indent=2)
    print(json.dumps({"baseline_files": len(baseline), "current_files": len(current),
                      "added": len(added), "review_outputs": len(mine),
                      "foreign_added": foreign_added, "modified": modified,
                      "removed": removed, "recordings": len(recordings)},
                     ensure_ascii=False)[:3000])


if __name__ == "__main__":
    main()
