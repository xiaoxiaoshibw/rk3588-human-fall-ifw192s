import contextlib
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np

from fall_candidate_runtime import file_sha256
from train_causal_fall import matrix
from train_fall_mil import WindowScorer, export
from validate_fall_mil import run


class ValidateFallMILTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.cache, self.models, self.training = [self.root/name for name in ('cache', 'models', 'training')]
        for path in (self.cache, self.models, self.training): path.mkdir()
        self.records = [{'sequence': 's', 'group': 'heldout', 'label': 1}]
        (self.cache/'INPUT.json').write_text(json.dumps({'records': self.records}), encoding='utf-8')
        self.frames = np.arange(15*19, dtype=np.float64).reshape(15, 19)/100
        np.savez(self.cache/'frames.npz', s=self.frames)
        export(WindowScorer().eval(), np.zeros(114, np.float32), np.ones(114, np.float32), self.models/'fold_a.npz')
        self.manifest = {'task': 'laseract_sequence_falling_vs_other', 'model_format': 'numpy_mil_v1',
            'feature_schema': 'sequence_ordered_xyz_v1', 'positive_class': 1, 'model': 'fold_a.npz',
            'model_sha256': file_sha256(self.models/'fold_a.npz'), 'window_frames': 30,
            'minimum_frames': 10, 'max_gap_s': .5, 'episode': {}}
        (self.training/'fold_a_training.json').write_text(json.dumps({
            'test_groups': ['heldout'], 'train_groups': ['other']}), encoding='utf-8')

    def validate(self, output='check.json'):
        (self.models/'fold_a.json').write_text(json.dumps(self.manifest), encoding='utf-8')
        with contextlib.redirect_stdout(io.StringIO()):
            return run(self.cache, self.models, self.training, self.root/output)

    def test_validation_consumes_manifest_schema_for_both_feature_formulas(self):
        hashes = []
        for schema in ('sequence_xyz_v1', 'sequence_ordered_xyz_v1'):
            with self.subTest(schema=schema):
                self.manifest['feature_schema'] = schema
                result = self.validate(schema+'.json')['checks'][0]
                expected, _ = matrix({'s': self.frames}, self.records, feature_schema=schema)
                digest = hashlib.sha256(expected.tobytes()).hexdigest()
                self.assertEqual(result['feature_matrix_sha256'], digest)
                self.assertEqual(result['feature_schema'], schema)
                self.assertEqual(result['manifest_sha256'], file_sha256(self.models/'fold_a.json'))
                self.assertTrue(all(result['all_threshold_decisions_equal'].values()))
                hashes.append(digest)
        self.assertNotEqual(*hashes)

    def test_invalid_binding_schema_and_context_cannot_report_success(self):
        original = self.manifest.copy()
        for key, value in [('model_sha256', '0'*64), ('feature_schema', 'unknown'),
                           ('minimum_frames', 11), ('model_format', 'numpy_forest_v1')]:
            with self.subTest(key=key):
                self.manifest = dict(original, **{key: value})
                with self.assertRaises((ValueError, KeyError)):
                    self.validate('invalid.json')
                self.assertFalse((self.root/'invalid.json').exists())


if __name__ == '__main__':
    unittest.main()
