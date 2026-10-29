"""S07F figures: OUTER_A hold series and step comparison (English labels)."""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'r11'))

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from common2 import EV, OLD_EV, jsonlines


def main():
    new = jsonlines(EV / 'FG_NEW2_FRAMES.jsonl')
    old = jsonlines(OLD_EV / 'FG_NEW_FRAMES.jsonl')
    hold = list(range(183, 334))
    zo = [old[fi]['nodes']['OUTER_A']['xyz'][2] if old[fi]['nodes']['OUTER_A']['valid'] else np.nan for fi in hold]
    zn = [new[fi]['nodes']['OUTER_A']['xyz'][2] if new[fi]['nodes']['OUTER_A']['valid'] else np.nan for fi in hold]
    fig, ax = plt.subplots(figsize=(10, 3.6))
    ax.plot(hold, zo, '.-', ms=3, lw=.8, color='0.6', label='S07 FG_NEW (r11 band [0.33,0.88))')
    ax.plot(hold, zn, '.-', ms=3, lw=.8, color='crimson', label='S07F FG_NEW2 (branch band [0.52,0.88))')
    ax.set_xlabel('frame index')
    ax.set_ylabel('OUTER_A raw z (m)')
    ax.set_title('OUTER_A hold [183,334): representative raw z')
    ax.legend()
    ax.grid(alpha=.3)
    fig.tight_layout()
    fig.savefig(EV / 'OUTER_A_HOLD_SERIES.png', dpi=130)
    plt.close(fig)

    def steps(recs):
        res = []
        for a, b in zip(recs, recs[1:]):
            if b['fi'] == a['fi'] + 1 and a['nodes']['OUTER_A']['valid'] and b['nodes']['OUTER_A']['valid']:
                res.append((b['fi'], float(np.linalg.norm(np.asarray(b['nodes']['OUTER_A']['xyz']) - np.asarray(a['nodes']['OUTER_A']['xyz'])) * 1000)))
        return res

    so = steps(old[183:334])
    sn = steps(new[183:334])
    fig, ax = plt.subplots(figsize=(10, 3.6))
    ax.plot([f for f, _ in so], [v for _, v in so], '.', ms=4, color='0.6', label='S07 FG_NEW')
    ax.plot([f for f, _ in sn], [v for _, v in sn], '.', ms=4, color='crimson', label='S07F FG_NEW2')
    ax.axhline(100, color='k', ls='--', lw=.8, label='100 mm gate')
    ax.axhline(200, color='k', ls=':', lw=.8, label='200 mm gate')
    ax.set_yscale('log')
    ax.set_xlabel('frame index')
    ax.set_ylabel('consecutive step (mm, log)')
    ax.set_title('OUTER_A consecutive steps (hold)')
    ax.legend()
    ax.grid(alpha=.3)
    fig.tight_layout()
    fig.savefig(EV / 'OUTER_A_HOLD_STEPS.png', dpi=130)
    plt.close(fig)
    print('figures saved', flush=True)


if __name__ == '__main__':
    main()
