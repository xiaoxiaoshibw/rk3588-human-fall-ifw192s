"""Aggregate 9-session x 2-inputMode SUMMARY table from all_run + resume_run.
Also compare resume_run 180235 sensor_valid SUMMARY vs baseline_final.
"""
import json, os, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
ROOT = r'D:/Code/ldiar'
A = os.path.join(ROOT, 'docs/human_capture/evidence/2026-10-11_hfus_integration_r1/sub_d01_verify/all_run')
B = os.path.join(ROOT, 'docs/human_capture/evidence/2026-10-11_hfus_integration_r1/sub_d01_verify/resume_run')
BASE = os.path.join(ROOT, 'docs/human_capture/evidence/2026-10-11_hfus_d01_r1/baseline_final')
SESS = ['cap_20261010_175227','cap_20261010_175429','cap_20261010_175553','cap_20261010_175804',
        'cap_20261010_175943','cap_20261010_180235','cap_20261010_180337','cap_20261010_180557','cap_20261010_180751']
ACT  = {'cap_20261010_175227':'S1-empty-with-furniture','cap_20261010_175429':'S3near-walk-x',
        'cap_20261010_175553':'S3far-walk-y','cap_20261010_175804':'S4-walk-stop-walk',
        'cap_20261010_175943':'S5-turn-in-place','cap_20261010_180235':'S6-sit/stand-hard',
        'cap_20261010_180337':'S7','cap_20261010_180557':'S8','cap_20261010_180751':'S9-ineligible'}
MODES = ['source_legacy','sensor_valid']

def load(sid, mode):
    name = f'{sid}__BG_A__{mode}__SUMMARY.json'
    for base in (A, B):
        p = os.path.join(base, name)
        if os.path.exists(p):
            return json.load(open(p, encoding='utf-8'))
    raise FileNotFoundError(name)

rows = []
for sid in SESS:
    for mode in MODES:
        s = load(sid, mode)
        strict, legacy = s['strict'], s['legacy']
        row = {
            'sid': sid, 'activity': ACT[sid], 'mode': mode,
            'gt_binding_valid': s['gt_binding_valid'],
            'total_frames': s['total_frames'], 'qualified_frames': s['qualified_frames'],
            'unknown_frames': s['unknown_frames'], 'exposure_s': round(s['exposure_seconds'],3),
            'strict_proposal':      strict['proposal'],
            'strict_accepted':      strict['accepted'],
            'strict_observed_conf': strict['observed_confirmed'],
            'legacy_accepted':      legacy['accepted'],
            'legacy_confirmed':     legacy['confirmed'],
            'invalid_candidate_row_count': s['invalid_candidate_row_count'],
        }
        rows.append(row)
        st = strict['proposal']; sa = strict['accepted']; so = strict['observed_confirmed']
        la = legacy['accepted']; lc = legacy['confirmed']
        print(f"{sid[:9]}…{sid[-6:]} {mode:<14} gtv={s['gt_binding_valid']!s:<5} frames={s['total_frames']:>3} q={s['qualified_frames']:>3} | "
              f"prop={st['tp']}/{st['fn']}/{st['fp']}/{st['unmatched_unknown']} acc={sa['tp']}/{sa['fn']}/{sa['fp']}/{sa['unmatched_unknown']} "
              f"obs={so['tp']}/{so['fn']}/{so['fp']}/{so['unmatched_unknown']} | legA={la['tp']}/{la['fp']}/{la['fn']} legC={lc['tp']}/{lc['fp']}/{lc['fn']}")
out = os.path.join(ROOT, 'docs/human_capture/evidence/2026-10-11_hfus_integration_r1/sub_d01_verify/nine_session_table.json')
json.dump(rows, open(out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('WROTE', out)

# Compare 180235 sensor_valid resume SUMMARY vs baseline_final
def flat(o, parent=''):
    out = {}
    if isinstance(o, dict):
        for k, v in o.items(): out.update(flat(v, f'{parent}.{k}' if parent else k))
    elif isinstance(o, list): out[parent] = json.dumps(o, sort_keys=True)
    else: out[parent] = o
    return out
a = json.load(open(os.path.join(BASE, 'cap_20261010_180235__BG_A__sensor_valid__SUMMARY.json'), encoding='utf-8'))
b = json.load(open(os.path.join(B,    'cap_20261010_180235__BG_A__sensor_valid__SUMMARY.json'), encoding='utf-8'))
fa, fb = flat(a), flat(b)
nonvol = sorted(k for k in set(fa) | set(fb) if not k.startswith('performance.'))
diffs = [k for k in nonvol if fa.get(k) != fb.get(k)]
print('180235 sensor_valid vs baseline_final: nonvolatile_diffs =', len(diffs), diffs[:10])
