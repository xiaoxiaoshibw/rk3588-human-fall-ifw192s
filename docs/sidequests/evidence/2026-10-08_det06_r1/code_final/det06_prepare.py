"""DET-06: bind and level the five new C1 sessions + new empty template; original captures read-only.

Mirrors DET-02 prepare_background.py (same leveling request, same prepared-frame layout), but for the
2026-10-08 sessions. No reuse branch: these sessions have no previous leveling artifacts.
"""
import argparse
import json
from pathlib import Path
import sys

import numpy as np
from experiment import adapt, read_frame, sha

NEW_SESSIONS = ["cap_20261008_114205", "cap_20261008_114254", "cap_20261008_114340",
                "cap_20261008_114422", "cap_20261008_114819"]


def rotation_angle(r):
    return float(np.degrees(np.arccos(np.clip((np.trace(r) - 1) / 2, -1, 1))))


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--data-root", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    a.out.mkdir(parents=True, exist_ok=False)
    repo = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(repo / "pc_apps/human_replay"))
    import leveling
    records = []
    for sid in NEW_SESSIONS:
        directory, meta, binding = leveling.source(a.data_root, sid)
        print("BEGIN", sid, flush=True)
        request = leveling.validate_request(dict(schema=1, sid=sid, source=binding,
            config=dict(mode="auto", pitch_deg=26, roll_deg=0, physical_height_m=1.1)))
        report, _ = leveling.run_job(a.data_root, a.out / "leveling", request, sid,
                                     lambda msg: print(sid, msg, flush=True))
        if not report["estimators"]["tls"]["valid"]:
            raise ValueError("TLS quality failed: " + sid)
        transform_path = a.out / "leveling" / sid / "tls/transform.json"
        transform = json.loads(transform_path.read_text(encoding="utf-8"))
        if transform["source"] != binding:
            raise ValueError("transform source changed")
        target = a.out / sid
        target.mkdir()
        frames = []
        for index, f in enumerate(meta["frames"]):
            points, _ = read_frame(directory, index)
            valid = np.any(points[:, :3] != 0, axis=1)
            cloud = adapt(points, transform, 0, 1)
            name = "frame_%06d.bin" % index
            cloud.astype("<f4").tofile(target / name)
            rows = np.flatnonzero(valid).astype("<i8") + f["offset_points"]
            rows.tofile(target / (name + ".rows"))
            frames.append(dict(index=index, seq=f["seq"], file=name, points=len(cloud),
                               source_points=len(points), sha256=sha(target / name),
                               rows_sha256=sha(target / (name + ".rows"))))
        if leveling.source(a.data_root, sid)[2] != binding:
            raise ValueError("input changed during preparation")
        records.append(dict(sid=sid, role="empty_reference" if sid.endswith("114819") else "human_target",
                            name=meta.get("name"), source=binding, raw_directory=str(directory),
                            transform_path=str(transform_path.resolve()), transform_sha256=sha(transform_path),
                            leveling_reused=False, leveling_recommended=report.get("recommended"), tls_valid=True,
                            R=transform["R"], t=transform["t"], physical_verified=False, frames=frames))
        print("END", sid, "frames", len(frames), flush=True)
    reference = next(r for r in records if r["role"] == "empty_reference")
    r0, t0 = np.asarray(reference["R"]), np.asarray(reference["t"])
    for r in records:
        if r is reference:
            continue
        rk, tk = np.asarray(r["R"]), np.asarray(r["t"])
        rel, dt = rotation_angle(r0.T @ rk), float(np.linalg.norm(tk - t0))
        r["rel_to_empty_deg"], r["rel_to_empty_t_m"] = rel, dt
        print("DELTA %s rel_deg=%.3f t_m=%.3f" % (r["sid"][-6:], rel, dt), flush=True)
    (a.out / "manifest.json").write_text(json.dumps(dict(
        empty_template_confirmed=True,
        user_confirmation=("2026-10-08 user: 114819 empty throughout; C1 is a different person than the four "
                           "2026-10-07 sessions; same room; lidar not moved between sessions"),
        sessions=records), indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
