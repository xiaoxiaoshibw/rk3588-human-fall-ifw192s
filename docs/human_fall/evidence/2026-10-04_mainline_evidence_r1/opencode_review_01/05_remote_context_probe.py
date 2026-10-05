"""GL-E01 R1 independent bounded recording-context probe (remote, read-only).

Reads only the named config/log paths and a non-recursive config.yaml* listing;
reports SHA-256, size, mtime and any enabled extrinsic/use_status lines. Makes
no recording-time binding claim.
"""
import datetime
import hashlib
import json
from pathlib import Path

FILES = ["/root/catkin_ws/src/inno_lidar_ros/config/config.yaml",
         "/var/log/inno_lidar.log",
         "/tmp/lidar.log"]


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    out = []
    for name in FILES:
        p = Path(name)
        item = dict(path=name, exists=p.is_file(), recording_binding="unknown")
        if p.is_file():
            st = p.stat()
            hits = []
            with p.open("r", encoding="utf-8", errors="replace") as f:
                for i, line in enumerate(f, 1):
                    low = line.lower()
                    if any(k in low for k in ("extrinsic", "use_status", "roll:",
                                              "pitch:", "yaw:", "x:", "y:", "z:")):
                        hits.append(i)
            item.update(sha256=sha(p), size=st.st_size,
                        mtime_utc=datetime.datetime.fromtimestamp(
                            st.st_mtime, datetime.timezone.utc).isoformat(),
                        matched_line_numbers=hits[:40])
        out.append(item)
    cfg_dir = Path("/root/catkin_ws/src/inno_lidar_ros/config")
    archives = sorted(dict(name=q.name, size=q.stat().st_size)
                      for q in cfg_dir.glob("config.yaml*") if q.is_file())
    print(json.dumps(dict(kind="gle01_r1_independent_remote_context", schema=1,
                          files=out, config_dir_archives=archives,
                          recording_config_binding="unknown", from_to_measured=False,
                          ground_region_identity=False, physical_verified=False)))


if __name__ == "__main__":
    main()
