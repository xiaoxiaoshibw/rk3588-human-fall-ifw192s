"""Evaluate the ten frozen S07-06 checks for S07F plus the fix-specific criteria."""
import numpy as np
from common2 import EV, OLD_EV, save, read, jsonlines


def main():
    base = read(OLD_EV / 'RAW_OLD_SUMMARY.json')['hold']
    candidate = read(EV / 'FG_NEW2_SUMMARY.json')['hold']
    old_candidate = read(OLD_EV / 'FG_NEW_SUMMARY.json')['hold']
    counts = read(OLD_EV / 'FOREGROUND_COUNTS.json')['frames']

    def ratio(lo, hi):
        return float(np.median([r['foreground_rows'] for r in counts[lo:hi]]) / np.median([r['roi_rows'] for r in counts[lo:hi]]))

    checks = {
        'six_coverage_136_of_151': candidate['six_frames'] >= 136,
        'chest_valid_136_of_151': candidate['nodes']['CHEST']['raw']['valid_frames'] >= 136,
        'outer_a_valid_136_of_151': candidate['nodes']['OUTER_A']['raw']['valid_frames'] >= 136,
        'no_total_valid_node_loss': candidate['total_valid_nodes'] >= base['total_valid_nodes'],
        'outer_a_max_step_le_100mm': candidate['nodes']['OUTER_A']['raw']['max_consecutive_step_mm'] is not None and candidate['nodes']['OUTER_A']['raw']['max_consecutive_step_mm'] <= 100,
        'all_nodes_max_step_le_200mm': all(n['raw']['max_consecutive_step_mm'] is None or n['raw']['max_consecutive_step_mm'] <= 200 for n in candidate['nodes'].values()),
        'common_measurable_nodes_no_max_jump_regression': all(candidate['nodes'][k]['raw']['max_consecutive_step_mm'] is None or candidate['nodes'][k]['raw']['max_consecutive_step_mm'] <= n['raw']['max_consecutive_step_mm'] for k, n in base['nodes'].items() if n['raw']['max_consecutive_step_mm'] is not None),
        'six_edges_current_measured_calibrated_ge_75_frames': sum(e['current_measured_calibrated_frames'] >= 75 for e in candidate['edges'].values()) >= 6,
        'empty_50_100_foreground_ratio_le_10pct': ratio(50, 100) <= .1,
        'exit_376_386_foreground_ratio_le_20pct': ratio(376, 386) <= .2,
    }
    records = jsonlines(EV / 'FG_NEW2_FRAMES.jsonl')
    old_records = jsonlines(OLD_EV / 'FG_NEW_FRAMES.jsonl')
    hold = [r for r in records if 183 <= r['fi'] < 334]
    drops = [r['fi'] for r in hold if not r['nodes']['OUTER_A']['valid']]
    prior_valid = {r['fi']: r['nodes']['OUTER_A']['valid'] for r in old_records}
    new_invalid_vs_s07 = [fi for fi in drops if prior_valid.get(fi)]
    valid_pts = [(r['fi'], np.asarray(r['nodes']['OUTER_A']['xyz'])) for r in hold if r['nodes']['OUTER_A']['valid']]
    span = [(a, b, round(float(np.linalg.norm(bb - aa) * 1000), 1)) for (a, aa), (b, bb) in zip(valid_pts, valid_pts[1:]) if b > a + 1]
    fix = dict(
        outer_a_max_step_le_100mm=checks['outer_a_max_step_le_100mm'],
        outer_a_valid_ge_136=checks['outer_a_valid_136_of_151'],
        drops_le_10=len(drops) <= 10,
        dropped_frames=drops,
        dropped_all_were_valid_in_s07=new_invalid_vs_s07 == drops,
        dropped_reasons='see VERIFY2.json (mask size and span-gate recomputation per dropped frame)',
        spanning_steps=span,
        spanning_max_mm=None if not span else max(x for _, _, x in span),
        s07_reference=dict(valid=old_candidate['nodes']['OUTER_A']['raw']['valid_frames'], max_step_mm=old_candidate['nodes']['OUTER_A']['raw']['max_consecutive_step_mm']),
    )
    fix_pass = fix['outer_a_max_step_le_100mm'] and fix['outer_a_valid_ge_136'] and fix['drops_le_10']
    ten = int(sum(checks.values()))
    save('EFFECT_GATE2.json', dict(
        frozen_checks=checks, FROZEN_ALL_PASS=all(checks.values()), ten_passed=ten, ten_total=10,
        s07_ten_passed=int(sum(read(OLD_EV / 'EFFECT_GATE.json')['checks'].values())),
        fix=fix, fix_pass=fix_pass,
        decision='DEVELOPMENT_GATE_ONLY_NO_GENERALIZATION_CLAIM' if all(checks.values()) else 'NO_PROMOTION',
        empty_ratio=ratio(50, 100), exit_ratio=ratio(376, 386),
        joint_accuracy='BLOCKED', human_effect='BLOCKED', purity='UNKNOWN', recall='UNKNOWN'))
    print('frozen passed', ten, 'of 10:', [k for k, v in checks.items() if not v], 'failed')
    print('fix_pass', fix_pass, 'drops', drops, 'spanning', span)
    for k in candidate['nodes']:
        c = candidate['nodes'][k]['raw']
        b = base['nodes'][k]['raw']
        o = old_candidate['nodes'][k]['raw']
        print('%-13s valid now/s07 %3d/%3d max now/base/s07 %s/%s/%s' % (
            k, c['valid_frames'], o['valid_frames'],
            None if c['max_consecutive_step_mm'] is None else round(c['max_consecutive_step_mm'], 1),
            None if b['max_consecutive_step_mm'] is None else round(b['max_consecutive_step_mm'], 1),
            None if o['max_consecutive_step_mm'] is None else round(o['max_consecutive_step_mm'], 1)))
    for key, e in candidate['edges'].items():
        print('edge %-25s measured=%3d cal>=75 now/s07 %3d/%3d' % (key, e['measured_frames'], e['current_measured_calibrated_frames'], old_candidate['edges'][key]['current_measured_calibrated_frames']))


if __name__ == '__main__':
    main()
