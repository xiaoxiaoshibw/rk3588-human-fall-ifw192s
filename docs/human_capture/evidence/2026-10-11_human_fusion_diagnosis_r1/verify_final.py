"""Input/snapshot/link integrity only; does not rerun detection or edit any input."""
import hashlib
import json
import re
from pathlib import Path

out = Path(__file__).resolve().parent
root = out.parents[3]

def sha(path):
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()

checks = []
for row in json.loads((out / "data_audit.json").read_text(encoding="utf-8"))["sessions"]:
    gt = Path(row["gt_path"])
    for path, expected in [
        (gt, row["gt_sha256"]),
        (gt.parent / "manifest.json", row["manifest_sha256"]),
        (root / "captures/remote" / row["sid"] / "meta.json", row["input_sha256"]["meta"]),
        (root / "captures/remote" / row["sid"] / "points.bin", row["input_sha256"]["points"]),
    ]:
        actual = sha(path)
        checks.append({"path": str(path), "before": expected, "after": actual, "unchanged": actual == expected})

snapshots = []
for source, row in json.loads((out / "snapshot_manifest.json").read_text(encoding="utf-8")).items():
    copy = out / row["snapshot"]
    snapshots.append({"source": source, "snapshot": str(copy), "expected": row["sha256"],
        "copy_unchanged": sha(copy) == row["sha256"], "live_source_unchanged": sha(root / source) == row["sha256"]})

missing = []
links = 0
for name in ["REPORT.md", "RESEARCH_NOTES.md", "CLAUDE_TASKBOOK.md", "INTEGRITY.md"]:
    text = (out / name).read_text(encoding="utf-8")
    for target in re.findall(r"\]\(([^)]+)\)", text):
        if target.startswith(("https:", "http:", "#")):
            continue
        cleaned = re.sub(r":\d+$", "", target)
        path = Path(cleaned) if re.match(r"^[A-Z]:/", cleaned) else out / cleaned
        links += 1
        if not path.exists():
            missing.append({"document": name, "target": target})

result = {"input_hash_checks": checks, "snapshot_checks": snapshots, "local_links_checked": links,
          "missing_local_links": missing, "limits": "Hash checks prove content identity only; no new semantic annotation, physical experiment, or browser test."}
with (out / "final_integrity.json").open("x", encoding="utf-8") as handle:
    json.dump(result, handle, ensure_ascii=False, indent=2)
print(json.dumps({"inputs": len(checks), "input_changed": [r["path"] for r in checks if not r["unchanged"]],
    "copies_changed": [r["snapshot"] for r in snapshots if not r["copy_unchanged"]],
    "live_sources_changed": [r["source"] for r in snapshots if not r["live_source_unchanged"]],
    "links_checked": links, "missing": missing}, ensure_ascii=False))
assert all(r["unchanged"] for r in checks)
assert all(r["copy_unchanged"] for r in snapshots)
assert not missing
