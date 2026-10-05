"""Revalidation step 1: audit the controller-recovered write/edit history.

Reads 25_review_history_final_01.json (exact version contents + execution
outcomes). Verifies content hashes, latest-revision-vs-file bytes, counts
same-name edits and failed executions, and materializes each recovered version
as a NEW immutable .py/.md under recovered_versions/. Writes only new files.
"""
import hashlib
import json
import os
from pathlib import Path

RUN = Path(r"D:\Code\ldiar\docs\human_fall\evidence\2026-10-04_gl_i06_r1")
HIST = RUN / "25_review_history_final_01.json"
REVIEW = RUN / "opencode_review_01"
REVAL = REVIEW / "revalidation_01"
RECOV = REVAL / "recovered_versions"


def sha_bytes(b):
    return hashlib.sha256(b).hexdigest()


def sha_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def main():
    d = json.loads(HIST.read_text(encoding="utf-8"))
    versions = d["versions"]
    executions = d["executions"]
    # 1. content hashes of every recovered version
    ver_fail = []
    by_file = {}
    materialized = []
    for v in versions:
        content = v["content"].encode("utf-8") if isinstance(v["content"], str) else v["content"]
        actual = sha_bytes(content)
        if actual != v["sha256"]:
            ver_fail.append({"version": v["version"], "file": v["file"],
                             "expected": v["sha256"], "actual": actual})
        rel = Path(v["file"]).name
        by_file.setdefault(rel, []).append(v)
    # 2. materialize every version (immutable new files); never overwrite
    for v in versions:
        rel = Path(v["file"]).name
        ext = Path(rel).suffix or ".txt"
        stem = Path(rel).stem
        base = RECOV / stem
        base.mkdir(parents=True, exist_ok=True)
        target = base / ("v%02d_%s%s" % (v["version"], v["sha256"][:12], ext))
        data = v["content"].encode("utf-8") if isinstance(v["content"], str) else v["content"]
        if target.exists():
            if sha_file(target) != v["sha256"]:
                raise SystemExit("materialized file mismatch: " + str(target))
        else:
            with target.open("xb") as f:
                f.write(data)
        materialized.append(str(target.relative_to(REVIEW).as_posix()))
    # 3. latest version vs actual current file bytes
    latest = {}
    for rel, vs in by_file.items():
        last = max(vs, key=lambda x: x["version"])
        p = REVIEW / rel
        latest[rel] = {
            "versions": len(vs),
            "edit_calls": sum(1 for v in vs if v["tool"] == "edit"),
            "latest_version": last["version"], "latest_sha": last["sha256"],
            "latest_tool": last["tool"], "exists": p.exists(),
            "actual_sha": sha_file(p) if p.exists() else None,
            "matches": (p.exists() and sha_file(p) == last["sha256"]),
        }
    same_name_edits = {k: v for k, v in latest.items() if v["edit_calls"] > 0}
    # 4. executions: exit codes, command kind, inferred source revision
    events = sorted([(v["event_ordinal"], "version", v) for v in versions] +
                    [(e["event_ordinal"], "exec", e) for e in executions])
    inferred = {}
    exec_records = []
    for e in executions:
        # latest version event_ordinal <= this execution's ordinal, by file if command references it
        cmd = e["command"]
        referenced = [rel for rel in by_file if rel in cmd]
        rev = {}
        for rel in referenced:
            prior = [v for v in by_file[rel] if v["event_ordinal"] < e["event_ordinal"]]
            rev[rel] = max(prior, key=lambda x: x["event_ordinal"])["version"] if prior else None
        meta = e.get("metadata", {})
        exec_records.append({
            "execution": e["execution"], "event_ordinal": e["event_ordinal"],
            "exit": meta.get("exit"), "truncated": meta.get("truncated"),
            "command_head": cmd.strip().splitlines()[0][:160],
            "expected_revision": rev,
            "source_revision_sha256_field": e.get("source_revision_sha256"),
            "output_head": (meta.get("output") or "")[:200].replace("\r", ""),
        })
    failed = [r for r in exec_records if r["exit"] != 0]
    out = {
        "history_kind": d.get("kind"), "partial_stream": d.get("partial_stream"),
        "stream_sha256": d.get("stream_sha256"),
        "n_versions": len(versions), "n_writes": sum(1 for v in versions if v["tool"] == "write"),
        "n_edits": sum(1 for v in versions if v["tool"] == "edit"),
        "n_same_name_edit_files": len(same_name_edits),
        "same_name_edit_total": sum(v["edit_calls"] for v in same_name_edits.values()),
        "n_executions": len(executions), "n_failed_executions": len(failed),
        "version_content_hash_failures": ver_fail,
        "latest_vs_file": latest, "all_latest_match": all(v["matches"] for v in latest.values()),
        "same_name_edit_files": {k: v for k, v in same_name_edits.items()},
        "executions": exec_records, "failed_executions": failed,
        "materialized_versions": materialized,
    }
    target = REVAL / "01_history_audit_01.json"
    if target.exists():
        raise SystemExit("refuse to overwrite " + str(target))
    target.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print("versions", len(versions), "writes", out["n_writes"], "edits", out["n_edits"],
          "same-name-edit-files", len(same_name_edits), "total edits", out["same_name_edit_total"])
    print("content hash failures", len(ver_fail), "all latest match", out["all_latest_match"])
    print("executions", len(executions), "failed", len(failed))
    for f in failed:
        print("  FAILRUN", f["execution"], "exit", f["exit"], f["command_head"][:90])
    for k, v in same_name_edits.items():
        print("  EDITFILE", k, "versions", v["versions"], "edit_calls", v["edit_calls"],
              "latest_sha", v["latest_sha"][:12])


if __name__ == "__main__":
    main()
