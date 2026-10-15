"""T2 配平：调用既有 leveling 管线（pc_apps/human_replay/leveling.run_job）。

用法：
    python -B -W error level_sessions.py --out <evidence_dir> <sid> [<sid> ...]
- 只对 captures/remote/<sid> 做自动（auto）配平；输出落 captures/leveled/<job_id>/（既有产物目录）。
- 产物验证：帧数/点数/非XYZ字节行序与源逐行一致、源SHA绑定一致、report/manifest 完整。
- 失败显式记录（不降门、不重试其它区域）。
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np

from common import LEVELED, REMOTE, sha256_file

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "pc_apps/human_replay"))
import leveling  # noqa: E402

NOMINAL = {"pitch_deg": 26.0, "roll_deg": 0.0, "physical_height_m": 1.14, "mode": "auto"}


def _opaque_columns(directory, meta):
    """intensity/ring/timestamp (bytes 12..27) as (N,16) uint8 for row-order checks."""
    raw = np.memmap(directory / "points.bin", dtype="u1", mode="r")
    rows = np.ndarray((int(meta["total_points"]), 28), dtype="u1", buffer=raw)
    return rows[:, 12:28]


def verify_job(sid, job_id):
    source_dir, source_meta, binding = leveling.source(REMOTE, sid)
    out = LEVELED / job_id
    report = json.loads((out / "report.json").read_text(encoding="utf8"))
    manifest = json.loads((out / "manifest.json").read_text(encoding="utf8"))
    result = {
        "sid": sid, "job_id": job_id, "source": binding,
        "report_sha256": sha256_file(out / "report.json"),
        "manifest_report_sha256": manifest.get("report_sha256"),
        "manifest_domain_sha256": manifest.get("domain_sha256"),
        "domain_sha256": sha256_file(out / "domain.npz"),
        "recommended": report.get("recommended"),
        "holdout_ordinals": report.get("holdout_ordinals"),
        "fit_point_count": report.get("fit_point_count"),
        "estimators": {},
        "artifacts": {},
    }
    for name, estimate in report["estimators"].items():
        result["estimators"][name] = {
            "valid": estimate.get("valid"), "reject_reasons": estimate.get("reject_reasons"),
            "pitch_deg": estimate.get("pitch_deg"), "roll_deg": estimate.get("roll_deg"),
            "offset_source_m": estimate.get("offset_source_m"),
            "full": (estimate.get("full") or {}).get("status"),
            "per_region": {k: v.get("status") for k, v in (estimate.get("per_region") or {}).items()},
            "holdouts": [{str(h.get("ordinal")): {k: v.get("status") for k, v in (h.get("regions") or {}).items()}
                          for h in (estimate.get("holdouts") or [])}],
        }
    source_opaque = None
    for name, files in (manifest.get("artifacts") or {}).items():
        target = out / name
        leveled_meta = json.loads((target / "meta.json").read_text(encoding="utf8"))
        frame_ok = len(leveled_meta["frames"]) == len(source_meta["frames"]) and all(
            a["offset_points"] == b["offset_points"] and a["count_points"] == b["count_points"]
            and a["seq"] == b["seq"]
            for a, b in zip(leveled_meta["frames"], source_meta["frames"]))
        size_ok = (target / "points.bin").stat().st_size == int(source_meta["total_points"]) * 28
        transform = json.loads((target / "transform.json").read_text(encoding="utf8"))
        binding_ok = transform.get("source") == binding
        sha_ok = all(sha256_file(target / f) == files[f] for f in leveling.FILES)
        if source_opaque is None:
            source_opaque = _opaque_columns(source_dir, source_meta)
        opaque_ok = bool(np.array_equal(_opaque_columns(target, source_meta), source_opaque))
        result["artifacts"][name] = {
            "files": files, "frames_ok": bool(frame_ok), "point_counts_ok": bool(size_ok),
            "row_order_opaque_bytes_equal": opaque_ok, "source_binding_ok": bool(binding_ok),
            "sha_ok": bool(sha_ok),
            "verified": bool(frame_ok and size_ok and opaque_ok and binding_ok and sha_ok),
        }
    result["deletable_candidate"] = bool(result["artifacts"]) and all(
        a["verified"] for a in result["artifacts"].values())
    return report, manifest, result


def run_one(sid):
    _, _, binding = leveling.source(REMOTE, sid)
    job_id = leveling.uuid.uuid4().hex
    print("LEVELING %s job=%s" % (sid, job_id), flush=True)
    messages = []
    report, _artifacts = leveling.run_job(
        REMOTE, LEVELED, {"sid": sid, "source": binding, "config": dict(NOMINAL)},
        job_id, messages.append)
    print("  recommended=%s estimators=%s" % (
        report.get("recommended"),
        {k: v.get("valid") for k, v in report["estimators"].items()}), flush=True)
    return job_id


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    parser.add_argument("--verify-only", action="store_true")
    parser.add_argument("--job", action="append", default=[], help="sid=job_id for --verify-only")
    parser.add_argument("sids", nargs="*")
    args = parser.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    jobs = {}
    if args.verify_only:
        for pair in args.job:
            sid, job_id = pair.split("=")
            jobs[sid] = job_id
    else:
        for sid in args.sids:
            jobs[sid] = run_one(sid)
    for sid, job_id in jobs.items():
        report, manifest, result = verify_job(sid, job_id)
        payload = {"job_id": job_id, "verification": result, "report": report}
        with (out / ("02_LEVELING_%s.json" % sid)).open("x", encoding="utf8") as stream:
            json.dump(payload, stream, ensure_ascii=False, indent=2, allow_nan=False)
        print("VERIFY %s deletable_candidate=%s" % (sid, result["deletable_candidate"]), flush=True)


if __name__ == "__main__":
    main()
