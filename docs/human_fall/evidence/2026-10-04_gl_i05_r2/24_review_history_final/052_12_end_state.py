"""End-of-review state: HEAD, manifest re-verify, and no author-source change."""
import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
RUN = Path(__file__).resolve().parents[1]
MAN = RUN / "research_01" / "11_submission_manifest.json"


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    manifest = json.loads(MAN.read_text(encoding="utf-8"))
    mism = [rel for rel, d in manifest["files"].items()
            if not (ROOT / rel).exists() or sha(ROOT / rel) != d]
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(ROOT),
                          capture_output=True, text=True).stdout.strip()
    scope = json.loads((Path(__file__).resolve().parent / "11_scope_diff.json")
                       .read_text(encoding="utf-8"))
    out = {"script": "12_end_state", "end_head": head,
           "manifest_head": manifest["head"], "head_match": head == manifest["head"],
           "manifest_mismatch_after_review": mism,
           "author_files_unchanged": not mism and scope["scope_clean"]}
    (Path(__file__).resolve().parent / "12_end_state.json").write_text(
        json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps(out))


if __name__ == "__main__":
    main()
