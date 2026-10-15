"""A07 待删清单：已验证配平产物的会话 + 消费者 + 板端状态 + 建议。

用法：
    python -B -W error deletion_list.py --inventory <01_INVENTORY_v2.json> --out <evidence_dir> [--write]
--write 时写 10_DELETION_CANDIDATES.json；不带 --write 只打印。
只读扫描仓库文本引用（代码 vs 文档分开），不删除任何文件。
"""
import argparse
import json
import re
from pathlib import Path

from common import LEVELED, REMOTE, ROOT

JOBS = {
    "cap_20261014_164522": ["363473a9e2e64649994dca11b2b26929"],
    "cap_20261010_175227": ["6d5809d5a87b462cad4023520868b9e6"],
    "cap_20261013_094302": ["53bfb3ca7bdc44b3b04084da998d7c65"],
    "cap_20261013_094333": ["04e9b3db32a143ccaf7c48945952a7a7"],
    "cap_20261013_131958": ["61cb6976b0f8479394641850d9a7c6ca"],
    "cap_20261009_113611": ["632eff1e189945d8915eb5af7a9ddcf9"],
    "cap_20261009_122700": ["d34c7d9d7d334ef2a421cb6a569cfa53"],
}
SCAN_DIRS = ("src", "webui", "pc_apps", "tools", "sidequests", "ML", "docs")
SKIP_PARTS = ("captures/", ".git/", "docs/sidequests/evidence/2026-10-14_plane_track_r1/",
              "sidequests/plane_track/", "node_modules/", "__pycache__/", "dist/", "output/",
              "results/", "runs/", "workspace/", "vendor/")
MAX_BYTES = 256_000              # 36 GB docs/ 全扫不现实；消费者判据只取小文本文件


def references(sid):
    """All in-repo text references, split code vs doc (bounded scan)."""
    pattern = re.compile(re.escape(sid))
    code, docs = [], []
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
                (docs if path.suffix in (".md", ".txt") else code).append(relative)
    return code, docs


def job_info(job_id):
    directory = LEVELED / job_id
    report = json.loads((directory / "report.json").read_text(encoding="utf8"))
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf8"))
    return {"job_id": job_id, "recommended": report.get("recommended"),
            "estimators_valid": {k: v.get("valid") for k, v in report["estimators"].items()},
            "report_sha256": manifest.get("report_sha256"),
            "artifacts": sorted((manifest.get("artifacts") or {}).keys())}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--inventory", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    inventory = json.loads(Path(args.inventory).read_text(encoding="utf8"))
    board = {row["session_id"]: row for row in inventory["board"]["payload"]["sessions"]}
    rows = []
    for sid, jobs in JOBS.items():
        directory = REMOTE / sid
        code, docs = references(sid)
        board_row = board.get(sid, {})
        rows.append({
            "sid": sid,
            "path": str(directory),
            "bytes_meta": (directory / "meta.json").stat().st_size,
            "bytes_points": (directory / "points.bin").stat().st_size,
            "bytes_total": (directory / "meta.json").stat().st_size + (directory / "points.bin").stat().st_size,
            "jobs": [job_info(job) for job in jobs],
            "board_state": board_row.get("state"),
            "board_bag_path": board_row.get("bag_path"),
            "code_references": code,
            "doc_references": docs,
            "recommendation_reason": ("no live consumer + board bag still present"
                                      if (not code and board_row.get("state") in ("transferred", "ready"))
                                      else ("live consumer(s): " + ", ".join(code[:3]) if code
                                            else "board state=%s (local raw is the remaining copy)"
                                                 % board_row.get("state"))),
            "recommendation": ("delete_candidate" if (not code and board_row.get("state") in ("transferred", "ready"))
                               else "keep"),
        })
    payload = {"rule": "只删本地 captures/remote/<sid> 的未配平副本；源 bag（板端）、captures/leveled/<job_id>/ 不删",
               "verified_products": "02_LEVELING_*.json（本轮验证：帧数/点数/非XYZ行序/SHA 与源一致）",
               "candidates": rows}
    if args.write:
        with (Path(args.out) / "10_DELETION_CANDIDATES.json").open("x", encoding="utf8") as stream:
            json.dump(payload, stream, ensure_ascii=False, indent=2, allow_nan=False)
    for row in rows:
        print("%-24s %8.1f MB board=%-10s code_refs=%2d doc_refs=%2d -> %s" % (
            row["sid"], row["bytes_total"] / 1e6, row["board_state"], len(row["code_references"]),
            len(row["doc_references"]), row["recommendation"]))


if __name__ == "__main__":
    main()
