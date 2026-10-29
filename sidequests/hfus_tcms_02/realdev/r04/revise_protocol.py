"""Protocol revision before any domain is frozen: v1 -> v2 (domain selection constraints only).

v1 required a 0.05 m clearance from every S2 rectangle. The FIT-only probe showed that no
0.4x0.4 m cell inside the visible floor core can satisfy that clearance while reaching the
0.9 purity target, because the seven S2 audit patches already occupy that core. The plan
itself only requires non-overlap, so v2 keeps exact non-overlap (gap reported) and makes the
purity target an eligibility floor plus a reported target instead of a hard gate.
No verification gate, M0 parameter or application-chain parameter changes.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import s3core as C

if __name__ == '__main__':
    v1 = C.load(C.OUT / 'PROTOCOL_V1.json')
    v2 = dict(v1, version=2, revision_reason=(
        'domain-selection constraints only: exact non-overlap replaces the 0.05 m clearance '
        '(unsatisfiable inside the pure floor core that S2 occupies), purity floor 0.85 with a '
        '0.9 target reported instead of a hard 0.9 gate, 0.1 m anchor grid and a deterministic '
        'top-3 rule; verification gates, M0 parameters and application-chain parameters unchanged'))
    v2['domains'] = dict(v1['domains'])
    v2['domains'].update(
        selection_rule='three cells with the highest exact FIT purity among cells that are non-overlapping with '
                       'all 7 S2 patches in S3_LOCAL, have >= 60 FIT rows in every FIT frame, are pairwise >= 0.6 m '
                       'apart, and reach the 0.85 eligibility floor',
        s2_clearance_m=0.0,
        s2_clearance_rule='exact non-overlap in S3_LOCAL against every S2 rectangle (dense 0.02 m boundary samples '
                          'mapped from the historical frame); the achieved rectangle gap is reported per patch; '
                          'zero shared source rows with S2 is enforced',
        purity_min=0.85,
        purity_target=0.9,
        purity_target_rule='a target, not a gate: the S2 core is fully occupied, so the third patch may fall just '
                           'below 0.9; the achieved purity is reported and the patch gate still needs 2/3',
        anchor_m=0.1,
        search=dict(u=[0.4, 2.0], v=[-0.2, 2.0]))
    v2['protocol_history'] = dict(v1_sha=C.sha(C.OUT / 'PROTOCOL_V1.json'),
                                  v1_used_for='bootstrap source/baseline only; never for a frozen domain or a run')
    C.write(C.OUT / 'PROTOCOL_V2.json', v2)
    print(C.sha(C.OUT / 'PROTOCOL_V2.json'))
