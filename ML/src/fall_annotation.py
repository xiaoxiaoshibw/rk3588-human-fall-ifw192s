"""Event-level fall annotation: schema, validation and window derivation.

A whole recording is annotated once, by hand, with what happened and when.
Frame labels are never invented from a clip label: the only time-resolved
statement an annotation makes is the event interval.  A `fall` interval covers
the descent and the time on the floor, not "every frame in which the person is
low", and it never replaces an observed posture.

Schema `fall_events_v1` (one JSON file per session):

    {
      "schema": "fall_events_v1",
      "session": "cap_20261101_093000",
      "subject": "S03",
      "site": "lab_a",
      "sensor": "ifw192s",
      "duration_s": 180.4,
      "clock": {"align": "clap", "offset_s": -0.12, "uncertainty_s": 0.10},
      "events": [
        {"id": "e01", "kind": "fall", "t_start": 12.4, "t_impact": 13.1,
         "t_end": 21.0, "posture_end": "lying", "direction": "forward",
         "certainty": "confirmed", "observable": true, "notes": "mat, self-paced"}
      ]
    }

`t_start` is the first frame of the loss of balance, `t_impact` the first
contact with the floor, `t_end` the last frame counted as this event (usually
when the person starts to get up).  `certainty` is the annotator's confidence in
the *label*, `observable` says whether the sensor chain actually saw it.
"""
import argparse
import json
import math
from pathlib import Path

SCHEMA = 'fall_events_v1'
KINDS = ('fall', 'lie_down', 'sit_fast', 'bend_pick', 'squat', 'kneel',
         'stumble', 'crawl', 'stand_up', 'walk', 'sit', 'other')
POSTURES = ('standing', 'sitting', 'kneeling', 'lying', 'unknown')
DIRECTIONS = ('forward', 'backward', 'left', 'right', 'unknown')
CERTAINTY = ('confirmed', 'probable', 'rejected')
FALL_KINDS = ('fall',)


def load(path):
    path = Path(path)
    # utf-8-sig: hand-edited annotations often come with a BOM from Windows editors.
    return json.loads(path.read_text(encoding='utf-8-sig'))


def _number(value, field, where):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError('%s: %s must be a finite number' % (where, field))
    return float(value)


def validate(doc):
    """Raise on a malformed annotation; return a short list of warnings."""
    if not isinstance(doc, dict):
        raise ValueError('annotation must be an object')
    if doc.get('schema') != SCHEMA:
        raise ValueError('schema must be %r' % SCHEMA)
    for field in ('session', 'subject'):
        if not isinstance(doc.get(field), str) or not doc[field].strip():
            raise ValueError('%s must be a non-empty string' % field)
    events = doc.get('events')
    if not isinstance(events, list):
        raise ValueError('events must be a list')
    duration = doc.get('duration_s')
    if duration is not None:
        duration = _number(duration, 'duration_s', 'annotation')
        if duration <= 0:
            raise ValueError('duration_s must be positive')
    if 'clock' in doc:
        clock = doc['clock']
        if not isinstance(clock, dict):
            raise ValueError('clock must be an object')
        _number(clock.get('offset_s'), 'offset_s', 'clock')
        uncertainty = _number(clock.get('uncertainty_s'), 'uncertainty_s', 'clock')
        if uncertainty < 0:
            raise ValueError('clock uncertainty must not be negative')

    warnings, seen_ids, spans = [], set(), []
    for index, event in enumerate(events):
        where = 'event[%d]' % index
        if not isinstance(event, dict):
            raise ValueError('%s must be an object' % where)
        identifier = event.get('id')
        if not isinstance(identifier, str) or not identifier:
            raise ValueError('%s needs a non-empty id' % where)
        if identifier in seen_ids:
            raise ValueError('duplicate event id %r' % identifier)
        seen_ids.add(identifier)
        kind = event.get('kind')
        if kind not in KINDS:
            raise ValueError('%s: kind %r not in %s' % (where, kind, KINDS))
        certainty = event.get('certainty', 'confirmed')
        if certainty not in CERTAINTY:
            raise ValueError('%s: certainty %r not in %s' % (where, certainty, CERTAINTY))
        if not isinstance(event.get('observable'), bool):
            raise ValueError('%s: observable must be a boolean' % where)
        start = _number(event.get('t_start'), 't_start', where)
        end = _number(event.get('t_end'), 't_end', where)
        if start < 0:
            raise ValueError('%s: t_start must not be negative' % where)
        if end <= start:
            raise ValueError('%s: t_end must be after t_start' % where)
        if duration is not None and end > duration + 1e-6:
            raise ValueError('%s: t_end %.3f exceeds duration_s %.3f' % (where, end, duration))
        if kind in FALL_KINDS:
            impact = _number(event.get('t_impact'), 't_impact', where)
            if not start <= impact <= end:
                raise ValueError('%s: t_impact must lie inside [t_start, t_end]' % where)
        elif event.get('t_impact') is not None:
            _number(event['t_impact'], 't_impact', where)
        posture = event.get('posture_end', 'unknown')
        if posture not in POSTURES:
            raise ValueError('%s: posture_end %r not in %s' % (where, posture, POSTURES))
        direction = event.get('direction', 'unknown')
        if direction not in DIRECTIONS:
            raise ValueError('%s: direction %r not in %s' % (where, direction, DIRECTIONS))
        if certainty == 'rejected':
            warnings.append('%s (%s) is rejected and will not enter any split' % (identifier, kind))
        spans.append((start, end, identifier))

    spans.sort()
    for (s0, e0, i0), (s1, e1, i1) in zip(spans, spans[1:]):
        if s1 < e0:
            raise ValueError('events %r and %r overlap in time' % (i0, i1))
    return warnings


def usable_events(doc):
    """Non-rejected annotations, including unobservable events (never negatives)."""
    return [e for e in doc['events'] if e.get('certainty', 'confirmed') != 'rejected']


def event_windows(doc, pad_s=0.5, context_s=2.0):
    """Convert events to study windows.

    Each window carries `pre` context (the upright approach) and `post` context
    (recovery), so a model can see the transition rather than only the floor.
    Windows are seconds, never frame counts: the same 30 frames mean 3.0 s on a
    10 Hz sensor and 4.3 s on a 7 Hz one.
    """
    validate(doc)
    if not math.isfinite(pad_s) or not math.isfinite(context_s) or pad_s < 0 or context_s < 0:
        raise ValueError('pad_s and context_s must not be negative')
    windows = []
    for event in usable_events(doc):
        start, end = float(event['t_start']), float(event['t_end'])
        windows.append({'id': '%s:%s' % (doc['session'], event['id']),
                        'session': doc['session'], 'subject': doc['subject'],
                        'kind': event['kind'],
                        'label': (int(event['kind'] in FALL_KINDS) if event['observable'] and
                                  event.get('certainty', 'confirmed') == 'confirmed' else None),
                        'observable': bool(event['observable']),
                        'window_start': round(max(0.0, start - pad_s - context_s), 3),
                        'event_start': round(start, 3), 'event_end': round(end, 3),
                        'event_impact': float(event['t_impact']) if event['kind'] in FALL_KINDS else None,
                        'certainty': event.get('certainty','confirmed'),
                        'window_end': round(min(doc.get('duration_s', float('inf')),
                                                end + pad_s + context_s), 3)})
    return windows


def summarize(doc):
    counts = {}
    for event in doc['events']:
        counts[event['kind']] = counts.get(event['kind'], 0) + 1
    falls = [e for e in doc['events'] if e['kind'] in FALL_KINDS]
    return {'session': doc['session'], 'subject': doc['subject'],
            'events': len(doc['events']), 'kinds': counts,
            'falls': len(falls),
            'falls_observable': sum(1 for e in falls if e['observable']),
            'falls_rejected': sum(1 for e in falls if e.get('certainty') == 'rejected'),
            'duration_s': doc.get('duration_s')}


def main():
    parser = argparse.ArgumentParser(description='Validate a fall_events_v1 annotation')
    parser.add_argument('--annotation', type=Path, required=True)
    parser.add_argument('--windows', action='store_true')
    args = parser.parse_args()
    doc = load(args.annotation)
    warnings = validate(doc)
    for warning in warnings:
        print('warning:', warning)
    print(json.dumps(summarize(doc), ensure_ascii=False))
    if args.windows:
        for window in event_windows(doc):
            print(json.dumps(window, ensure_ascii=False))


if __name__ == '__main__':
    main()
