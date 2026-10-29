"""Evaluate frozen gates, without tuning parameters or choosing windows."""
import json
from common import EV, read, save

groups={g:read(EV/(g+'_SUMMARY.json')) for g in ('RAW_OLD','FG_OLD','RAW_NEW','FG_NEW')}
base=groups['RAW_OLD']['hold'];candidate=groups['FG_NEW']['hold']
counts=read(EV/'FOREGROUND_COUNTS.json')['frames']
import numpy as np

def ratio(lo,hi):
    return float(np.median([r['foreground_rows'] for r in counts[lo:hi]])/np.median([r['roi_rows'] for r in counts[lo:hi]]))

checks={
    'six_coverage_136_of_151':candidate['six_frames']>=136,
    'chest_valid_136_of_151':candidate['nodes']['CHEST']['raw']['valid_frames']>=136,
    'outer_a_valid_136_of_151':candidate['nodes']['OUTER_A']['raw']['valid_frames']>=136,
    'no_total_valid_node_loss':candidate['total_valid_nodes']>=base['total_valid_nodes'],
    'outer_a_max_step_le_100mm':candidate['nodes']['OUTER_A']['raw']['max_consecutive_step_mm'] is not None and candidate['nodes']['OUTER_A']['raw']['max_consecutive_step_mm']<=100,
    'all_nodes_max_step_le_200mm':all(n['raw']['max_consecutive_step_mm'] is None or n['raw']['max_consecutive_step_mm']<=200 for n in candidate['nodes'].values()),
    'common_measurable_nodes_no_max_jump_regression':all(candidate['nodes'][k]['raw']['max_consecutive_step_mm'] is None or candidate['nodes'][k]['raw']['max_consecutive_step_mm']<=n['raw']['max_consecutive_step_mm'] for k,n in base['nodes'].items() if n['raw']['max_consecutive_step_mm'] is not None),
    'six_edges_current_measured_calibrated_ge_75_frames':sum(e['current_measured_calibrated_frames']>=75 for e in candidate['edges'].values())>=6,
    'empty_50_100_foreground_ratio_le_10pct':ratio(50,100)<=.1,
    'exit_376_386_foreground_ratio_le_20pct':ratio(376,386)<=.2,
}
save('EFFECT_GATE.json',dict(checks=checks,PASS=all(checks.values()),empty_ratio=ratio(50,100),exit_ratio=ratio(376,386),decision='NO_PROMOTION' if not all(checks.values()) else 'DEVELOPMENT_GATE_ONLY_NO_GENERALIZATION_CLAIM',joint_accuracy='BLOCKED',human_effect='BLOCKED',purity='UNKNOWN',recall='UNKNOWN'))
print(json.dumps(checks),flush=True)
