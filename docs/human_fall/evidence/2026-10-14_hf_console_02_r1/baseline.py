import hashlib
import json
import os
import subprocess
from pathlib import Path


OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
EXCLUDED = OUT.relative_to(ROOT).as_posix()


def git_value(*args):
    result = subprocess.run(
        ["git", *args], cwd=str(ROOT), check=True, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, text=True,
    )
    return result.stdout.strip()


files = []
errors = []
for current, dirs, names in os.walk(str(ROOT), topdown=True):
    rel_dir = Path(current).relative_to(ROOT).as_posix()
    dirs[:] = sorted(
        name for name in dirs
        if name != ".git" and not (Path(current) / name).is_symlink()
        and (rel_dir == "." or not rel_dir.startswith(EXCLUDED))
    )
    for name in sorted(names):
        path = Path(current) / name
        rel = path.relative_to(ROOT).as_posix()
        if rel == EXCLUDED or rel.startswith(EXCLUDED + "/") or path.is_symlink():
            continue
        try:
            digest = hashlib.sha256()
            with path.open("rb") as stream:
                for block in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(block)
            files.append({"path": rel, "size": path.stat().st_size,
                          "sha256": digest.hexdigest()})
        except OSError as exc:
            errors.append({"path": rel, "error": str(exc)})

payload = {
    "branch": git_value("rev-parse", "--abbrev-ref", "HEAD"),
    "head": git_value("rev-parse", "HEAD"),
    "scope": "all regular files including ignored and untracked; excludes .git, symlinks, and this evidence directory",
    "non_atomic": True,
    "file_count": len(files),
    "read_errors": errors,
    "files": sorted(files, key=lambda item: item["path"]),
}
with (OUT / "BASELINE_BEFORE.json").open("x", encoding="utf-8") as stream:
    json.dump(payload, stream, ensure_ascii=False, separators=(",", ":"))
    stream.write("\n")
print(json.dumps({"branch": payload["branch"], "head": payload["head"],
                  "file_count": payload["file_count"],
                  "read_errors": len(errors)}, ensure_ascii=False))
