"""Stream actual ledger, verify conservation and export events without changing inference."""
import argparse
import hashlib
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('run_directory')
    parser.add_argument('output')
    args = parser.parse_args()
    out = Path(args.output)
    if out.exists():
        raise FileExistsError(out)
    report = []
    for file in sorted(Path(args.run_directory).glob('*.jsonl')):
        h = hashlib.sha256()
        events, active, layers, cases = [], {}, {}, []
        frames = 0
        with file.open('rb') as stream:
            for line in stream:
                h.update(line)
                row = json.loads(line)
                frames += 1
                fate = row['fate']
                ids = [i for v in fate.values() for i in v]
                assert len(ids) == len(set(ids)) == row['valid_points']
                for c in row['raw_components']:
                    assert len(c['raw_indices']) == len(set(c['raw_indices']))
                gt = {g['id']: g for g in row['gt'] or [] if g['class_name'] == 'PERSON'}
                seen = set()
                for kind in ['proposal', 'accepted', 'observed_confirmed']:
                    score = row['evaluation'][kind]
                    if score is None:
                        continue
                    for gid in score['fn_ids']:
                        obj = gt[gid]
                        key = (kind, obj['track_id'])
                        seen.add(key)
                        prior = active.get(key)
                        if prior and row['frame_index'] == prior['end_frame'] + 1 and 0 <= row['timestamp_s'] - prior['end_time_s'] <= .3:
                            prior.update(end_frame=row['frame_index'], end_time_s=row['timestamp_s'], observations=prior['observations'] + 1)
                        else:
                            event = dict(kind=kind, gt_track_id=obj['track_id'], start_frame=row['frame_index'], end_frame=row['frame_index'], start_time_s=row['timestamp_s'], end_time_s=row['timestamp_s'], observations=1)
                            events.append(event)
                            active[key] = event
                active = {k: v for k, v in active.items() if k in seen}
                for gid, g in gt.items():
                    G = set(g['indices'])
                    counts = {key: len(G.intersection(v)) for key, v in fate.items()}
                    assert sum(counts.values()) == len(G)
                    for key, n in counts.items():
                        layers[key] = layers.get(key, 0) + n
                    overlaps = []
                    for c in row['raw_components']:
                        n = len(G.intersection(c['raw_indices']))
                        if n:
                            overlaps.append(dict(component_id=c['id'], path=c['path'], hard_gate_pass=c['hard_gate_pass'], intersection=n, coverage=n / len(G), purity=n / len(c['raw_indices']), rejection_reasons=c['rejection_reasons']))
                    if row['sid'].endswith('180235') and row['frame_index'] in [128, 129, 130, 171, 187, 188]:
                        cases.append(dict(frame_index=row['frame_index'], gt_id=gid, current_gt_points=len(G), exclusive_flow=counts, components=overlaps, scoring_candidates=[dict(id=c['id'], score=c['score'], decision=c['decision'], intersection=len(G.intersection(c['raw_indices'])), coverage=len(G.intersection(c['raw_indices'])) / len(G), purity=len(G.intersection(c['raw_indices'])) / len(c['raw_indices']), association_anchor=c['association_anchor'], scoring_centroid=c['scoring_centroid']) for c in row['candidates']]))
        summary = json.loads(file.with_name(file.stem + '__SUMMARY.json').read_text(encoding='utf8'))
        report.append(dict(file=str(file), sha256=h.hexdigest(), frames=frames, point_conservation='PASS', qualified_exposure_seconds=summary['exposure_seconds'], FN_events=events, current_GT_point_flow=layers, S6_cases=cases, known_negative_FP_event_status='BLOCKED: no independently reviewed complete-negative qualification', recovery_latency_status='UNKNOWN outside adjacent qualified windows'))
    out.write_text(json.dumps({'reports': report, 'event_contract': 'same GT track, adjacent qualified frames, gap<=0.3s; UNKNOWN breaks; FN count by object not points; known FP unavailable'}, ensure_ascii=False, indent=2), encoding='utf8')
    print('LEDGER_CHECK_PASS', len(report), 'runs', sum(r['frames'] for r in report), 'frames')


if __name__ == '__main__':
    main()
