"""R3 independent axis-domain audit; synthetic, no device motion or ROS."""
import copy
import itertools
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src/human_fall_detection"))
from core.sensor_quality import ImuSemantics

# Independent signed-permutation representation: dimension index and sign.
DIRECTIONS = {"forward": (0, 1), "backward": (0, -1),
              "left": (1, 1), "right": (1, -1),
              "up": (2, 1), "down": (2, -1)}


class AxisDomainAudit(unittest.TestCase):
    def test_all_cardinal_triads_accept_exactly_24_proper_rotations(self):
        accepted_count = 0
        for names in itertools.product(DIRECTIONS, repeat=3):
            dims, signs = zip(*(DIRECTIONS[name] for name in names))
            inversions = sum(dims[i] > dims[j] for i in range(3)
                             for j in range(i + 1, 3))
            expected = (len(set(dims)) == 3
                        and (-1) ** inversions * signs[0] * signs[1] * signs[2] == 1)
            description = "x_{}_y_{}_z_{}".format(*names)
            semantics = ImuSemantics()
            try:
                semantics.verify("axis_mapping", description, "vendor_protocol")
                accepted = True
            except ValueError:
                accepted = False
            self.assertEqual(accepted, expected, description)
            self.assertEqual(semantics.alignment_verified, expected, description)
            accepted_count += accepted
        self.assertEqual(accepted_count, 24)
        print("CARDINAL_TRIADS=216 ACCEPTED_PROPER_ROTATIONS=24", flush=True)

    def test_rejected_update_preserves_previous_evidence_and_valid_mapping(self):
        semantics = ImuSemantics()
        semantics.verify("axis_mapping", "x_forward_y_left_z_up", "vendor_protocol")
        baseline = copy.deepcopy(semantics.report())
        for value in ("unknown", "x_forward_y_backward_z_up",
                      "x_forward_y_right_z_up", "x_forward_x_left_z_up"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    semantics.verify("axis_mapping", value, "controlled_attitude")
                self.assertEqual(semantics.report(), baseline)


if __name__ == "__main__":
    unittest.main(verbosity=2)
