"""GL-A R2：修复前后样例 manifest 字节差异定位（只读对照，非生产代码）。"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
BEFORE = HERE.parent / "2026-10-05_agl_a_r1" / "20_sample_manifest.json"
AFTER = HERE / "20_sample_manifest_after_fix.json"


def walk(first, second, path=""):
    if type(first) is not type(second):
        print("TYPE", path)
        return
    if isinstance(first, dict):
        for key in first:
            walk(first[key], second[key], path + "/" + str(key))
    elif isinstance(first, list):
        for index, (old, new) in enumerate(zip(first, second)):
            walk(old, new, path + "/" + str(index))
    elif first != second:
        delta = (second - first) if isinstance(first, (int, float)) else ""
        print("%s | %r -> %r | delta=%s" % (path, first, second, delta))


def main():
    before = json.loads(BEFORE.read_text(encoding="utf8"))
    after = json.loads(AFTER.read_text(encoding="utf8"))
    walk(before, after)
    print("diff-scan-complete")
    return 0


if __name__ == "__main__":
    sys.exit(main())
