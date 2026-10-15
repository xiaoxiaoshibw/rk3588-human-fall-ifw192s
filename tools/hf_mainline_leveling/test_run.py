"""SYNTHETIC checks for immutable exports and the frozen two-session protocol."""
import copy
import tempfile
import unittest
from pathlib import Path

import numpy as np
import run as experiment
import select_planar


class ExperimentTest(unittest.TestCase):
    def test_frozen_plan_does_not_alias_historical_config(self):
        configs = [{"config": {"pitch_deg": 26, "roll_deg": 0, "physical_height_m": 1.14,
                               "regions": [[i, i + .25, 0, .25] for i in range(4)]}} for _ in range(2)]
        original = copy.deepcopy(configs)
        arms = experiment.plan(configs)
        arms["shared_source_patches"][0]["regions"][0][0] = 99
        self.assertEqual(configs, original)
        self.assertNotEqual(arms["shared_source_patches"][1]["regions"][0][0], 99)
        configs[1]["config"]["roll_deg"] = 1
        with self.assertRaisesRegex(ValueError, "nominal"):
            experiment.plan(configs)

    def test_all_rows_opaque_bytes_and_invalid_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            records = np.arange(5 * 28, dtype="u1").reshape(5, 28).copy()
            xyz = np.ndarray((5, 3), dtype="<f4", buffer=records, strides=(28, 4))
            xyz[:] = [[1, 2, 3], [0, 0, 0], [np.nan, 1, 2], [4, 5, 6], [2, 3, 4]]
            raw = directory / "raw.bin"
            raw.write_bytes(records.tobytes())
            derived = records.copy()
            out = np.ndarray((5, 3), dtype="<f4", buffer=derived, strides=(28, 4))
            valid = [0, 3, 4]
            transform = {"R": experiment.rotation(26, -1).tolist(), "t": [0, 0, 1.14]}
            out[valid] = xyz[valid].astype("f8") @ np.asarray(transform["R"]).T + transform["t"]
            path = directory / "derived.bin"
            path.write_bytes(derived.tobytes())
            result = experiment.check_export(raw, path, transform, chunk_rows=2)
            self.assertEqual(result["rows"], 5)
            self.assertEqual(result["invalid_preserved"], 2)
            for index, message in ((12, "Non-XYZ"), (28, "Invalid XYZ"), (0, "Derived XYZ")):
                broken = bytearray(derived.tobytes())
                broken[index] ^= 128
                path.write_bytes(broken)
                with self.assertRaisesRegex(ValueError, message):
                    experiment.check_export(raw, path, transform, chunk_rows=2)
            path.write_bytes(derived.tobytes()[:-1])
            with self.assertRaisesRegex(ValueError, "row count"):
                experiment.check_export(raw, path, transform)

    def test_existing_output_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(FileExistsError):
                experiment.run(Path(tmp))

    def test_joint_fit_selection_requires_both_sessions_full_height_quality(self):
        rng = np.random.RandomState(19)
        keys = [(0, 0), (0, 3), (3, 0), (3, 3)]
        data = [{key: np.column_stack([rng.uniform(key[0]*.25, (key[0]+1)*.25, 80),
                                     rng.uniform(key[1]*.25, (key[1]+1)*.25, 80),
                                     rng.normal(-1.14, .001, 80)]) for key in keys} for _ in range(2)]
        candidates, eligible, winner = select_planar.rank_candidates(keys, data)
        self.assertEqual(len(candidates), 1)
        self.assertEqual(len(eligible), 1)
        self.assertIsNotNone(winner)
        # High obstacle remains in the cell; selector cannot trim it to gain PASS.
        data[1][keys[0]][0, 2] = 2
        _, eligible, winner = select_planar.rank_candidates(keys, data)
        self.assertFalse(eligible)
        self.assertIsNone(winner)


if __name__ == "__main__":
    unittest.main(verbosity=2)
