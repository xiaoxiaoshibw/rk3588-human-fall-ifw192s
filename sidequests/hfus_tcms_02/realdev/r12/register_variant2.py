"""Register exactly one S07F region variant after the mechanism review."""
import time
from common2 import EV, OLD_EV, save, read, sha


def main():
    mech = read(EV / 'MECHANISM_SUPPORT_RULES_R3.json')
    dual = read(EV / 'MECHANISM_DUAL_POP_R3.json')
    old = read(OLD_EV / 'FG_NEW_SUMMARY.json')['hold']
    assert mech['rules']['OUTER_A|R0']['valid'] == 151 and mech['rules']['OUTER_A|R0']['max_step'] == round(old['nodes']['OUTER_A']['raw']['max_consecutive_step_mm'], 1)
    assert mech['mask_replica']['mismatch'] == []
    assert mech['rules']['OUTER_A|RB']['valid'] >= 136
    gaps = [f['largest_axis_gap'] for f in dual['frames'] if f['mask_n'] >= 2 and 183 <= f['fi'] < 334]
    save('REGION_PROTOCOL_V2.json', dict(
        version=2,
        epoch=time.time(),
        predecessor=dict(item='HFUS-TCMS-02-REALDEV-02-S07', region_protocol_sha=sha(OLD_EV / 'REGION_PROTOCOL_V1.json'), fg_new_outer_a_hold_valid=old['nodes']['OUTER_A']['raw']['valid_frames'], fg_new_outer_a_hold_max_step_mm=old['nodes']['OUTER_A']['raw']['max_consecutive_step_mm']),
        upstream_protocol_sha=sha(EV / 'PROTOCOL_V1.json'),
        acceptance_sha=sha(EV / 'ACCEPTANCE_V1.md'),
        mechanism_shas=[sha(EV / 'MECHANISM_SUPPORT_RULES_R3.json'), sha(EV / 'MECHANISM_DUAL_POP_R3.json')],
        evidence=dict(dual_population_separation_m={'min': min(gaps), 'max': max(gaps), 'n': len(gaps)}, rule_comparison={k: dict(valid=v['valid'], max_step=v['max_step'], drops=len(v['drops'])) for k, v in mech['rules'].items() if k.startswith('OUTER_A')}),
        hypothesis='OUTER_A/B support must be consistent with its own branch: restricted to the UPPER band [0.52,0.88). The previous [0.33,0.88) admitted a detached lower-fraction population about 0.83-0.86m away, so the mask median switched between populations. Keep the unchanged distal quantile 0.75 and all validity gates; verify the resulting support is one connected group.',
        method=dict(band='[0.52,0.88) same constant as upper_branch_band; distal quantile 0.75; no other threshold changed', connectivity='single-linkage 0.30m; intra-population spacing below 0.15m, dual-population separation 0.83-0.86m', scope='OUTER_A and OUTER_B node masks only; open/exit/standing phases use the same rule', state='NONE; no axis history, EMA, prediction, display fill or manual per-frame selection'),
        applicability=dict(coordinate='RAW/innolidar', session='cap_20261018_110029', fixed_roi='PROTOCOL_V1 ROI only', synthetic='explicit SYNTHETIC_IN_CONTRACT; not production', other_sessions='reject; never apply to old780 S3 input'),
        tests=['dual-population synthetic band inclusion/exclusion', 'single-support connectivity on synthetic', 'permutation determinism and no state', 'contract rejection (coordinate/session/rows/ROI/invalid)', 'non-OUTER nodes unchanged vs r11 on the same cloud'],
        stop='one variant only. Run raw_new2+fg_new2 once, frozen gates unchanged; failure retained and no promotion. No new thresholds/windows after observing outcomes.',
        semantic='UNVERIFIED_BODY_REGIONS_NOT_ANATOMICAL_JOINTS',
    ))
    print('registered REGION_PROTOCOL_V2', flush=True)


if __name__ == '__main__':
    main()
