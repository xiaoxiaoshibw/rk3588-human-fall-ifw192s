"""Independent R2 manifest + scope verification. Read-only.

Verifies the author submission manifest SHAs against the working tree, the
active-ledger implementation SHA claims, and the frozen/no-production-change
scope claim in 17_scope_check.json.
"""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
HERE = Path(__file__).resolve().parent
RUN = HERE.parent
MAN = RUN / "research_01" / "11_submission_manifest.json"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    out = {"script": "01_manifest_scope"}
    manifest = json.loads(MAN.read_text(encoding="utf-8"))

    files = manifest["files"]
    out["manifest_file_count"] = len(files)
    mism, missing = [], []
    for rel, digest in files.items():
        p = ROOT / rel
        if not p.exists():
            missing.append(rel)
            continue
        got = sha(p)
        if got != digest:
            mism.append({"path": rel, "manifest": digest, "actual": got})
    out["manifest_sha_mismatch"] = mism
    out["manifest_missing"] = missing
    out["manifest_all_match"] = not mism and not missing

    # active ledger implementation SHA self-claims
    active = RUN / "research_01" / manifest["active_ledger"]
    ledger = json.loads(active.read_text(encoding="utf-8"))
    impl = ledger.get("implementation_sha256", {})
    out["ledger_impl_count"] = len(impl)
    impl_bad = []
    for rel, digest in impl.items():
        p = ROOT / rel
        got = sha(p) if p.exists() else None
        if got != digest:
            impl_bad.append({"path": rel, "claimed": digest, "actual": got})
    out["ledger_impl_mismatch"] = impl_bad
    # The manifest old_new_implementation_sha must resolve to full paths too
    on = manifest.get("old_new_implementation_sha", {})
    on_bad = []
    for rel, digest in on.items():
        p = ROOT / rel
        got = sha(p) if p.exists() else None
        if got != digest:
            on_bad.append({"path": rel, "claimed": digest, "actual": got})
    out["old_new_sha_mismatch"] = on_bad

    scope = json.loads((RUN / "17_scope_check.json").read_text(encoding="utf-8"))
    out["scope"] = {
        "changed_existing": scope["changed_existing"],
        "unexpected_changes": scope["unexpected_changes"],
        "new_paths_count": len(scope["new_paths"]),
        "frozen_core_and_old_evidence_unchanged":
            scope["frozen_core_and_old_evidence_unchanged"],
        "production_regression_reused": scope["production_regression_reused"],
    }
    # any changed_existing not inside this run root is a scope break
    outside = [p for p in scope["changed_existing"]
               if not p.startswith("docs/human_fall/evidence/2026-10-04_gl_i05_r2")]
    out["changed_existing_outside_run_root"] = outside

    out["workspace_head"] = __import__("subprocess").run(
        ["git", "rev-parse", "HEAD"], cwd=str(ROOT), capture_output=True,
        text=True).stdout.strip()
    out["manifest_head"] = manifest.get("head")
    out["head_match"] = out["workspace_head"] == out["manifest_head"]

    (HERE / "01_manifest_scope.json").write_text(
        json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({k: out[k] for k in (
        "manifest_file_count", "manifest_all_match", "manifest_sha_mismatch",
        "manifest_missing", "ledger_impl_count", "ledger_impl_mismatch",
        "old_new_sha_mismatch", "changed_existing_outside_run_root",
        "head_match")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
