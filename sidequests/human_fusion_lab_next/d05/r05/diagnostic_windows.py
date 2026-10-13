"""Saved-run causal windows only; no candidate generation or score changes."""
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
OUT = ROOT / 'docs/human_capture/evidence/2026-10-12_hfus_d05_r5'
selected = {'175429': set(range(210, 228)), '175553': set(range(0, 11)) | set(range(65, 76))}
windows = []
for variant in ['control', 'anchor']:
    for suffix, frames in selected.items():
        sid = 'cap_20261010_' + suffix
        with (OUT / 'runs' / variant / ('R05_' + variant + '_' + sid + '.jsonl')).open(encoding='utf-8') as f:
            for line in f:
                row = json.loads(line)
                if row['frame_index'] not in frames:
                    continue
                human = set(i for g in row['gt'] if g['class_name'] == 'PERSON' and g['source'] == 'human' for i in g['indices'])
                counts = {k: len(human & set(row['stages'][k])) for k in ['valid_ids', 'bg_kept_ids', 'cleanup_kept_ids', 'retained_ids', 'final_ids']}
                events = row['bank_events']
                proofs = []
                for update in events['updates']:
                    candidate = next(c for c in events['pre_fusion_candidates'] if c['id'] == update['proof_candidate'])
                    hits = len(human & set(candidate['raw_indices']))
                    proofs.append({**update, 'independent_n': candidate['independent_fg_points'],
                                   'retained_n': candidate['retained_points'], 'prob': candidate['prob'],
                                   'human_overlap_coverage': hits / len(human) if human else None,
                                   'human_overlap_purity': hits / len(candidate['raw_indices']) if human else None})
                windows.append({'sid': sid, 'variant': variant, 'frame': row['frame_index'], 'timestamp': row['timestamp'],
                                'qualification': row['qualification'], 'gt_human_points': len(human), 'human_counts': counts,
                                'strict_observed': row['strict']['observed_confirmed'], 'bank_updates': proofs,
                                'bank_before': events['bank_before'], 'bank_after': events['bank_after']})
with (OUT / 'CAUSAL_WINDOWS.json').open('x', encoding='utf-8') as f:
    json.dump({'rows': windows, 'scope': 'complete selected continuous windows in both real runs; GT is after-the-fact support only, not inference'}, f, indent=2)
cases = json.loads((OUT / 'analysis_v2/CASE_INDEX.json').read_text(encoding='utf-8'))
with (OUT / 'WIN_LOSS_INDEX.json').open('x', encoding='utf-8') as f:
    json.dump({'wins': [c for c in cases if c['kind'] == 'SUCCESS'], 'losses': [c for c in cases if c['kind'] == 'REGRESSION'],
               'remaining': [c for c in cases if c['kind'] == 'REMAINING_FAILURE'],
               'scope': 'no overall averaging can erase a per-frame loss; unknown intervals omitted from official delta'}, f, indent=2)
print(json.dumps({'windows': len(windows), 'wins': sum(c['kind'] == 'SUCCESS' for c in cases), 'losses': sum(c['kind'] == 'REGRESSION' for c in cases)}))
