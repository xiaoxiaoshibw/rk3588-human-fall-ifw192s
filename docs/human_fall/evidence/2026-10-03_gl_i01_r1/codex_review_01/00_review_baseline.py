# GL-I01/R1 independent review - baseline verification (read-only).
# Recomputes SHAs of the whitelist sources, frozen assets and the real capture,
# and compares them against the implementer return + the pre-round baseline.

import hashlib
import io
import json
import os
import sys

REPO_ROOT = os.path.abspath(os.getcwd())
EVIDENCE = os.path.join(REPO_ROOT, "docs", "human_fall", "evidence",
                        "2026-10-03_gl_i01_r1")


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main():
    declared = {
        "src/human_fall_detection/core/capture_input.py":
            "56355e9594433d91c871685f58c6ae9f8fe0e47d2b3ad7d07f9b5b8050b85f16",
        "src/human_fall_detection/scripts/prepare_capture_input.py":
            "648a8da63a6656b02d169957cede2df4aca3a48e94dcc787c3c48c7f10c5d000",
        "src/human_fall_detection/scripts/calibrate_sensors.py":
            "3f30cf945d70b06f0fce22bdec9ba738f774f98dde2f9a33ce466eeaf9c6c785",
        "src/human_fall_detection/tests/test_gli01_capture_input.py":
            "50f615d7a5ffdc490f1011b316df30da1e65c958cce93f18ad4cf0c88547030e",
    }
    result = {"whitelist": {}, "frozen": {}, "capture": {}}
    ok = True
    for relpath, expected in declared.items():
        actual = sha256_file(os.path.join(REPO_ROOT, relpath))
        match = actual == expected
        ok = ok and match
        result["whitelist"][relpath] = {"expected": expected, "actual": actual,
                                        "match": match}

    frozen = [
        "src/human_fall_detection/core/ground.py",
        "src/human_fall_detection/core/calibration.py",
        "src/human_capture/scripts/capture_server.py",
        "src/human_capture/core/bag2session.py",
    ]
    with io.open(os.path.join(EVIDENCE, "00_before_manifest.json"),
                 encoding="utf-8") as handle:
        baseline = json.load(handle)["files"]
    for relpath in frozen:
        full = os.path.join(REPO_ROOT, relpath)
        entry = baseline.get(relpath)
        if entry is None:
            result["frozen"][relpath] = {"error": "missing from baseline"}
            ok = False
            continue
        before = entry["sha256"]
        actual = sha256_file(full)
        match = actual == before
        ok = ok and match
        result["frozen"][relpath] = {"before": before, "actual": actual,
                                     "match": match}

    capture = {
        "captures/remote/cap_20261002_163621/meta.json":
            "675c23ded9dcee82e6e985f17665469a487d34520408582708601eb188b1d692",
        "captures/remote/cap_20261002_163621/points.bin":
            "b81797f9825792655e5930edeb39c15275eb64e01999984884da61d252c599ff",
    }
    for relpath, expected in capture.items():
        actual = sha256_file(os.path.join(REPO_ROOT, relpath))
        match = actual == expected
        ok = ok and match
        result["capture"][relpath] = {"expected": expected, "actual": actual,
                                      "match": match}

    out = os.path.join(EVIDENCE, "codex_review_01", "00_review_baseline.json")
    with io.open(out, "w", encoding="utf-8") as handle:
        json.dump(result, handle, indent=1, ensure_ascii=False)
        handle.write("\n")
    print(json.dumps({"all_match": ok, "repo_root": REPO_ROOT},
                     ensure_ascii=False))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
