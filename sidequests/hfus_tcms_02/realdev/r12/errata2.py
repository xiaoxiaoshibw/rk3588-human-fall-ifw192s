"""Errata for the REGION_PROTOCOL_V2 separation statistic (branch-mixed entries)."""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'r11'))

from common2 import EV, save, read, sha


def main():
    dual = read(EV / 'MECHANISM_DUAL_POP_R3.json')
    seen = set()
    A = []
    B = []
    for f in dual['frames']:
        fi = f['fi']
        (A if fi not in seen else B).append(f)
        seen.add(fi)
    assert len(A) == len(B), 'expected paired OUTER_A/OUTER_B entries per frame'
    ag = [f['largest_axis_gap'] for f in A if f['mask_n'] >= 2]
    bg = [f['largest_axis_gap'] for f in B if f['mask_n'] >= 2]
    f190 = sorted((f['fi'], round(f['largest_axis_gap'], 4)) for f in A if f['fi'] in (190, 191, 192))
    save('REGION_PROTOCOL_V2_ERRATA.json', dict(
        subject='REGION_PROTOCOL_V2.json evidence.dual_population_separation_m; MECHANISM_DUAL_POP_R3.json entry interleaving',
        finding='The separation field in REGION_PROTOCOL_V2 was computed over OUTER_A and OUTER_B entries together because MECHANISM_DUAL_POP_R3.json stores both branches per frame (first entry OUTER_A, second OUTER_B). The registered minimum 0.08 is an OUTER_B small-gap value, not the OUTER_A dual-population separation.',
        outer_a=dict(n=len(ag), min=round(min(ag), 4), max=round(max(ag), 4), f190_192=f190,
                     note='OUTER_A case-frame separations; f190-192 are 0.8379/0.8548/0.8553 m, matching the registered hypothesis sentence about 0.83-0.86 m.'),
        outer_b=dict(n=len(bg), min=round(min(bg), 4), max=round(max(bg), 4),
                     note='OUTER_B is a single large support in the hold (no dual-population switch); its largest internal gap is 0.08-0.25 m.'),
        field_note='For second (OUTER_B) entries, comps/largest_axis_gap are OUTER_B values while median_r0 was copied from OUTER_A; that field is unused for any decision.',
        impact='No threshold, variant selection, run or gate depends on the mixed statistic. No registered or historical file is modified; this errata is appended evidence. The OUTER_A f190-192 values and the 0.60-0.86 m case-frame range above are the correct reference.',
        registered_file_sha=sha(EV / 'REGION_PROTOCOL_V2.json'),
    ))
    print('errata written; A-side n=%d min=%s max=%s; B-side n=%d min=%s max=%s' % (
        len(ag), round(min(ag), 4), round(max(ag), 4), len(bg), round(min(bg), 4), round(max(bg), 4)), flush=True)


if __name__ == '__main__':
    main()
