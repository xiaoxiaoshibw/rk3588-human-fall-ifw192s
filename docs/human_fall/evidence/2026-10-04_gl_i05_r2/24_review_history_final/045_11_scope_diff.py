"""Independent full-tree scope diff vs the author submission baseline.

Hashes every path in 17_submitted_baseline.json, reports changed/removed, and
lists current tracked+untracked paths absent from the baseline, classifying
whether each is an expected review/administrative addition.
"""
import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
RUN = Path(__file__).resolve().parents[1]
BASE = RUN / "17_submitted_baseline.json"


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    base_files = json.loads(BASE.read_text(encoding="utf-8"))["files"]
    changed, removed, unreadable = [], [], []
    for rel, meta in base_files.items():
        expected = meta.get("sha256") if isinstance(meta, dict) else None
        if expected is None:
            continue
        p = ROOT / rel
        try:
            if not p.exists():
                removed.append(rel)
            elif sha(p) != expected:
                changed.append(rel)
        except OSError as exc:
            unreadable.append({"path": rel, "err": str(exc)})

    prime = subprocess.run(["git", "-c", "core.quotepath=false", "ls-files",
                            "-co", "--exclude-standard"],
                           cwd=str(ROOT), capture_output=True, text=True).stdout.splitlines()
    prime = {p.replace("\\", "/") for p in prime}
    known = {k.replace("\\", "/") for k in base_files}
    new = sorted(prime - known)
    run_root = "docs/human_fall/evidence/2026-10-04_gl_i05_r2/"
    review_root = run_root + "opencode_second_review_01/"
    admin = {
        "docs/human_fall/DISPATCH.md", "docs/human_fall/README.md",
        "docs/human_fall/WORKFLOW.md", "docs/human_fall/returns/GL-I05.md",
    }
    # pre-existing untracked user material the baseline enumerator skipped
    preexisting_untracked = [p for p in new if p.startswith("文档/") or p.startswith("\"")
                             or "\u6587\u6863" in p]
    orchestrator = [p for p in new if p.startswith(run_root) and not p.startswith(review_root)]
    unexpected_new = [p for p in new
                      if not p.startswith(run_root)
                      and p not in admin and p not in preexisting_untracked]
    out = {"script": "11_scope_diff", "baseline_paths": len(base_files),
           "changed_existing": changed, "removed": removed, "unreadable": unreadable,
           "new_path_count": len(new),
           "new_review_files": [p for p in new if p.startswith(review_root)],
           "new_orchestrator_files": orchestrator,
           "preexisting_untracked_doc": len(preexisting_untracked),
           "unexpected_new": unexpected_new,
           "admin_changes_outside_run_root": sorted(set(changed) & admin),
           "scope_clean": not removed and not unreadable and not unexpected_new}
    (Path(__file__).resolve().parent / "11_scope_diff.json").write_text(
        json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({k: out[k] for k in (
        "baseline_paths", "changed_existing", "removed", "unreadable",
        "new_path_count", "unexpected_new", "scope_clean")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
