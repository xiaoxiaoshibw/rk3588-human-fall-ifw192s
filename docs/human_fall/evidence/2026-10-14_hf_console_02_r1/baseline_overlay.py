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
    return subprocess.check_output(["git", *args], cwd=str(ROOT)).decode().strip()


prior = json.loads((PRIOR / "BASELINE_BEFORE.json").read_text(encoding="utf-8"))
files = dict(prior["files"])
current_paths = set()
for current, dirs, names in os.walk(str(ROOT), topdown=True):
    rel_dir = Path(current).relative_to(ROOT).as_posix()
    dirs[:] = sorted(name for name in dirs if name != ".git"
                     and not (Path(current) / name).is_symlink()
                     and (rel_dir == "." or not rel_dir.startswith(EXCLUDED)))
    for name in names:
        path = Path(current) / name
        if path.is_symlink():
            continue
        rel = path.relative_to(ROOT).as_posix()
        if rel == EXCLUDED or rel.startswith(EXCLUDED + "/"):
            continue
        current_paths.add(rel)
files = {path: digest for path, digest in files.items() if path in current_paths}

changed = []
status = subprocess.check_output(
    ["git", "status", "--porcelain=v1", "-z", "--untracked-files=all"], cwd=str(ROOT)
)
for record in status.split(b"\0"):
    if not record:
        continue
    state, raw_path = record[:2].decode("ascii", "replace"), record[3:]
    path = os.fsdecode(raw_path).replace("\\", "/")
    if "D" in state and not Path(ROOT / path).exists():
        files.pop(path, None)
        continue
    absolute = ROOT / path
    if absolute.is_file() and path not in (EXCLUDED,):
        files[path] = sha(absolute)
        changed.append(path)

# Reapply the prior audit's known external/ignored-file changes if still present.
preservation = json.loads((PRIOR / "PRESERVATION_CHECK.json").read_text(encoding="utf-8"))
for change in preservation.get("changes", []):
    path = change["path"]
    absolute = ROOT / path
    if absolute.is_file():
        files[path] = sha(absolute)

payload = {
    "branch": git("rev-parse", "--abbrev-ref", "HEAD"),
    "head": git("rev-parse", "HEAD"),
    "file_count": len(files),
    "read_errors": [],
    "non_atomic": True,
    "method": "reused previous complete all-file SHA map, removed absent paths, and overlaid all current git-status paths plus prior audit's known external/ignored changes",
    "prior_full_snapshot": "../hf_real_close_data_bg_r1/BASELINE_BEFORE.json",
    "overlay_path_count": len(set(changed)),
    "files": dict(sorted(files.items())),
}
with (OUT / "BASELINE_BEFORE.json").open("x", encoding="utf-8") as stream:
    json.dump(payload, stream, ensure_ascii=False, separators=(",", ":"))
    stream.write("\n")
print(json.dumps({"branch": payload["branch"], "head": payload["head"],
                  "file_count": payload["file_count"],
                  "overlay_path_count": payload["overlay_path_count"]}))
