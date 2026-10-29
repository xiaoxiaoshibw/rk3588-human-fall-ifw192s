"""Regression cases for the event annotation schema."""
import copy
import json
import tempfile
import unittest
from pathlib import Path

from fall_annotation import event_windows, load, summarize, usable_events, validate

DOC = {
    'schema': 'fall_events_v1', 'session': 'cap_test', 'subject': 'S01',
    'duration_s': 60.0,
    'events': [
        {'id': 'e01', 'kind': 'fall', 't_start': 10.0, 't_impact': 10.8, 't_end': 14.0,
         'posture_end': 'lying', 'direction': 'forward', 'certainty': 'confirmed',
         'observable': True},
        {'id': 'e02', 'kind': 'lie_down', 't_start': 30.0, 't_end': 33.0,
         'posture_end': 'lying', 'certainty': 'confirmed', 'observable': True},
    ],
}


def mutated(**changes):
    doc = copy.deepcopy(DOC)
    doc.update(changes)
    return doc


class ValidateTest(unittest.TestCase):
    def test_valid_document(self):
        self.assertEqual(validate(DOC), [])

    def test_schema_required(self):
        with self.assertRaises(ValueError):
            validate(mutated(schema='fall_events_v2'))

    def test_subject_required(self):
        with self.assertRaises(ValueError):
            validate(mutated(subject='  '))

    def test_unknown_kind_rejected(self):
        doc = copy.deepcopy(DOC)
        doc['events'][0]['kind'] = 'tripping'
        with self.assertRaises(ValueError):
            validate(doc)

    def test_impact_must_be_inside_event(self):
        doc = copy.deepcopy(DOC)
        doc['events'][0]['t_impact'] = 15.0
        with self.assertRaises(ValueError):
            validate(doc)

    def test_fall_needs_impact(self):
        doc = copy.deepcopy(DOC)
        del doc['events'][0]['t_impact']
        with self.assertRaises(ValueError):
            validate(doc)

    def test_event_beyond_duration_rejected(self):
        doc = copy.deepcopy(DOC)
        doc['events'][1]['t_end'] = 61.0
        with self.assertRaises(ValueError):
            validate(doc)

    def test_overlap_rejected(self):
        doc = copy.deepcopy(DOC)
        doc['events'][1]['t_start'] = 13.0
        with self.assertRaises(ValueError):
            validate(doc)

    def test_duplicate_id_rejected(self):
        doc = copy.deepcopy(DOC)
        doc['events'][1]['id'] = 'e01'
        with self.assertRaises(ValueError):
            validate(doc)

    def test_end_before_start_rejected(self):
        doc = copy.deepcopy(DOC)
        doc['events'][1]['t_end'] = 29.0
        with self.assertRaises(ValueError):
            validate(doc)

    def test_observable_must_be_boolean(self):
        doc = copy.deepcopy(DOC)
        doc['events'][0]['observable'] = 'yes'
        with self.assertRaises(ValueError):
            validate(doc)


class WindowTest(unittest.TestCase):
    def test_windows_carry_context(self):
        windows = event_windows(DOC, pad_s=0.5, context_s=2.0)
        self.assertEqual(len(windows), 2)
        first = windows[0]
        self.assertEqual(first['window_start'], 7.5)
        self.assertEqual(first['window_end'], 16.5)
        self.assertEqual(first['label'], 1)
        self.assertEqual(windows[1]['label'], 0)

    def test_window_start_is_clamped(self):
        doc = copy.deepcopy(DOC)
        doc['events'][0]['t_start'] = 1.0
        doc['events'][0]['t_impact'] = 1.4
        self.assertEqual(event_windows(doc, pad_s=0.5, context_s=2.0)[0]['window_start'], 0.0)

    def test_rejected_events_are_not_scored(self):
        doc = copy.deepcopy(DOC)
        doc['events'][0]['certainty'] = 'rejected'
        self.assertEqual(len(usable_events(doc)), 1)
        self.assertEqual(len(event_windows(doc)), 1)

    def test_negative_padding_rejected(self):
        with self.assertRaises(ValueError):
            event_windows(DOC, pad_s=-1.0)


class LoadTest(unittest.TestCase):
    def test_bom_is_accepted(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'annotation.json'
            path.write_bytes(b'\xef\xbb\xbf' + json.dumps(DOC).encode('utf-8'))
            self.assertEqual(load(path)['session'], 'cap_test')


class SummaryTest(unittest.TestCase):
    def test_counts(self):
        doc = copy.deepcopy(DOC)
        doc['events'].append({'id': 'e03', 'kind': 'fall', 't_start': 40.0, 't_impact': 40.5,
                              't_end': 44.0, 'posture_end': 'lying', 'certainty': 'rejected',
                              'observable': False})
        result = summarize(doc)
        self.assertEqual(result['falls'], 2)
        self.assertEqual(result['falls_observable'], 1)
        self.assertEqual(result['falls_rejected'], 1)
        self.assertEqual(result['kinds']['fall'], 2)
        self.assertEqual(result['kinds']['lie_down'], 1)


if __name__ == '__main__':
    unittest.main()