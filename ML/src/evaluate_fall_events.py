"""Event scoring independent of geometric admission. All timestamps in seconds.

Input JSON: {sessions: [{annotation: fall_events_v1, alarms: [{alarm_s: ...}],
negative_intervals: [[start,end],...], unknown_intervals: [[start,end],...]}]}.
Annotations and interval bounds use video time; LiDAR = video + clock.offset_s.
Alarms already use LiDAR time. Negative exposure must be explicitly labelled;
unlabelled silence is never assumed to be non-fall monitoring.
"""
import argparse
import json
import math
from pathlib import Path

from fall_annotation import validate
from fall_candidate_runtime import file_sha256


def wilson(hits, total):
    if not total:
        return None
    z = 1.959963984540054
    p, z2 = hits / total, z * z
    centre = (p + z2 / (2 * total)) / (1 + z2 / total)
    half = z * math.sqrt(p * (1 - p) / total + z2 / (4 * total * total)) / (1 + z2 / total)
    return [max(0., centre - half), min(1., centre + half)]


def poisson_interval(count, hours):
    """Exact two-sided 95% Poisson interval by CDF inversion, no SciPy runtime."""
    if hours <= 0:
        return None

    def cdf(k, mean):
        if mean == 0:
            return 1.
        logs = [-mean + i * math.log(mean) - math.lgamma(i + 1) for i in range(k + 1)]
        largest = max(logs)
        return math.exp(largest) * sum(math.exp(v - largest) for v in logs)

    def solve(k, probability):
        lo, hi = 0., max(1., count + 1.)
        while cdf(k, hi) > probability:
            hi *= 2
        for _ in range(80):
            mid = (lo + hi) / 2
            if cdf(k, mid) > probability:
                lo = mid
            else:
                hi = mid
        return (lo + hi) / 2

    return [solve(count - 1, .975) / hours if count else 0., solve(count, .025) / hours]


def _finite(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError('Expected finite numeric time')
    return float(value)


def _intervals(value, duration):
    rows = []
    for pair in value:
        if len(pair) != 2:
            raise ValueError('Interval needs two endpoints')
        start, end = map(_finite, pair)
        if not 0 <= start < end <= duration:
            raise ValueError('Interval outside session')
        rows.append([start, end])
    rows.sort()
    if any(a[1] > b[0] for a, b in zip(rows, rows[1:])):
        raise ValueError('Overlapping exposure intervals')
    return rows


def score_session(record, match_after_impact_s=1.5, timely_s=1.5):
    doc = record['annotation']
    validate(doc)
    duration = _finite(doc['duration_s'])
    clock = doc.get('clock')
    if not isinstance(clock, dict):
        raise ValueError('Explicit clock offset and uncertainty required')
    offset, uncertainty = _finite(clock['offset_s']), _finite(clock['uncertainty_s'])
    if uncertainty < 0:
        raise ValueError('Negative clock uncertainty')
    match_after_impact_s, timely_s = _finite(match_after_impact_s), _finite(timely_s)
    if match_after_impact_s < 0 or timely_s < 0:
        raise ValueError('Negative matching or latency budget')
    negative = _intervals(record.get('negative_intervals', []), duration)
    unknown = _intervals(record.get('unknown_intervals', []), duration)
    # Negative exposure must not overlap any fall label, even a disputed one.
    for start, end in negative:
        if any(e['kind'] == 'fall' and start < max(e['t_end'], e['t_impact']+match_after_impact_s)
               and end > e['t_start'] for e in doc['events']):
            raise ValueError('Negative exposure overlaps fall-labelled interval')
    falls = [e for e in doc['events'] if e['kind'] == 'fall' and
             e.get('certainty', 'confirmed') == 'confirmed']
    # High alignment uncertainty is retained but cannot support a timed score.
    if uncertainty > .2 and falls:
        raise ValueError('Confirmed events require clock uncertainty <= 0.2 s')
    windows = sorted([(e['t_start'] + offset, e['t_impact'] + offset + match_after_impact_s, e)
                      for e in falls], key=lambda r: (r[1], r[0], r[2]['id']))
    alarms = sorted(_finite(a['alarm_s']) for a in record.get('alarms', []))
    if any(t < offset or t > duration + offset for t in alarms):
        raise ValueError('Alarm outside session clock')
    matched, rows = {}, []
    false_alarms = duplicates = unscored = 0
    for alarm in alarms:
        eligible = [(start, end, e) for start, end, e in windows if start <= alarm <= end]
        available = [r for r in eligible if r[2]['id'] not in matched]
        if available:
            start, _, event = available[0]
            matched[event['id']] = alarm
            rows.append(dict(alarm_s=alarm, status='matched', event_id=event['id'], latency_s=alarm-start))
        elif eligible:
            duplicates += 1
            rows.append(dict(alarm_s=alarm, status='duplicate'))
        elif any(start <= alarm - offset < end for start, end in negative):
            false_alarms += 1
            rows.append(dict(alarm_s=alarm, status='false_alarm'))
        else:
            unscored += 1
            rows.append(dict(alarm_s=alarm, status='outside_scored_exposure'))
    event_rows = [dict(event_id=e['id'], observable=e['observable'], detected=e['id'] in matched,
                       latency_s=(matched[e['id']] - e['t_start'] - offset) if e['id'] in matched else None,
                       latency_interval_s=([matched[e['id']] - e['t_start'] - offset - uncertainty,
                                            matched[e['id']] - e['t_start'] - offset + uncertainty]
                                           if e['id'] in matched else None))
                  for e in falls]
    negative_s = sum(end-start for start, end in negative)
    unknown_s = sum(max(0., min(b, d)-max(a, c)) for a, b in negative for c, d in unknown)
    return dict(session=doc['session'], subject=doc['subject'], all_events=len(falls),
                detected_events=len(matched), observable_events=sum(e['observable'] for e in falls),
                detected_observable=sum(e['observable'] and e['id'] in matched for e in falls),
                timely_events=sum(r['detected'] and r['latency_interval_s'][1] <= timely_s for r in event_rows),
                probable_or_rejected_falls=sum(e['kind'] == 'fall' for e in doc['events'])-len(falls),
                negative_s=negative_s, unknown_negative_s=unknown_s, false_alarms=false_alarms,
                duplicates=duplicates, unscored_alarms=unscored, events=event_rows, alarms=rows,
                clock_offset_s=offset, clock_uncertainty_s=uncertainty)


def aggregate(rows):
    fields = ('all_events', 'detected_events', 'observable_events', 'detected_observable',
              'timely_events', 'probable_or_rejected_falls', 'negative_s', 'unknown_negative_s',
              'false_alarms', 'duplicates', 'unscored_alarms')
    result = {k: sum(r[k] for r in rows) for k in fields}
    n, hits, obs = result['all_events'], result['detected_events'], result['observable_events']
    hours = result['negative_s'] / 3600
    latencies = sorted(e['latency_s'] for r in rows for e in r['events'] if e['detected'])
    result.update(end_to_end_recall=hits/n if n else None, recall_wilson95=wilson(hits, n),
                  observable_recall=result['detected_observable']/obs if obs else None,
                  timely_recall=result['timely_events']/n if n else None,
                  false_alarms_per_hour=result['false_alarms']/hours if hours else None,
                  false_alarm_poisson95=poisson_interval(result['false_alarms'], hours),
                  observed_negative_fraction=1-result['unknown_negative_s']/result['negative_s']
                  if result['negative_s'] else None,
                  detected_latency_s=latencies)
    return result


def evaluate(records, **settings):
    if not records:
        raise ValueError('No sessions to evaluate')
    ids = [r['annotation']['session'] for r in records]
    if len(ids) != len(set(ids)):
        raise ValueError('Duplicate session would inflate evidence')
    rows = [score_session(r, **settings) for r in records]
    return dict(schema='fall_event_metrics_v1', overall=aggregate(rows), sessions=rows,
                by_subject={s: aggregate([r for r in rows if r['subject'] == s])
                            for s in sorted(set(r['subject'] for r in rows))},
                protocol=dict(match_after_impact_s=settings.get('match_after_impact_s', 1.5),
                              timely_s=settings.get('timely_s', 1.5),
                              negative_exposure='explicit intervals; UNKNOWN time stays in denominator',
                              intervals='descriptive; repeated events within a subject are correlated',
                              geometry_gate_used_for_eligibility=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = evaluate(json.loads(args.input.read_text(encoding='utf-8-sig'))['sessions'])
    report['input_sha256'] = file_sha256(args.input)
    with args.output.open('x', encoding='utf-8') as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2, allow_nan=False)
    print(json.dumps(report['overall'], allow_nan=False))
