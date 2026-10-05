"""Independent full-record replay of exported XYZ, opaque bytes and source rows."""
import json
from pathlib import Path
import sys
import numpy as np

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "pc_apps" / "human_replay"))
import leveling as W
import validation as V

remote = ROOT / "captures" / "remote"; outroot = ROOT / "captures" / "leveled"
checks = []
for sid in ("cap_20261004_203349", "cap_20261004_203135", "cap_20261004_202456"):
    directory, meta, binding = W.source(remote, sid)
    job = V.latest(remote, outroot, sid, binding)
    report = job["report"]
    with np.load(outroot / job["job_id"] / "domain.npz") as domain:
        rows, held = domain["source_rows"], domain["holdout_rows"]
        assert len(np.unique(rows)) == len(rows)
        assert not len(np.intersect1d(rows, held))
    for method, hashes in job["artifacts"].items():
        target = outroot / job["job_id"] / method
        derived = json.loads((target / "meta.json").read_text(encoding="utf-8"))
        transform = json.loads((target / "transform.json").read_text(encoding="utf-8"))
        assert derived["frames"] == meta["frames"] and derived["total_points"] == meta["total_points"]
        assert all(transform[flag] is False for flag in ("physical_verified", "extrinsics_verified", "runtime_eligible"))
        assert transform["source"] == binding
        R, t = np.array(transform["R"]), np.array(transform["t"])
        count = 0
        with (directory / "points.bin").open("rb") as before, (target / "points.bin").open("rb") as after:
            for raw in iter(lambda: before.read(28*65536), b""):
                new = after.read(len(raw)); assert len(new) == len(raw)
                a = np.frombuffer(raw, dtype="u1").reshape(-1,28)
                b = np.frombuffer(new, dtype="u1").reshape(-1,28)
                xyz = np.ndarray((len(a),3),dtype="<f4",buffer=raw,strides=(28,4))
                actual = np.ndarray((len(b),3),dtype="<f4",buffer=new,strides=(28,4))
                valid = np.isfinite(xyz).all(axis=1) & np.any(xyz != 0, axis=1)
                assert np.array_equal(a[:,12:], b[:,12:])
                assert np.array_equal(a[~valid,:12], b[~valid,:12])
                expected = (xyz[valid].astype("f8") @ R.T + t).astype("<f4")
                assert np.array_equal(actual[valid], expected)
                count += len(a)
            assert after.read(1) == b""
        assert count == meta["total_points"]
        assert all(W.sha(target / name) == sha for name, sha in hashes.items())
        checks.append({"sid":sid,"job_id":job["job_id"],"method":method,"points":count,
                       "opaque_bytes":"PASS","xyz_full_replay":"PASS","frames_rows":"PASS","manifest_sha":"PASS"})
W.dump(Path(__file__).with_name("09_derivative_checks.json"), checks)
print(json.dumps(checks,ensure_ascii=False),flush=True)
