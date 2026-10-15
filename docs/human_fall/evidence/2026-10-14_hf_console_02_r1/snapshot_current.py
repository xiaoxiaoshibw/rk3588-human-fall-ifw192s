import hashlib
import json
import os
import subprocess
from pathlib import Path


OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
EXCLUDED = OUT.relative_to(ROOT).as_posix()
PRIOR = ROOT / "docs/human_fall/evidence/2026-10-14_hf_real_close_data_bg_r1"


def sha(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def git(*args):
    return subprocess.check_output(["git", *args], cwd=str(ROOT))


prior = json.loads((PRIOR / "BASELINE_BEFORE.json").read_text(encoding="utf-8"))
files = dict(prior["files"])
changed = []
deleted = []
diff = git("diff", "--name-status", "--no-renames", "HEAD").decode("utf-8", "surrogateescape")
for line in diff.splitlines():
    if not line:
        continue
    state, rel = line.split("\t", 1)
    rel = rel.replace("\\", "/")
    if rel == EXCLUDED or rel.startswith(EXCLUDED + "/"):
        continue
    absolute = ROOT / rel
    if state.startswith("D") or not absolute.is_file():
        files.pop(rel, None)
        deleted.append(rel)
    else:
        files[rel] = sha(absolute)
        changed.append(rel)

# Add only untracked files absent from the inherited complete snapshot. Existing
# untracked entries retain their baseline digest; the prior preservation audit's
# exact deltas are rehashed below.
untracked = git("ls-files", "--others", "--exclude-standard", "-z").split(b"\0")
added = []
for raw in untracked:
    if not raw:
        continue
    rel = os.fsdecode(raw).replace("\\", "/")
    if rel == EXCLUDED or rel.startswith(EXCLUDED + "/"):
        continue
    absolute = ROOT / rel
    if absolute.is_file() and rel not in files:
        files[rel] = sha(absolute)
        added.append(rel)

preservation = json.loads((PRIOR / "PRESERVATION_CHECK.json").read_text(encoding="utf-8"))
for change in preservation.get("changes", []):
    rel = change["path"]
    absolute = ROOT / rel
    if absolute.is_file():
        files[rel] = sha(absolute)

payload = {
    "branch": git("rev-parse", "--abbrev-ref", "HEAD").decode().strip(),
    "head": git("rev-parse", "HEAD").decode().strip(),
    "file_count": len(files),
    "read_errors": [],
    "non_atomic": True,
    "method": "complete prior full-tree SHA map plus current tracked diffs, newly untracked paths, and prior audit deltas; excluded this evidence directory",
    "prior_full_snapshot": "../hf_real_close_data_bg_r1/BASELINE_BEFORE.json",
    "tracked_overlay_count": len(set(changed)),
    "new_untracked_count": len(set(added)),
    "deleted_count": len(set(deleted)),
    "files": dict(sorted(files.items())),
}
with (OUT / "BASELINE_BEFORE.json").open("x", encoding="utf-8") as stream:
    json.dump(payload, stream, ensure_ascii=False, separators=(",", ":"))
    stream.write("\n")
print(json.dumps({"branch": payload["branch"], "head": payload["head"],
                  "file_count": payload["file_count"],
                  "tracked_overlay_count": payload["tracked_overlay_count"],
                  "new_untracked_count": payload["new_untracked_count"],
                  "deleted_count": payload["deleted_count"]}))
