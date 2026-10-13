"""Read-only Git/file baseline; never stage or change repository files."""
import hashlib
import json
import pathlib
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[4]
OUT = pathlib.Path(__file__).parent


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT)


def snapshot(name):
    files = git("ls-files", "--cached", "--others", "--exclude-standard", "-z")
    hashes, missing = {}, []
    for raw in sorted(set(files.split(b"\0")) - {b""}):
        rel = raw.decode("utf-8")
        if rel.startswith(str(OUT.relative_to(ROOT)).replace("\\", "/") + "/"):
            continue
        p = ROOT / rel
        if p.is_file():
            hashes[rel] = hashlib.sha256(p.read_bytes()).hexdigest()
        else:
            missing.append(rel)
    result = {"branch": git("branch", "--show-current").decode().strip(),
              "head": git("rev-parse", "HEAD").decode().strip(),
              "files": hashes, "missing_or_symlink": missing}
    with (OUT / (name + ".json")).open("x", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=1)
    (OUT / (name + "_status.txt")).write_bytes(git("status", "--short"))
    print(name, len(hashes), "files", len(missing), "missing/symlink")


if __name__ == "__main__":
    import sys
    snapshot(sys.argv[1])
