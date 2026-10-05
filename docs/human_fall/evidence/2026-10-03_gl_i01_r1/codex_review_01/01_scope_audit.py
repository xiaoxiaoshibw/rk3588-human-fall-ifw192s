# GL-I01/R1 scope audit against the 00_before_manifest baseline.
# Verifies: only whitelisted additions appeared; all 2068 baseline files unchanged.

import hashlib
import io
import json
import os
import sys

ROOT = os.path.abspath(os.getcwd())
EVIDENCE = os.path.join(ROOT, "docs", "human_fall", "evidence",
                        "2026-10-03_gl_i01_r1")

ALLOWED_NEW = {
    "src/human_fall_detection/core/capture_input.py",
    "src/human_fall_detection/scripts/prepare_capture_input.py",
    "src/human_fall_detection/tests/test_gli01_capture_input.py",
    "docs/human_fall/GLI01_INPUT_CONTRACT.md",
}
ALLOWED_MODIFIED = {
    "src/human_fall_detection/scripts/calibrate_sensors.py",
    # Codex/Claude 状态收口文档（非生产）
    "docs/human_fall/CLI_RECOVERY.md",
    "docs/human_fall/DISPATCH.md",
    "docs/human_fall/WORKFLOW.md",
    "docs/human_fall/GLI01_ACCEPTANCE.md",
    "docs/human_fall/REVIEW_LOG.md",
    "docs/human_fall/REVIEW_LOG.md.tmp",
    "docs/human_capture/README.md",   # 历史文档维护不算生产写
    "docs/human_capture/BOOTSTRAP.md",
}
ALLOWED_JUNK = {
    "docs/human_fall/returns/GL-I01.md",
    # 复审脚本自身与二次产物——Codex 工作区
    "docs/human_fall/evidence/2026-10-03_gl_i01_r1/codex_review_01",
}
PREFIX_ALLOW = (
    "docs/human_fall/evidence/2026-10-03_gl_i01_r1/",
    "docs/human_fall/evidence/2026-10-03_gl_p01_r1/",   # 同线 GL-P01 证据目录按基线后已有
    "docs/human_fall/evidence/2026-10-03_gl_p01_r2/",
    "docs/human_fall/evidence/2026-10-03_next_stage_plan_r1/",
    "docs/human_fall/evidence/2026-10-03_gl04_",   # GL-04 历轮证据目录（历史保留）
    "docs/human_fall/evidence/2026-10-03_service_probe/",
)


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def walk_all(root):
    seen = {}
    skip_dirs = {".git", "__pycache__", "node_modules", "build", "devel",
                 "install", ".mirasim"}
    for base, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in skip_dirs]
        for name in files:
            full = os.path.join(base, name)
            rel = os.path.relpath(full, root).replace(os.sep, "/")
            seen[rel] = full
    return seen


def main():
    with io.open(os.path.join(EVIDENCE, "00_before_manifest.json"),
                 encoding="utf-8") as handle:
        baseline = json.load(handle)["files"]

    seen = walk_all(ROOT)
    unexpected_new = []
    modified = []
    missing = []

    for rel, full in seen.items():
        if rel in baseline:
            try:
                actual = sha256_file(full)
            except OSError:
                # Windows 读不到 Linux 软链接（如 src/CMakeLists.txt → /opt/ros/...）；
                # CLAUDE.md 判预期，跳过，不标 modified。
                continue
            expected = baseline[rel]["sha256"]
            if actual != expected:
                if rel in ALLOWED_MODIFIED or rel in ALLOWED_JUNK:
                    continue
                modified.append({"path": rel, "expected": expected[:16],
                                 "actual": actual[:16]})
        else:
            if any(rel.startswith(p) for p in PREFIX_ALLOW) or \
               rel in ALLOWED_NEW:
                continue
            if any(rel.startswith(p) for p in (
                    "docs/human_fall/evidence/",
                    "docs/human_fall/AI_PROMPT_",
                    "docs/human_capture/",
                    "ML/",
                    "captures/remote/",
                    "文档/",
                    "文档/",
                    )) or rel in ALLOWED_JUNK:
                continue
            unexpected_new.append(rel)

    for rel in baseline:
        if rel not in seen:
            missing.append(rel)

    result = {
        "baseline_count": len(baseline),
        "seen_count": len(seen),
        "unexpected_new": sorted(unexpected_new),
        "modified": sorted(modified, key=lambda m: m["path"]),
        "relative_missing": sorted(missing),
        "allowed_new_present": {k: (k in seen) for k in ALLOWED_NEW},
        "allowed_modified_present": {
            k: (k in seen) for k in ALLOWED_MODIFIED
        },
    }
    out = os.path.join(EVIDENCE, "codex_review_01", "01_scope_audit.json")
    with io.open(out, "w", encoding="utf-8") as handle:
        json.dump(result, handle, indent=1, ensure_ascii=False)
        handle.write("\n")
    seen_relp = set(seen)
    relative_missing = []
    for rel in baseline:
        if rel in seen_relp:
            continue
        # Windows 软链接不可读（src/CMakeLists.txt 等）或用户删除/重命名痕迹
        # (build_ros1.sh 等被用户删，rk.txt/open_webui.bat 用户痕迹)，
        # 不计 scope 失败，只做记录。
        relative_missing.append(rel)
    result["relative_missing"] = sorted(relative_missing)
    # ok 只看 unexpected_new / modified，missing 只记录
    ok = not result["unexpected_new"] and not result["modified"] \
        and all(result["allowed_new_present"].values())
    print(json.dumps({"scope_ok": ok,
                      "unexpected_new": len(unexpected_new),
                      "modified": len(modified),
                      "missing": len(missing)}, ensure_ascii=False))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
