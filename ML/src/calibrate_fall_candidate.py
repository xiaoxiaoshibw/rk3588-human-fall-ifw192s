"""Training-person-only event rule selection; outer test replay is exploratory."""
import argparse
from collections import defaultdict
import json
from pathlib import Path

from evaluate_fall_candidate import scores
from fall_candidate_runtime import FallEpisodeLatch
from prepare_human_pointset import dump, sha


def read_rows(paths):
    result = defaultdict(list)
    for path in paths:
        with path.open(encoding='utf-8') as stream:
            for line in stream:
                row = json.loads(line)
                result[row['sequence']].append(row)
    return result


def simulate(records, windows, high, votes):
    results = []
    for record in records:
        rows = windows.get(record['sequence'], [])
        latch = FallEpisodeLatch(high=high, low=.2, positive_windows=votes, release_windows=5)
        events, last = [], None
        for row in sorted(rows, key=lambda r: r['end_index_exclusive']):
            end = row['end_index_exclusive']
            if last is not None and end <= last: raise ValueError('Duplicate/out-of-order cached window')
            if last is not None and end != last+1: latch.gap()
            prediction = latch.update(row['fall_probability'], record['sequence'])
            if prediction['new_event']: events.append(end-1)
            last = end
        results.append(dict(record, observable=bool(rows), candidate=int(bool(events)) if rows else None,
                            event_end_frames_0based=events))
    return results


def fit_rule(records, windows):
    grid = []
    for high in [.5, .6, .7, .8, .9, .95, .99]:
        for votes in [1, 2, 3]:
            rows = simulate(records, windows, high, votes)
            people = {}
            recalls = []
            for person in sorted({r['group'] for r in rows}):
                selected = [r for r in rows if r['group'] == person]
                positive = [r for r in selected if r['label'] == 1]
                negative = [r for r in selected if r['label'] == 0 and r['observable']]
                detected = sum(r['candidate'] == 1 for r in positive)
                fp = sum(r['candidate'] == 1 for r in negative)
                people[person] = {'positive_total': len(positive), 'detected': detected,
                                  'observable_negative': len(negative), 'false_candidates': fp,
                                  'negative_clip_fraction': fp/len(negative) if negative else None}
                if positive: recalls.append(detected/len(positive))
            eligible = all(p['negative_clip_fraction'] is not None and p['negative_clip_fraction'] <= .01
                           for p in people.values())
            grid.append({'high': high, 'positive_windows': votes, 'eligible': eligible,
                         'mean_positive_person_recall': sum(recalls)/len(recalls) if recalls else 0,
                         'false_candidates': sum(p['false_candidates'] for p in people.values()), 'people': people})
    eligible = [r for r in grid if r['eligible']]
    selection = max(eligible, key=lambda r: (r['mean_positive_person_recall'], -r['false_candidates'],
                                            r['high'], r['positive_windows'])) if eligible else None
    return grid, selection


def run(cache, lopo, outer, original_manifest, output, calibrated_manifest):
    output.mkdir(parents=True, exist_ok=False)
    metadata = json.loads((cache/'INPUT.json').read_text(encoding='utf-8'))
    training = [r for r in metadata['records'] if r['split'] == 'train']
    testing = [r for r in metadata['records'] if r['split'] == 'test']
    training_people = {r['group'] for r in training}
    if training_people & {r['group'] for r in testing}: raise ValueError('Person overlap')
    for path in lopo.glob('fold_*_training.json'):
        split = json.loads(path.read_text(encoding='utf-8'))
        if not set(split['train_groups']+split['test_groups']) <= training_people:
            raise ValueError('Calibration consumed official test people')
    windows = read_rows(sorted(lopo.glob('fold_*_windows.jsonl')))
    if set(windows)-{r['sequence'] for r in training}: raise ValueError('Outer test window leakage')
    sequence_files = [json.loads(p.read_text(encoding='utf-8')) for p in lopo.glob('fold_*_sequences.json')]
    predicted = [r['sequence'] for rows in sequence_files for r in rows]
    if len(predicted) != len(set(predicted)) or set(predicted) != {r['sequence'] for r in training}:
        raise ValueError('Incomplete or repeated calibration heldouts')
    grid, selected = fit_rule(training, windows)
    dump(output/'GRID.json', grid)
    dump(output/'SELECTION.json', {'selected': selected, 'used_people': sorted(training_people),
         'official_test_people_used_for_rule_selection': [], 'budget_scope': 'training-side clip proxy only, not field acceptance',
         'outer_test_status': 'previously observed; repeated evaluation is exploratory'})
    if selected is None:
        result = {'status': 'NO_SUPPORTED_RULE', 'rule_published': False,
                  'reason': 'no training-only rule meets declared exploratory calibration budget',
                  'used_people': sorted(training_people), 'official_test_people_used_for_rule_selection': [],
                  'prior_manifest_unchanged': True, 'IFW192S_validity': 'UNKNOWN'}
        dump(output/'SUMMARY.json', result)
        print(json.dumps(result), flush=True)
        return result
    manifest = json.loads(original_manifest.read_text(encoding='utf-8'))
    manifest['episode'] = dict(manifest['episode'], high=selected['high'], positive_windows=selected['positive_windows'])
    # A new manifest beside the unchanged numeric weights gives the rule a distinct event identity.
    if original_manifest.parent.resolve() != calibrated_manifest.parent.resolve():
        raise ValueError('Write calibrated manifest beside the original numeric model')
    manifest['rule_calibration'] = {'source': str(output/'SELECTION.json'), 'sha256': sha(output/'SELECTION.json'),
                                  'people': sorted(training_people), 'selection_scope': 'official training people only'}
    dump(calibrated_manifest, manifest)
    test_windows = read_rows(sorted(outer.glob('fold_*_windows.jsonl')))
    results = simulate(testing, test_windows, selected['high'], selected['positive_windows'])
    visible = [r for r in results if r['observable']]
    dump(output/'TEST_SEQUENCES.json', results)
    summary = {'selected_high': selected['high'], 'selected_positive_windows': selected['positive_windows'],
               'all_positive_sequences': sum(r['label'] == 1 for r in results),
               'detected_positive_sequences': sum(r['label'] == 1 and r['candidate'] == 1 for r in results),
               'conditional_score': scores([r['label'] for r in visible], [r['candidate'] for r in visible]),
               'unobservable_sequences': [r['sequence'] for r in results if not r['observable']],
               'manifest_sha256': sha(calibrated_manifest), 'outer_test_status': 'exploratory repeated evaluation',
               'IFW192S_validity': 'UNKNOWN', 'deployment': 'NOT_DEPLOYED'}
    dump(output/'SUMMARY.json', summary); print(json.dumps(summary), flush=True)
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--lopo', type=Path, required=True)
    parser.add_argument('--outer', type=Path, required=True)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--calibrated-manifest', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    run(args.input, args.lopo, args.outer, args.manifest, args.output, args.calibrated_manifest)
