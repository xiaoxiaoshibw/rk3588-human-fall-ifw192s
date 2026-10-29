"""独立旁路CLI的输出隔离、对照及因果前缀检查。"""
import json
from pathlib import Path
import subprocess
import sys
import unittest

import range_shape_shadow as shape
import test_range_experiment as fixture


def rows(path):
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]


class ShadowReplayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixture.RangeExperimentTests.setUpClass()

    def setUp(self):
        self.f = fixture.RangeExperimentTests()
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)

    def test_baseline_shadow_and_independent_prefix(self):
        before = {p.name:shape.sha256_file(p) for p in self.f.session.iterdir()}
        full, short = self.f.root/'full', self.f.root/'short'
        result = shape.run(self.f.session, full, empty_prefix_frames=1, rounds=2)
        shape.run(self.f.session, short, empty_prefix_frames=1, limit=3, rounds=1)
        self.assertEqual(result['software_status'], 'PASS')
        self.assertEqual(len({r['inference_sha256'] for r in result['runs']}), 1)
        a, b = rows(full/'shadow_1.jsonl'), rows(short/'shadow_1.jsonl')
        self.assertEqual([r['shape_shadow'] for r in a[:3]], [r['shape_shadow'] for r in b])
        self.assertEqual([r['baseline_sha256'] for r in rows(full/'baseline.jsonl')],
                         [r['baseline_sha256'] for r in a])
        self.assertTrue(a[-1]['shape_shadow']['available'])
        self.assertEqual(before, {p.name:shape.sha256_file(p) for p in self.f.session.iterdir()})

    def test_no_causal_prefix_inference_or_output_in_data(self):
        for kwargs in ({}, dict(empty_prefix_frames=0), dict(rounds=0, empty_prefix_frames=1),
                       dict(exploratory_p98=True, empty_prefix_frames=1)):
            with self.assertRaises(ValueError): shape.run(self.f.session, self.f.root/'bad', **kwargs)
        with self.assertRaises(ValueError):
            shape.run(self.f.session, self.f.session/'forbidden', empty_prefix_frames=1)

    def test_exploration_is_explicit_and_cli_runs(self):
        out = self.f.root/'exploratory'
        result = subprocess.run([sys.executable, '-B', '-W', 'error', str(Path(shape.__file__)),
            '--session', str(self.f.session), '--out', str(out), '--rounds', '1', '--exploratory-p98'],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors='replace'))
        config = json.loads((out/'CONFIG.json').read_text(encoding='utf-8'))
        self.assertTrue(config['noncausal_exploration'])
        self.assertIsNone(config['empty_prefix_frames'])
        self.assertEqual(config['background_scope_frames'], 4)


if __name__ == '__main__': unittest.main()
