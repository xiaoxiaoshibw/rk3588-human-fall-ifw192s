"""Upload the isolated HF-04..06 round-2 tree to ldiar-wel and run device tests.

Passes the remote bash script as UTF-8 bytes (no text-mode newline translation)
to avoid the CRLF failure seen in round 1. No credentials are stored.
"""

import os
import subprocess
import sys
import tarfile

ROOT = r"D:\Code\ldiar"
EVIDENCE = os.path.join(ROOT, "docs", "human_fall", "evidence",
                        "2026-10-01_autonomous_hf04_06_r2")
TAR = os.path.join(EVIDENCE, "hf04_06_r2_verify.tar")
SCRIPT = os.path.join(EVIDENCE, "run_device_check.sh")
OUTPUT = os.path.join(EVIDENCE, "05_device_tests.txt")

INCLUDES = [
    "src/human_fall_detection",
    "src/human_follow_calibration/scripts/calibrate_human_follow.py",
    "docs/human_fall/evidence/review_hf04_06_codex.py",
]


def build_tar():
    with tarfile.open(TAR, "w") as archive:
        for relative in INCLUDES:
            archive.add(os.path.join(ROOT, relative), arcname=relative)


def main():
    build_tar()
    print("tar bytes:", os.path.getsize(TAR))
    subprocess.run(["scp", "-o", "BatchMode=yes", TAR,
                    "ldiar-wel:/tmp/hf04_06_r2_verify.tar"], check=True)
    with open(SCRIPT, encoding="utf-8") as handle:
        remote = handle.read().replace("\r\n", "\n").replace("\r", "\n")
    process = subprocess.run(["ssh", "-o", "BatchMode=yes", "ldiar-wel", "bash -s"],
                             input=remote.encode("utf-8"), capture_output=True, timeout=600)
    stdout = (process.stdout or b"").decode("utf-8", "replace")
    stderr = (process.stderr or b"").decode("utf-8", "replace")
    with open(OUTPUT, "w", encoding="utf-8") as handle:
        handle.write(stdout)
        handle.write(stderr)
    print("ssh exit:", process.returncode)
    print(stdout[-3000:])
    print(stderr[-1000:])
    return 0 if process.returncode == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
