"""Record the argmax frame of the FG_NEW2-vs-S07 OUTER_A position delta."""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'r11'))

import numpy as np
from common2 import EV, OLD_EV, save, jsonlines


def main():
    new = jsonlines(EV / 'FG_NEW2_FRAMES.jsonl')
    old = jsonlines(OLD_EV / 'FG_NEW_FRAMES.jsonl')
    best = None
    n = 0
    for r in new[183:334]:
        o = old[r['fi']]['nodes']['OUTER_A']
        m = r['nodes']['OUTER_A']
        if o['valid'] and m['valid']:
            n += 1
            d = float(np.linalg.norm(np.asarray(m['xyz']) - np.asarray(o['xyz'])) * 1000)
            if best is None or d > best[1]:
                best = (r['fi'], d)
    save('VERIFY2_DELTA_ARGMAX.json', dict(
        n=n, argmax_frame=best[0], argmax_mm=round(best[1], 2),
        note='Recomputed from FG_NEW2_FRAMES vs S07 FG_NEW_FRAMES, hold window, both-valid frames only. Closes static-review non-blocking item NB4 (argmax frame now stored). The argmax is the frame where the S07 median sat in the lower-fraction population that this variant excludes.',
        source='FG_NEW2_FRAMES.jsonl + 2026-10-18_hfus_tcms_02_s07_r1/FG_NEW_FRAMES.jsonl'))
    print('argmax', best, 'n', n, flush=True)


if __name__ == '__main__':
    main()
