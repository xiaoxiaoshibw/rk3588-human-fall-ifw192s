"""Independent malformed-metadata boundaries for performance measurement."""
import json
import sys
import unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src/human_fall_detection/scripts"))
import profile_pipeline as profile


class ProfileInputs(unittest.TestCase):
    def test_boolean_version_is_not_a_supported_integer_schema(self):
        self.assertIsNone(profile.parse_state(json.dumps({
            "kind": "target_state", "schema_version": True})))

    def test_frame_key_rejects_malformed_header_without_raising(self):
        valid = {"session_id": "s", "time_epoch": 0,
                 "source": {"seq": 1, "stamp_secs": 100, "stamp_nsecs": 1}}
        self.assertEqual(profile.frame_key(valid), ("s", 0, 1, 100, 1))
        for field, bad in [("seq", "garbage"), ("stamp_secs", 100.5),
                           ("stamp_nsecs", 1000000000), ("seq", True)]:
            with self.subTest(field=field, value=bad):
                payload = dict(valid, source=dict(valid["source"], **{field: bad}))
                self.assertIsNone(profile.frame_key(payload))

    def test_negative_or_boolean_duration_is_not_a_latency(self):
        for value in [-1, True, float("nan"), float("inf")]:
            with self.subTest(value=value):
                self.assertIsNone(profile._ms(value))
        self.assertEqual(profile._ms(0), 0)
        self.assertEqual(profile._ms(0.075), 75)


if __name__ == "__main__":
    unittest.main(verbosity=2)
