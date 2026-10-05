"""Revalidation step 2: author manifest SHA + frozen inputs, before and after.

Writes NEW output 02_manifest_scope_01.json.
"""
import hashlib
import json
from pathlib import Path

REPO = Path(r"D:\Code\ldiar")
RUN = REPO / "docs/human_fall/evidence/2026-10-04_gl_i06_r1"
REVAL = RUN / "opencode_review_01/revalidation_01"
RUN_PREFIX = RUN.relative_to(REPO).as_posix() + "/"


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def verify(label, mapping, out):
    missing, mismatch, ok, nonhash = [], [], 0, []
    for rel, meta in mapping.items():
        if not (isinstance(meta, dict) and "sha256" in meta):
            nonhash.append(rel)
            continue
        p = REPO / rel
        try:
            if not p.exists():
                missing.append(rel)
                continue
            a = sha(p)
        except OSError:
            missing.append(rel + " [unreadable]")
            continue
        if a != meta["sha256"]:
            mismatch.append({"rel": rel, "expected": meta["sha256"], "actual": a})
        else:
            ok += 1
    out[label] = {"hashable": len(mapping) - len(nonhash), "ok": ok,
                  "missing": missing, "missing_count": len(missing),
                  "mismatch": mismatch[:50], "mismatch_count": len(mismatch),
                  "nonhash_entries": nonhash[:20], "nonhash_count": len(nonhash)}
    return out[label]


def scope_diff(before, after, label, out, exclude_prefixes):
    b, a = before["files"], after["files"]
    changed, added = [], []
    for rel in set(b) & set(a):
        if any(rel.startswith(x) for x in exclude_prefixes):
            continue
        bs = b[rel].get("sha256") if isinstance(b[rel], dict) else None
        as_ = a[rel].get("sha256") if isinstance(a[rel], dict) else None
        if bs != as_:
            changed.append(rel)
    for rel in set(a) - set(b):
        if any(rel.startswith(x) for x in exclude_prefixes):
            continue
        added.append(rel)
    out[label] = {"changed": sorted(changed), "changed_count": len(changed),
                  "added_outside": sorted(added), "added_count": len(added)}


def main():
    man = json.loads((RUN / "19_manifest_01.json").read_text(encoding="utf-8"))
    before = json.loads((RUN / "01_before_baseline.json").read_text(encoding="utf-8"))
    sub = json.loads((RUN / "16_submission_baseline_01.json").read_text(encoding="utf-8"))
    after = json.loads((RUN / "27_after_review_baseline_01.json").read_text(encoding="utf-8"))
    out = {
        "heads": {"before": before["head"], "submission": sub["head"],
                  "after": after["head"], "manifest": man["head"]},
        "branches": {"before": before["branch"], "submission": sub["branch"],
                     "after": after["branch"], "manifest": man["branch"]},
        "manifest_self_sha_now": sha(RUN / "19_manifest_01.json"),
        "manifest_self_sha_in_after": after["files"].get(
            RUN.joinpath("19_manifest_01.json").relative_to(REPO).as_posix(), {}).get("sha256"),
        "acceptance_sha_expected": man["acceptance_sha256"],
        "acceptance_sha_now": sha(REPO / "docs/human_fall/GLI06_ACCEPTANCE.md"),
    }
    verify("manifest_files", man["files"], out)
    verify("manifest_frozen_dependencies", man["frozen_dependencies"], out)
    verify("before_files", before["files"], out)
    verify("submission_files", sub["files"], out)
    verify("after_review_files", after["files"], out)
    scope_diff(before, sub, "before_vs_submission_protected", out, [RUN_PREFIX])
    scope_diff(before, after, "before_vs_after_protected", out,
               [RUN_PREFIX, "docs/human_fall/returns/GL-I06.md"])
    out["manifest_self_unchanged"] = out["manifest_self_sha_now"] == out["manifest_self_sha_in_after"]
    out["acceptance_unchanged"] = out["acceptance_sha_expected"] == out["acceptance_sha_now"]
    target = REVAL / "02_manifest_scope_01.json"
    if target.exists():
        raise SystemExit("refuse to overwrite " + str(target))
    target.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    for k in ("manifest_files", "manifest_frozen_dependencies", "after_review_files"):
        r = out[k]
        print(k, "ok=%d/%d" % (r["ok"], r["hashable"]), "missing", r["missing_count"],
              "mismatch", r["mismatch_count"], "nonhash", r["nonhash_count"])
    print("manifest_self_unchanged", out["manifest_self_unchanged"],
          "acceptance_unchanged", out["acceptance_unchanged"])
    print("before_vs_submission changed", out["before_vs_submission_protected"]["changed_count"],
          "added", out["before_vs_submission_protected"]["added_count"])
    print("before_vs_after changed", out["before_vs_after_protected"]["changed_count"],
          "added_outside", out["before_vs_after_protected"]["added_count"])
    print("before_vs_after changed list", out["before_vs_after_protected"]["changed"][:20])


if __name__ == "__main__":
    main()
