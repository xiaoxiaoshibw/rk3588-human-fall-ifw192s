"""C：data/ 会话清点与删除清单（只读扫描；按新数据目录规矩只出清单，删除需用户确认）。

用法：
    python -B -W error data_manifest.py --out <evidence_dir> [--write]
输出：33_DATA_MANIFEST.json + 33_DATA_MANIFEST.md（sid / 帧数 / 字节 / meta+bin sha256 /
      是否有配平产物 job / 在仓代码消费者 / 建议）+ 汇总统计。
"""
import argparse
import hashlib
import json
import re
from pathlib import Path

from common import LEVELED, ROOT, REMOTE

SCAN_DIRS = ("src", "webui", "pc_apps", "tools", "sidequests", "ML", "docs")
SKIP_PARTS = ("captures/", "data/", ".git/", "docs/sidequests/evidence/2026-10-14_plane_track_r1/",
              "sidequests/plane_track/", "node_modules/", "__pycache__/", "dist/", "output/",
              "results/", "runs/", "workspace/", "vendor/")
MAX_BYTES = 256_000


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def references_all(sids):
    """单次遍历仓库，返回 {sid: [files]}（避免每段会话都重扫一遍）。"""
    listing = list(sids)
    pattern = re.compile("|".join(re.escape(s) for s in listing))
    found = {sid: [] for sid in listing}
    for directory in SCAN_DIRS:
        base = ROOT / directory
        if not base.is_dir():
            continue
        for path in base.rglob("*"):
            if not path.is_file():
                continue
            relative = path.relative_to(ROOT).as_posix()
            if any(part in relative + "/" for part in SKIP_PARTS):
                continue
            if path.suffix in (".png", ".jpg", ".bin", ".bag", ".pcap", ".zip", ".npz", ".exe", ".ico", ".so"):
                continue
            try:
                if path.stat().st_size > MAX_BYTES:
                    continue
                text = path.read_text(encoding="utf8", errors="ignore")
            except OSError:
                continue
            for match in set(pattern.findall(text)):
                found[match].append(relative)
    return found


def references(sid):
    pattern = re.compile(re.escape(sid))
    code = []
    for directory in SCAN_DIRS:
        base = ROOT / directory
        if not base.is_dir():
            continue
        for path in base.rglob("*"):
            if not path.is_file():
                continue
            relative = path.relative_to(ROOT).as_posix()
            if any(part in relative + "/" for part in SKIP_PARTS):
                continue
            if path.suffix in (".png", ".jpg", ".bin", ".bag", ".pcap", ".zip", ".npz", ".exe", ".ico", ".so"):
                continue
            try:
                if path.stat().st_size > MAX_BYTES:
                    continue
                text = path.read_text(encoding="utf8", errors="ignore")
            except OSError:
                continue
            if pattern.search(text):
                code.append(relative)
                break
    return code


def leveled_jobs(sid):
    """哪些 job 的 report.json 记录的 sid 与此会话一致。"""
    jobs = []
    for job in sorted(LEVELED.iterdir()):
        report = job / "report.json"
        if job.is_dir() and report.exists():
            try:
                if json.loads(report.read_text(encoding="utf8")).get("sid") == sid:
                    jobs.append(job.name)
            except (OSError, ValueError):
                continue
    return jobs


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    out = Path(args.out)
    rows, total_bytes, leveled_bytes = [], 0, 0
    session_dirs = sorted(p for p in REMOTE.iterdir() if p.is_dir())
    refs = references_all([p.name for p in session_dirs])
    for directory in session_dirs:
        sid = directory.name
        meta_path, bin_path = directory / "meta.json", directory / "points.bin"
        if not meta_path.exists() or not bin_path.exists():
            rows.append({"sid": sid, "error": "meta.json/points.bin 缺失"})
            continue
        meta = json.loads(meta_path.read_text(encoding="utf8"))
        size = meta_path.stat().st_size + bin_path.stat().st_size
        jobs = leveled_jobs(sid)
        jobs_bytes = 0
        for job in jobs:
            jobs_bytes += sum(p.stat().st_size for p in (LEVELED / job).rglob("*") if p.is_file())
        code = refs.get(sid, [])
        rows.append({
            "sid": sid, "frames": len(meta.get("frames", [])),
            "duration_s": meta.get("duration_sec"), "points": int(meta.get("total_points", 0)),
            "bytes_session": size, "meta_sha256": sha256(meta_path), "bin_sha256": sha256(bin_path),
            "leveled_jobs": jobs, "bytes_leveled": jobs_bytes,
            "code_consumers": code,
            "recommendation": ("delete_candidate(有配平产物且无在仓代码消费者)" if jobs and not code
                               else ("keep(有在仓代码消费者)" if code else "no_leveled_product(先配平才可删)")),
        })
        total_bytes += size
        leveled_bytes += jobs_bytes
    payload = {"root": str(REMOTE), "sessions": len(rows), "bytes_sessions": total_bytes,
               "bytes_leveled_products": leveled_bytes, "rows": rows,
               "rule": "删除任何会话/产物前需 sid+字节+sha256 清单并经用户确认；本脚本只出清单，不删"}
    text = json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False)
    if args.write:
        with (out / "33_DATA_MANIFEST.json").open("x", encoding="utf8") as stream:
            stream.write(text)
        lines = ["| sid | 帧 | 时长s | 字节 | meta sha256(前16) | bin sha256(前16) | 配平 job | 代码消费者 | 建议 |",
                 "|---|---:|---:|---:|---|---|---|---|---|"]
        for row in rows:
            if "error" in row:
                lines.append("| %s | - | - | - | - | - | - | - | %s |" % (row["sid"], row["error"]))
                continue
            lines.append("| %s | %d | %.1f | %d | `%s` | `%s` | %s | %s | %s |" % (
                row["sid"], row["frames"], row["duration_s"] or 0, row["bytes_session"],
                row["meta_sha256"][:16], row["bin_sha256"][:16],
                ",".join(row["leveled_jobs"]) or "无", len(row["code_consumers"]),
                row["recommendation"]))
        with (out / "33_DATA_MANIFEST.md").open("x", encoding="utf8") as stream:
            stream.write("# data/ 会话清单（删除前必需）\n\n"
                         "> 只读扫描；删除执行需用户确认（新数据目录规矩）。\n\n"
                         + "\n".join(lines) + "\n\n"
                         "汇总：会话 %d 段 / %.2f GB；配平产物 %.2f GB。\n" % (
                             payload["sessions"], total_bytes / 1e9, leveled_bytes / 1e9))
    summary = {"sessions": len(rows), "GB": round(total_bytes / 1e9, 2),
               "leveled_GB": round(leveled_bytes / 1e9, 2),
               "delete_candidates": [r["sid"] for r in rows if r.get("recommendation", "").startswith("delete_candidate")],
               "keep": [r["sid"] for r in rows if r.get("recommendation", "").startswith("keep")]}
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
