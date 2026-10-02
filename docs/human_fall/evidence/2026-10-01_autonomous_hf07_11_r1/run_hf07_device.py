"""Upload the isolated HF-07 tree to ldiar-wel and run build + protocol checks.

The remote bash script is sent as UTF-8 bytes (no text-mode newline translation)
to avoid the CRLF failure seen in earlier rounds. No credentials are stored.
"""

import os
import subprocess
import sys
import tarfile

ROOT = r"D:\Code\ldiar"
EVIDENCE = os.path.join(ROOT, "docs", "human_fall", "evidence",
                        "2026-10-01_autonomous_hf07_11_r1")
TAR = os.path.join(EVIDENCE, "hf07_verify_r1.tar")
SCRIPT = os.path.join(EVIDENCE, "01_build_and_verify.sh")
OUTPUT = os.path.join(EVIDENCE, "02_device_tests.txt")

INCLUDES = [
    "src/human_fall_detection",
    "src/human_follow_calibration",
    "docs/human_fall/evidence/2026-10-01_autonomous_hf07_11_r1/hf07_ground.json",
    "docs/human_fall/evidence/2026-10-01_autonomous_hf07_11_r1/hf07_verify.yaml",
    "docs/human_fall/evidence/2026-10-01_autonomous_hf07_11_r1/hf07_verify_integration.py",
    "docs/human_fall/evidence/2026-10-01_autonomous_hf07_11_r1/probe_imports.py",
    "docs/human_fall/evidence/review_hf07_codex.py",
    "docs/human_fall/evidence/review_hf04_06_codex.py",
]


def _skip_pycache(info):
    if "__pycache__" in info.name.split("/"):
        return None
    return info


def build_tar():
    with tarfile.open(TAR, "w") as archive:
        for relative in INCLUDES:
            archive.add(os.path.join(ROOT, relative), arcname=relative,
                        filter=_skip_pycache)


def main():
    build_tar()
    print("tar bytes:", os.path.getsize(TAR))
    subprocess.run(["scp", "-o", "BatchMode=yes", TAR,
                    "wel@192.168.3.125:/tmp/hf07_verify_r1.tar"], check=True)
    with open(SCRIPT, encoding="utf-8") as handle:
        remote = handle.read().replace("\r\n", "\n").replace("\r", "\n")
    process = subprocess.run(
        ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=20",
         "wel@192.168.3.125", "bash -s"],
        input=remote.encode("utf-8"), capture_output=True, timeout=1800)
    stdout = (process.stdout or b"").decode("utf-8", "replace")
    stderr = (process.stderr or b"").decode("utf-8", "replace")
    with open(OUTPUT, "w", encoding="utf-8") as handle:
        handle.write(stdout)
        handle.write("\n--- STDERR ---\n")
        handle.write(stderr)
    print("ssh exit:", process.returncode)
    print(stdout[-6000:])
    if stderr.strip():
        print("--- STDERR ---")
        print(stderr[-2000:])
    return 0 if process.returncode == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
