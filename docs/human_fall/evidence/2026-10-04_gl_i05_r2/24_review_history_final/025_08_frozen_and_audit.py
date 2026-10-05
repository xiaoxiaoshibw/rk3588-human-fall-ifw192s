"""Verify recording audit SHAs, no-new-capture claim, no-cache claim and
Python 3.8 AST compatibility of the five new research files.
"""
import ast
import hashlib
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
RUN = Path(__file__).resolve().parents[1]
RES = RUN / "research_01"
AUDIT = RUN / "08_assets_audit.json"


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    audit = json.loads(AUDIT.read_text(encoding="utf-8"))
    out = {"script": "08_frozen_and_audit"}

    recs = audit["local_metadata"]
    out["record_count"] = len(recs)
    bad = []
    for r in recs:
        p = ROOT / r["path"]
        if not p.exists() or sha(p) != r["sha256"]:
            bad.append(r["path"])
    out["record_sha_mismatch"] = bad
    out["all_records_present_matching"] = not bad

    # no capture modified on/after the R2 day
    late = []
    for r in recs:
        p = ROOT / r["path"]
        if p.exists() and "2026-10-04" <= __import__("datetime").datetime.fromtimestamp(
                p.stat().st_mtime).strftime("%Y-%m-%d"):
            late.append(r["path"])
    out["captures_modified_on_or_after_20261004"] = late

    # unknown identity claims preserved
    out["unknowns_retained"] = all(
        r["recording_config_binding"] == "unknown" and r["extrinsic_from_to"] == "unknown"
        for r in recs)
    out["rotation_unknown"] = audit["recording_evidence"]["measured_source_to_world_rotation"] == "unknown"
    out["config_binding_unknown"] = audit["recording_evidence"]["configuration_sha_binding"].startswith("unknown")
    out["physical_flags"] = {k: audit[k] for k in ("B01", "B02", "D01", "D02")}

    # referenced diagnostic SHA
    diag = ROOT / "docs/human_fall/evidence/2026-10-03_gl_i04_r1/12_real_final/diagnostic.json"
    out["diagnostic_sha_ok"] = sha(diag) == audit["recording_evidence"]["diagnostic_sha256"]

    # no-cache static check in the new research files
    files = ["oracle_analysis.py", "search_prototype.py", "experiment.py",
             "test_gli05_research.py", "source_review.py"]
    cache_hits = {}
    for name in files:
        text = (RES / name).read_text(encoding="utf-8")
        cache_hits[name] = sorted(set(re.findall(r"\b(cache|lru_cache|memo\w*)\b", text)))
    out["cache_tokens_in_new_files"] = cache_hits
    out["no_cache_implemented"] = all(not v for v in cache_hits.values())

    # Python 3.8 AST compatibility
    ast_bad = {}
    for name in files:
        src = (RES / name).read_text(encoding="utf-8")
        try:
            ast.parse(src, filename=name, feature_version=(3, 8))
        except SyntaxError as exc:
            ast_bad[name] = str(exc)
    out["py38_ast_failures"] = ast_bad
    out["py38_ast_ok"] = not ast_bad

    (Path(__file__).resolve().parent / "08_frozen_and_audit.json").write_text(
        json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False))


if __name__ == "__main__":
    main()
