"""Compare new all_run SUMMARY jsons vs original baseline_final SUMMARY jsons (3 sessions x 2 modes).
Also (separately) build the 9-session x 2-mode aggregate table from all_run + resume_run.
"""
import json, os, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
ROOT = r'D:/Code/ldiar'
BASE = os.path.join(ROOT, 'docs/human_capture/evidence/2026-10-11_hfus_d01_r1/baseline_final')
NEW  = os.path.join(ROOT, 'docs/human_capture/evidence/2026-10-11_hfus_integration_r1/sub_d01_verify/all_run')
SESS = ['cap_20261010_175227','cap_20261010_175429','cap_20261010_180235']
MODES = ['source_legacy','sensor_valid']

def flat(o, parent=''):
    """flatten dict recursively -> {path: leaf}"""
    out = {}
    if isinstance(o, dict):
        for k, v in o.items():
            out.update(flat(v, f'{parent}.{k}' if parent else k))
    elif isinstance(o, list):
        out[parent] = json.dumps(o, sort_keys=True)
    else:
        out[parent] = o
    return out

# volatile fields: timestamps/perf not expected to match bit-for-bit across runs
IGNORE_PREFIX = ('performance.',)

report = {}
for sid in SESS:
    for mode in MODES:
        name = f'{sid}__BG_A__{mode}__SUMMARY.json'
        a = json.load(open(os.path.join(BASE, name), encoding='utf-8'))
        pnew = os.path.join(NEW, name)
        if not os.path.exists(pnew):
            report[f'{sid}/{mode}'] = {'status': 'PENDING (rerun in progress, see resume_run)'}
            print(f'{sid}/{mode}: PENDING')
            continue
        b = json.load(open(pnew, encoding='utf-8'))
        fa, fb = flat(a), flat(b)
        keys = sorted(set(fa) | set(fb))
        diffs = []
        for k in keys:
            if any(k.startswith(p) for p in IGNORE_PREFIX):
                if fa.get(k) != fb.get(k):
                    diffs.append({'field': k, 'orig': fa.get(k), 'new': fb.get(k), 'volatile': True})
                continue
            if fa.get(k) != fb.get(k):
                diffs.append({'field': k, 'orig': fa.get(k), 'new': fb.get(k)})
        report[f'{sid}/{mode}'] = {'n_diff_fields_nonvolatile': sum(1 for d in diffs if not d.get('volatile')),
                                   'n_diff_fields_volatile': sum(1 for d in diffs if d.get('volatile')),
                                   'diffs': diffs}
        ok = not diffs or all(d.get('volatile') for d in diffs)
        print(f'{sid}/{mode}: {"MATCH" if ok else "DIFF"} (nonvolatile_diffs={report[f"{sid}/{mode}"]["n_diff_fields_nonvolatile"]}, volatile={report[f"{sid}/{mode}"]["n_diff_fields_volatile"]})')

out = os.path.join(ROOT, 'docs/human_capture/evidence/2026-10-11_hfus_integration_r1/sub_d01_verify/summary_diff_vs_baseline_final.json')
json.dump(report, open(out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('WROTE', out)
