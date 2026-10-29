import importlib.util
import sys
from pathlib import Path
from register import ROOT, EV, HERE, sha, put

def module(name, p):
    spec = importlib.util.spec_from_file_location(name, p)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m

sys.path.insert(0, str(HERE.parent/'r08'))
import wire as W
sys.path.insert(0, str(W.R04S))
SK = W.r04_skeleton()

def save(name, value):
    put(EV/name, value)

def read(p):
    return W.load(p)

def jsonlines(p):
    import json
    with Path(p).open(encoding='utf8') as f: return [json.loads(line) for line in f]

