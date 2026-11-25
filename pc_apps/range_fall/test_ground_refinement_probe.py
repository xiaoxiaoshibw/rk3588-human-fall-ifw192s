import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import ground_refinement_probe as probe


class GroundRefinementProbeTests(unittest.TestCase):
    def test_globals_restored_after_fit_failure(self):
        original_compare = probe.site.compare
        original_estimators = probe.quality.ESTIMATORS
        with tempfile.TemporaryDirectory() as directory:
            session = Path(directory)
            (session / 'meta.json').write_text(json.dumps({'frames': [], 'sensor': {'frame_id': 'lidar'}}), encoding='utf8')
            (session / 'points.bin').write_bytes(b'')
            with patch.object(probe.site, 'fit_site', side_effect=RuntimeError('injected')):
                with self.assertRaisesRegex(RuntimeError, 'injected'):
                    probe.compare_session(session)
        self.assertIs(probe.site.compare, original_compare)
        self.assertIs(probe.quality.ESTIMATORS, original_estimators)

    def test_output_cannot_be_inside_protected_data(self):
        with patch('sys.argv', ['probe', '--session', 'unused', '--out', str(probe.ROOT/'data'/'forbidden')]):
            with self.assertRaisesRegex(ValueError, 'outside data'):
                probe.main()


if __name__ == '__main__':
    unittest.main()
