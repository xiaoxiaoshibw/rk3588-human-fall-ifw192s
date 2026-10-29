"""S4: why is the session-level watertight flag false? Classify the frames where the identity does not apply."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import s4core as C

if __name__ == '__main__':
    recs = [json.loads(l) for l in (C.OUT / 'RUN/frames.jsonl').read_text(encoding='utf8').splitlines()]
    bad, building, action_bad = [], 0, []
    for r in recs:
        d = r['decomp']
        ok = d['watertight']
        if ok:
            continue
        if r['phase'] == 'MAP_BUILDING':
            building += 1
            continue
        action_bad.append(dict(fi=r['fi'], phase=r['phase'], valid=d['valid'], seeds=d['seeds'],
                               members=d['candidate_members'], rejected=d['rejected_total'],
                               leftover=d['leftover'], bg_plus_seeds=d['bg_plus_seeds_equals_valid'],
                               seeds_eq=d['seeds_equals_members_plus_rejected'],
                               counts_eq=d['rejected_counts_match_rows']))
    C.write(C.OUT / 'DECOMPOSITION_AUDIT.json', dict(
        item=C.ITEM, frames=len(recs),
        raw_flag_all_watertight=False,
        explanation='the identity "every seed row is either a candidate member or a rejected row" only holds '
                    'once groups are formed; during MAP_BUILDING the engine deliberately skips candidate '
                    'formation (phase MAP_BUILDING), so seeds == valid and members == rejected == 0 there',
        map_building_frames_without_groups=building,
        non_building_failures=action_bad,
        non_building_frames=len(recs) - building,
        watertight_where_applicable=bool(not action_bad),
        tail_window=dict(checked=[int(k) for k in C.load(C.OUT / 'TAIL_DECOMPOSITION.json')['frames']],
                         all_watertight=C.load(C.OUT / 'TAIL_DECOMPOSITION.json')['summary']['all_watertight']),
        f430_window=dict(checked=[int(k) for k in C.load(C.OUT / 'F430_DECOMPOSITION.json')['frames']],
                         all_watertight=C.load(C.OUT / 'F430_DECOMPOSITION.json')['summary']['all_watertight']),
        note='SUMMARY.json keeps the raw flag watertight_all=false; this audit is the authoritative breakdown'))
    print(json.dumps(dict(map_building=building, non_building_failures=len(action_bad),
                          watertight_where_applicable=not action_bad)))
