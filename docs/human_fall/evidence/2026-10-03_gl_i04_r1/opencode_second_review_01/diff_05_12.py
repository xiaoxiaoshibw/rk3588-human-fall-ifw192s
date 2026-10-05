"""Locate fields differing between 05_real_diagnostic and 12_real_final."""
import json
from pathlib import Path

RUN = Path(r"D:/Code/ldiar/docs/human_fall/evidence/2026-10-03_gl_i04_r1")
a = json.loads((RUN / "05_real_diagnostic/diagnostic.json").read_text(encoding="utf-8"))
b = json.loads((RUN / "12_real_final/diagnostic.json").read_text(encoding="utf-8"))


def walk(x, y, path=""):
    if type(x) is not type(y):
        yield path, x, y
    elif isinstance(x, dict):
        for k in sorted(set(x) | set(y)):
            yield from walk(x.get(k, "<MISSING>"), y.get(k, "<MISSING>"), path + "/" + str(k))
    elif isinstance(x, list):
        if len(x) != len(y):
            yield path + "/len", len(x), len(y)
        else:
            for i, (u, v) in enumerate(zip(x, y)):
                yield from walk(u, v, path + "[%d]" % i)
    elif x != y:
        yield path, x, y


diffs = list(walk(a, b))
print("num_field_diffs:", len(diffs))
for path, x, y in diffs[:40]:
    sx, sy = json.dumps(x)[:120], json.dumps(y)[:120]
    print(path, "\n  05:", sx, "\n  12:", sy)
