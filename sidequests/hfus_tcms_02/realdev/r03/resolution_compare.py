"""G02 resolution comparison on FIT: 1024x512 (primary) vs 512x256 (probe)."""
import json, sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))
from s2core import load_source, OUT, write, validity, roles
import distance

if __name__ == '__main__':
    src, times = load_source()
    fit, _, _ = roles(times)
    out = {}
    for naz, nel in [(1024, 512), (512, 256)]:
        im = distance.build(src, fit, naz, nel)
        out['%dx%d' % (naz, nel)] = distance.stats(im)
        del im
    write(OUT / 'full_r1/DISTANCE_RESOLUTION_COMPARISON.json', out)
    print(json.dumps(out))
