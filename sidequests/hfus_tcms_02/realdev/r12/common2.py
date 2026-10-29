"""S07F common paths/helpers (r12); no writes outside explicit save() calls."""
import importlib.util
import sys
from pathlib import Path
from register2 import ROOT, EV, HERE, sha, put

OLD_EV = ROOT / 'docs/human_fall/evidence/2026-10-18_hfus_tcms_02_s07_r1'


def module(name, p):
    spec = importlib.util.spec_from_file_location(name, p)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


sys.path.insert(0, str(HERE.parent / 'r08'))
import wire as W  # noqa: E402  (frozen r08)
sys.path.insert(0, str(W.R04S))
SK = W.r04_skeleton()


def save(name, value):
    put(EV / name, value)


def read(p):
    return W.load(p)


def jsonlines(p):
    import json
    with Path(p).open(encoding='utf8') as f:
        return [json.loads(line) for line in f]
