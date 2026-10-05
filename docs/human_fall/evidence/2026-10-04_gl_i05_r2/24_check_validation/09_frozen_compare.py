"""Confirm production/frozen files are byte-identical between the R1 baseline
and the R2 baseline, so R1's 423/2 regression evidence is validly reusable.
"""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
EV = ROOT / "docs/human_fall/evidence"
R1 = EV / "2026-10-04_gl_i05_r1/00_before_baseline.json"
R2 = EV / "2026-10-04_gl_i05_r2/00_before_baseline.json"


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    r1 = {k: v["sha256"] for k, v in
          json.loads(R1.read_text(encoding="utf-8"))["files"].items()
          if isinstance(v, dict) and "sha256" in v}
    r2 = {k: v["sha256"] for k, v in
          json.loads(R2.read_text(encoding="utf-8"))["files"].items()
          if isinstance(v, dict) and "sha256" in v}
    prod = lambda k: k.startswith("src/") or "/config/" in k
    r1p = {k: v for k, v in r1.items() if prod(k)}
    r2p = {k: v for k, v in r2.items() if prod(k)}
    diff = {k for k in set(r1p) & set(r2p) if r1p[k] != r2p[k]}
    only1 = set(r1p) - set(r2p)
    only2 = set(r2p) - set(r1p)
    # current tree for the manifest src/config entries
    cur_bad = []
    unreadable = []
    for k, v in r2p.items():
        p = ROOT / k
        try:
            if not p.exists() or sha(p) != v:
                cur_bad.append(k)
        except OSError:
            unreadable.append(k)
    out = {"script": "09_frozen_compare",
           "r1_prod_files": len(r1p), "r2_prod_files": len(r2p),
           "prod_changed_between_baselines": sorted(diff),
           "prod_only_r1": sorted(only1), "prod_only_r2": sorted(only2),
           "current_tree_prod_mismatch": cur_bad,
           "unreadable_win_symlink": unreadable,
           "production_frozen_ok": not diff and not only1 and not cur_bad}
    (Path(__file__).resolve().parent / "09_frozen_compare.json").write_text(
        json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False))


if __name__ == "__main__":
    main()
