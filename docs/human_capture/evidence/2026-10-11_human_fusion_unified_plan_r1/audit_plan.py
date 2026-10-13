"""Offline planning evidence: full working-tree hashes and read-only CLI review."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[4]
EVIDENCE = Path(__file__).resolve().parent


def save(name, value):
    target = EVIDENCE / name
    if target.exists():
        raise FileExistsError(target)
    target.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def digest(path):
    if path.is_symlink():
        return {"kind": "symlink", "target": os.readlink(path),
                "sha256": hashlib.sha256(os.readlink(path).encode("utf-8")).hexdigest()}
    before = path.stat()
    sha = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            sha.update(block)
    after = path.stat()
    return {"kind": "file", "bytes": after.st_size, "sha256": sha.hexdigest(),
            "stable_during_read": (before.st_size, before.st_mtime_ns) ==
                                  (after.st_size, after.st_mtime_ns)}


def inventory(name):
    started = time.time()
    files, errors = {}, {}
    # Include ignored inputs/caches and untracked code; only Git internals are excluded.
    for directory, dirs, names in os.walk(ROOT, followlinks=False):
        dirs[:] = sorted(d for d in dirs if d != ".git")
        for filename in sorted(names):
            path = Path(directory) / filename
            relative = path.relative_to(ROOT).as_posix()
            try:
                files[relative] = digest(path)
            except OSError as exc:
                errors[relative] = str(exc)
    def git(*args):
        return subprocess.check_output(["git", *args], cwd=ROOT).decode("utf-8", "replace").strip()
    value = {"root": str(ROOT), "branch": git("branch", "--show-current"),
             "head": git("rev-parse", "HEAD"), "status": git("status", "--short", "--branch"),
             "tracked_paths": git("ls-files").splitlines(), "files": files, "errors": errors,
             "unstable": [p for p, row in files.items() if row.get("stable_during_read") is False],
             "elapsed_seconds": time.time() - started,
             "scope": "all filesystem files, including ignored/untracked; .git internals excluded; no directory symlink traversal"}
    save(name, value)
    print(json.dumps({"file": name, "files": len(files), "errors": len(errors),
                      "unstable": value["unstable"], "head": value["head"],
                      "elapsed_seconds": value["elapsed_seconds"]}, ensure_ascii=False))


def compare(before_name, after_name, output_name):
    before = json.loads((EVIDENCE / before_name).read_text(encoding="utf-8"))
    after = json.loads((EVIDENCE / after_name).read_text(encoding="utf-8"))
    old, new = before["files"], after["files"]
    changes = {p: {"before": old.get(p), "after": new.get(p)} for p in sorted(set(old) | set(new))
               if old.get(p, {}).get("sha256") != new.get(p, {}).get("sha256")}
    allowed_docs = {"docs/human_capture/README.md", "docs/human_capture/HUMAN_FUSION_UNIFIED_PLAN.md",
                    "docs/human_capture/HUMAN_FUSION_UNIFIED_PLAN_ACCEPTANCE.md",
                    "docs/human_capture/tickets/HUMAN-FUSION-UNIFIED-PLAN.md",
                    "docs/human_capture/returns/HUMAN-FUSION-UNIFIED-PLAN.md"}
    prefix = EVIDENCE.relative_to(ROOT).as_posix() + "/"
    external = {p: row for p, row in changes.items() if p not in allowed_docs and not p.startswith(prefix)}
    result = {"before": before_name, "after": after_name, "changes": changes,
              "outside_authorized_paths": external, "head_unchanged": before["head"] == after["head"],
              "baseline_errors": before["errors"], "final_errors": after["errors"],
              "baseline_unstable": before["unstable"], "final_unstable": after["unstable"]}
    save(output_name, result)
    print(json.dumps({"file": output_name, "changes": len(changes),
                      "outside_authorized_paths": list(external),
                      "head_unchanged": result["head_unchanged"]}, ensure_ascii=False))


def cli(label, prompt, timeout, readonly=False, instruction_file=None):
    # The npm .cmd wrapper truncates multiline arguments. Call the same binary directly.
    # A one-line carrier requires an observed read of the complete, hashed task file.
    carrier = ("Please read " + instruction_file.as_posix() +
               " and follow all instructions in that file. Return the review in Chinese.") if instruction_file else prompt
    command = [r"C:\Users\30680\AppData\Roaming\npm\node_modules\opencode-ai\bin\opencode.exe", "run", "--agent", "plan",
               "-m", "opencode-go/deepseek-v4.1-flash", "--format", "json", carrier]
    env = os.environ.copy()
    env["OPENCODE_DISABLE_AUTOUPDATE"] = "true"
    if readonly:
        # Per-process permissions only; preserve provider/auth/model/default database.
        env["OPENCODE_CONFIG_CONTENT"] = json.dumps({"permission": {"*": "deny", "read": "allow",
                    "glob": "allow", "grep": "allow", "list": "allow",
                    "external_directory": {"C:/Users/30680/.codex/skills/ponytail/*": "allow"}}})
    raw_path = EVIDENCE / (label + ".jsonl")
    start = time.time()
    with raw_path.open("x", encoding="utf-8") as out:
        process = subprocess.Popen(command, cwd=ROOT, env=env, stdout=out, stderr=subprocess.STDOUT)
        timed_out = False
        try:
            status = process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], stdout=out, stderr=subprocess.STDOUT)
            process.wait()
            status = process.returncode
    events = []
    for line in raw_path.read_text(encoding="utf-8").splitlines():
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            pass
    texts = [e.get("part", {}).get("text", "") for e in events if e.get("type") in ("text", "part.text")]
    output = "\n\n".join(texts)
    (EVIDENCE / (label + ".md")).write_text(output, encoding="utf-8")
    sessions = sorted({e["sessionID"] for e in events if e.get("sessionID")})
    verification = {"status": "NOT_RUN"}
    if sessions:
        exported = subprocess.run([command[0], "export", sessions[0]], cwd=ROOT,
                                  capture_output=True, encoding="utf-8", timeout=40)
        if exported.returncode == 0:
            data = json.loads(exported.stdout)
            messages = data.get("messages", [])
            user_texts = ["\n".join(p.get("text", "") for p in m.get("parts", []) if p.get("type") == "text")
                          for m in messages if m.get("info", {}).get("role") == "user"]
            infos = [m["info"] for m in messages if m.get("info", {}).get("role") == "assistant"]
            # This Windows CLI retains one pair of literal transport quotes, including for probes.
            canonical = [t[1:-1] if t.startswith('"') and t.endswith('"') else t for t in user_texts]
            verification = {"status": "PASS" if carrier in canonical else "FAIL",
                            "expected_chars": len(carrier), "actual_user_chars": [len(t) for t in user_texts],
                            "exact_raw_carrier_present": carrier in user_texts,
                            "canonical_carrier_present": carrier in canonical,
                            "normalization": "at most one pair of surrounding transport quotes; no whitespace/content normalization",
                            "actual_models": sorted({i.get("providerID", "") + "/" + i.get("modelID", "") for i in infos})}
    tool_parts = [e.get("part", {}) for e in events if e.get("type") == "tool_use"]
    if instruction_file:
        target = instruction_file.as_posix().lower()
        matched_reads = [p for p in tool_parts if p.get("tool") == "read" and
                         p.get("state", {}).get("input", {}).get("filePath", "").replace("\\", "/").lower() == target]
        verification["instruction_path"] = str(instruction_file)
        verification["instruction_sha256"] = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
        verification["instruction_file_unchanged"] = instruction_file.read_text(encoding="utf-8") == prompt
        verification["instruction_read_observed"] = any(p.get("state", {}).get("status") == "completed" and
                    not p.get("state", {}).get("metadata", {}).get("truncated", False) for p in matched_reads)
        if not verification["instruction_file_unchanged"] or not verification["instruction_read_observed"]:
            verification["status"] = "FAIL"
    save(label + "_status.json", {"command": command[:-1], "model": command[5],
         "exit_code": status, "timed_out": timed_out, "elapsed_seconds": time.time() - start,
         "session_ids": sessions, "dispatch_verification": verification,
         "actual_tools": sorted({p.get("tool", "") for p in tool_parts}), "tool_calls": len(tool_parts),
         "skill_read_observed": any("ponytail" in p.get("state", {}).get("input", {}).get("filePath", "")
                                    for p in tool_parts if p.get("tool") == "read"),
         "events": len(events), "text_chars": len(output), "readonly_permissions": readonly,
         "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest()})
    print(json.dumps({"label": label, "exit_code": status, "timed_out": timed_out,
                      "elapsed_seconds": time.time() - start, "text_chars": len(output),
                      "dispatch_verification": verification}))
    if verification.get("status") != "PASS" or verification.get("actual_models") != [command[5]]:
        return 1, output
    if (not readonly and tool_parts) or (readonly and any(p.get("tool") not in {"read", "glob", "grep", "list"} for p in tool_parts)):
        return 1, output
    return status, output


if __name__ == "__main__":
    action = sys.argv[1]
    if action == "inventory":
        inventory(sys.argv[2])
    elif action == "compare":
        compare(*sys.argv[2:5])
    elif action == "probe":
        status, output = cli(sys.argv[2] if len(sys.argv) > 2 else "OPENCODE_PROBE_01",
                             "Reply PROBE_OK only. Do not use any tools.", 55)
        if status != 0 or "PROBE_OK" not in output:
            raise SystemExit("PROBE_BLOCKED")
    elif action == "review":
        instruction_file = EVIDENCE / sys.argv[3]
        status, output = cli(sys.argv[2], instruction_file.read_text(encoding="utf-8"), 900, True, instruction_file)
        if status != 0 or "REVIEW_COMPLETE" not in output:
            raise SystemExit("REVIEW_INCOMPLETE")
    else:
        raise SystemExit("unknown action")
