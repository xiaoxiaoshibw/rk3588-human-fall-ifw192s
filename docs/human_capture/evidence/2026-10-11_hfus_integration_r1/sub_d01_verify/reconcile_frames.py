"""Task 2: frame-level reconcile D01 baseline_final jsonl vs D03 A ledger.
Reads only; writes diff report into sub_d01_verify.
Metric keys compared: proposal/accepted/observed_confirmed {tp,fn,fp,unmatched_unknown}
+ per-candidate frame info (id -> n points, prob, decision, track_id, raw_indices set).
"""
import json, os, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

ROOT = r'D:/Code/ldiar'
D01 = os.path.join(ROOT, 'docs/human_capture/evidence/2026-10-11_hfus_d01_r1/baseline_final')
D03 = os.path.join(ROOT, 'docs/human_capture/evidence/2026-10-11_hfus_d03_r1')
OUT = os.path.join(ROOT, 'docs/human_capture/evidence/2026-10-11_hfus_integration_r1/sub_d01_verify')

SESSID = {'near': 'cap_20261010_175429', 'S6': 'cap_20261010_180235'}

def load_frames(path):
    frames = {}
    with open(path, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            frames[(r['sid'], r['frame_index'])] = r
    return frames

def metrics(row, key):
    ev = row.get('evaluation') if 'evaluation' in row else row.get('strict')
    if not ev:
        return None
    d = ev.get(key) or {}
    return {k: d.get(k) for k in ('tp', 'fn', 'fp', 'unmatched_unknown')}

def cand_map(row):
    m = {}
    for c in row.get('candidates') or []:
        cid = c.get('id')
        n = len(c.get('raw_indices') or []) if c.get('raw_indices') is not None else c.get('n')
        m[cid] = {
            'n': n,
            'prob': c.get('prob') if 'prob' in c else c.get('score'),
            'decision': c.get('decision'),
            'track_id': c.get('track_id'),
            'track_confirmed': c.get('track_confirmed'),
            'source': c.get('source'),
            'raw_set': set(c.get('raw_indices') or []),
        }
    return m

def diff_cand(a, b):
    keys = ('n', 'prob', 'decision', 'track_id', 'track_confirmed', 'source')
    d = {k: (a.get(k), b.get(k)) for k in keys if a.get(k) != b.get(k)}
    aset, bset = a.get('raw_set'), b.get('raw_set')
    if aset is not None and bset is not None:
        if aset != bset:
            d['raw_indices'] = (len(aset), len(bset), len(aset - bset), len(bset - aset))
    return d

def main():
    report = {}
    for tag, sid in SESSID.items():
        p1 = os.path.join(D01, f'{sid}__BG_A__sensor_valid.jsonl')
        p3 = os.path.join(D03, f'A_{sid}.jsonl')
        f1, f3 = load_frames(p1), load_frames(p3)
        keys1, keys3 = set(f1), set(f3)
        common = sorted(keys1 & keys3, key=lambda k: k[1])
        sec = {
            'd01_frames': len(f1), 'd03_frames': len(f3),
            'common_frames': len(common),
            'only_d01': sorted((keys1 - keys3), key=lambda k: k[1])[:10],
            'only_d03': sorted((keys3 - keys1), key=lambda k: k[1])[:10],
            'metric_mismatches': [], 'cand_mismatches': [], 'legacy_mismatches': [],
        }
        for k in common:
            r1, r3 = f1[k], f3[k]
            for stage in ('proposal', 'accepted', 'observed_confirmed'):
                m1, m3 = metrics(r1, stage), metrics(r3, stage)
                if m1 != m3:
                    sec['metric_mismatches'].append({'frame': k[1], 'stage': stage, 'd01': m1, 'd03': m3})
            l1, l3 = json.dumps(r1.get('legacy'), sort_keys=True), json.dumps(r3.get('legacy'), sort_keys=True)
            if l1 != l3:
                sec['legacy_mismatches'].append({'frame': k[1], 'd01': r1.get('legacy'), 'd03': r3.get('legacy')})
            c1, c3 = cand_map(r1), cand_map(r3)
            if set(c1) != set(c3):
                sec['cand_mismatches'].append({'frame': k[1], 'id_sets_differ': True,
                    'only_d01': sorted(set(c1) - set(c3)), 'only_d03': sorted(set(c3) - set(c1))})
            else:
                for cid in c1:
                    d = diff_cand(c1[cid], c3[cid])
                    if d:
                        sec['cand_mismatches'].append({'frame': k[1], 'cand': cid, 'diff_(d01,d03)': d})
        report[tag] = sec
        print(f"[{tag}] d01={len(f1)} d03={len(f3)} common={len(common)} "
              f"metric_mm={len(sec['metric_mismatches'])} cand_mm={len(sec['cand_mismatches'])} legacy_mm={len(sec['legacy_mismatches'])}")
    out = os.path.join(OUT, 'task2_frame_reconcile.json')
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=1, default=str)
    print('WROTE', out)

if __name__ == '__main__':
    main()
