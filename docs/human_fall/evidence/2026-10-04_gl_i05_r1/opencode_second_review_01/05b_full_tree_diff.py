"""GL-I05 R1 second review: corrected full tracked+untracked diff.

05_full_tree_and_recording.py walked every file including .gitignore'd ones,
so 215 of its 230 "additions" were gitignored captures/ML files that were never
part of the baseline universe (snapshot.py uses `git ls-files --exclude-standard`
plus three explicit capture paths). This new numbered script reproduces the
baseline's exact file universe and diffs against it, then reports local capture
material with mtimes for E02. Writes only into this review directory.
"""
import hashlib
import json
import os
import subprocess
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
BASELINE = HERE.parent / "00_before_baseline.json"
EXPLICIT = [
    "captures/remote/cap_20261002_163621/meta.json",
    "captures/remote/cap_20261002_163621/points.bin",
    "docs/human_fall/evidence/2026-10-03_gl_i02_r1/08_real/real_candidate.adapted.npz",
]


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def universe():
    out = subprocess.check_output(
        ["git", "ls-files", "-c", "-o", "--exclude-standard", "-z"], cwd=ROOT)
    paths = set(out.decode("utf-8").split("\0")) - {""}
    paths.update(EXPLICIT)
    return paths


def main():
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))["files"]
    paths = universe()
    added, removed, modified, missing, unreadable = [], [], [], [], []
    for rel in sorted(paths):
        path = ROOT / rel
        try:
            is_file = path.is_file()
        except OSError as exc:
            # Windows catkin reparse-point (src/CMakeLists.txt) is a broken
            # symlink; the baseline recorded it as unreadable_winerror, not as
            # a normal file. Match that representation instead of crashing.
            unreadable.append({"file": rel, "winerror": getattr(exc, "winerror", None)})
            continue
        if not is_file:
            missing.append(rel)
            continue
        digest = sha256(path)
        info = baseline.get(rel)
        if info is None:
            added.append(rel)
        elif info.get("sha256") != digest:
            modified.append({"file": rel, "baseline": info.get("sha256"),
                             "actual": digest})
    removed = sorted(set(baseline) - set(paths))

    review_prefix = "docs/human_fall/evidence/2026-10-04_gl_i05_r1/opencode_second_review_01/"
    added_foreign = [n for n in added if not n.startswith(review_prefix)]

    # ignored local capture material with mtimes (E02 bounded audit)
    ignored = subprocess.check_output(
        ["git", "ls-files", "-o", "-i", "--exclude-standard", "-z"], cwd=ROOT)
    ignored_paths = [p for p in ignored.decode("utf-8").split("\0") if p]
    recordings = []
    for rel in ignored_paths:
        if rel.startswith("captures/") or rel.startswith("ML/"):
            full = ROOT / rel
            if full.is_file():
                st = full.stat()
                recordings.append({"path": rel, "size": st.st_size,
                                   "mtime": time.strftime("%Y-%m-%dT%H:%M:%S",
                                                          time.localtime(st.st_mtime))})
    recordings.sort(key=lambda r: r["mtime"])
    new_since_baseline = [r for r in recordings
                          if r["mtime"] >= "2026-10-04T00:00:00"]

    result = {
        "kind": "gli05_second_review_full_tree_diff_corrected",
        "baseline_time": json.loads(BASELINE.read_text(encoding="utf-8"))["time"],
        "universe_size": len(paths),
        "baseline_files": len(baseline),
        "added_count": len(added),
        "added_review_outputs": len(added) - len(added_foreign),
        "added_foreign": added_foreign,
        "removed": removed,
        "modified": modified,
        "missing": missing,
        "unreadable_winerror": unreadable,
        "ignored_capture_files": len(recordings),
        "ignored_capture_earliest": recordings[0] if recordings else None,
        "ignored_capture_latest": recordings[-1] if recordings else None,
        "ignored_captures_mtime_on_or_after_2026_10_04": new_since_baseline,
    }
    with (HERE / "05b_full_tree_diff.json").open("x", encoding="utf-8") as handle:
        json.dump(result, handle, ensure_ascii=False, allow_nan=False, indent=2)
    print(json.dumps({"universe": len(paths), "added": len(added),
                      "added_foreign": added_foreign, "removed": removed,
                      "modified_count": len(modified), "modified": modified[:10],
                      "ignored_capture_files": len(recordings),
                      "latest_capture": recordings[-1] if recordings else None,
                      "new_on_or_after_2026_10_04": len(new_since_baseline)},
                     ensure_ascii=False)[:3000])


if __name__ == "__main__":
    main()
