# B1 自写探针：v2 是否在 B 层阈值上硬编码字面量（绕过冻结的 PROFILE）
import re, sys
sys.path.insert(0, 'pc_apps/human_replay')
src = open('pc_apps/human_replay/floor_sheet.py', encoding='utf-8').read()
hard = re.findall(r'(?<![\w.])(0\.18|0\.94|0\.025|0\.08)(?![\w.])', src)
print('hardcoded_B_gates =', hard)
print('PROFILE_refs =', len(re.findall(r'PROFILE\[', src)))
from floor_sheet import SHEET_PROFILE
b_keys = [k for k in SHEET_PROFILE if any(s in k for s in
    ('min_points_per_fit_frame','cell_height_span_max','normal_alignment_min','cell_local_rms','cell_floor_gap'))]
print('SHEET_PROFILE_B_keys =', b_keys)
print('OK' if not hard and not b_keys else 'FAIL')
