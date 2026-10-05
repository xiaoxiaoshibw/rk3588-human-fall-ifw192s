"""Independent manifest/baseline SHA verification. Read-only."""
import hashlib
import json
from pathlib import Path

REPO = Path(r"D:\Code\ldiar")
RUN = REPO / "docs/human_fall/evidence/2026-10-04_gl_i06_r1"


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def verify_mapping(label, mapping, out):
    missing, mismatch, ok, broken = [], [], 0, []
    for rel, meta in mapping.items():
        p = REPO / rel
        try:
            if not p.exists():
                missing.append(rel)
                continue
            actual = sha256(p)
        except OSError:
            if p.is_symlink():
                broken.append(rel)
            else:
                missing.append(rel)
            continue
        exp = meta["sha256"] if isinstance(meta, dict) else meta
        if actual != exp:
            mismatch.append({"rel": rel, "expected": exp, "actual": actual})
        else:
            ok += 1
    out[label] = {"total": len(mapping), "ok": ok,
                  "missing": missing[:50], "missing_count": len(missing),
                  "broken_symlink": broken[:50], "broken_symlink_count": len(broken),
                  "mismatch": mismatch[:50], "mismatch_count": len(mismatch)}
    return out[label]


def main():
    man = json.loads((RUN / "19_manifest_01.json").read_text(encoding="utf-8"))
    before = json.loads((RUN / "01_before_baseline.json").read_text(encoding="utf-8"))
    sub = json.loads((RUN / "16_submission_baseline_01.json").read_text(encoding="utf-8"))
    out = {"manifest_head": man["head"], "manifest_branch": man["branch"],
           "before_head": before["head"], "before_branch": before["branch"],
           "submission_head": sub["head"], "submission_branch": sub["branch"],
           "manifest_self_in_files": "19_manifest_01.json" in man["files"],
           "acceptance_sha_expected": man["acceptance_sha256"],
           "acceptance_sha_actual": sha256(REPO / "docs/human_fall/GLI06_ACCEPTANCE.md")}
    verify_mapping("manifest_files", man["files"], out)
    verify_mapping("manifest_frozen_dependencies", man["frozen_dependencies"], out)
    verify_mapping("before_files", before["files"], out)
    verify_mapping("submission_files", sub["files"], out)
    # before vs submission scope
    bf, sf = before["files"], sub["files"]
    out["scope_added_in_submission"] = sorted(set(sf) - set(bf))
    out["scope_only_in_before"] = sorted(set(bf) - set(sf))
    def _s(v):
        return v.get("sha256") if isinstance(v, dict) else v
    out["scope_changed_sha"] = sorted(
        rel for rel in (set(bf) & set(sf)) if _s(bf[rel]) != _s(sf[rel]))
    out["counts"] = {"before": len(bf), "submission": len(sf),
                     "manifest_files": len(man["files"]),
                     "manifest_frozen": len(man["frozen_dependencies"])}
    (RUN / "opencode_review_01/01_manifest_verify_01.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    for label in ("manifest_files", "manifest_frozen_dependencies", "before_files", "submission_files"):
        r = out[label]
        print(label, "ok=%d/%d" % (r["ok"], r["total"]),
              "missing=%d" % r["missing_count"], "mismatch=%d" % r["mismatch_count"])
    print("acceptance match:", out["acceptance_sha_expected"] == out["acceptance_sha_actual"])
    print("counts:", out["counts"])
    print("added_in_submission:", len(out["scope_added_in_submission"]))
    print("changed_sha:", out["scope_changed_sha"][:20])


if __name__ == "__main__":
    main()
