"""GL-N01: independently constructed geometry and identity/consumer checks."""
import copy
import math
from pathlib import Path
import sys
import tempfile
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from core.nominal_leveling import (apply_nominal, build_nominal_model,
                                  inverse_nominal, validate_nominal_model)
from core.calibration import validate_geometry_calibration, validate_known_transform
from core.capture_input import prepare_npz, load_adapted
from level_capture_nominal import level_capture, comparison_html
from test_gli01_capture_input import write_export


class NominalLevelingTest(unittest.TestCase):
    def test_known_ground_rotation_translation_order_and_inverse_N01_N02(self):
        for pitch, height in [(0, 1.1), (26, 1.1), (40, 1.8), (-10, .7), (90, 0)]:
            with self.subTest(pitch=pitch, height=height):
                a = math.radians(pitch)
                # Independent inverse scalar geometry, not code's stored R.
                ground = np.array([[x, y, 0] for x in (0, 1, 4) for y in (-1, 0, 2)], dtype=float)
                source = np.array([[math.cos(a)*x+math.sin(a)*height, y,
                                    math.sin(a)*x-math.cos(a)*height] for x,y,_ in ground])
                model = build_nominal_model(pitch, height, "innolidar")
                got = apply_nominal(source, model, "innolidar")
                np.testing.assert_allclose(got, ground, atol=1e-12)
                np.testing.assert_allclose(inverse_nominal(got, model, "ground_nominal"), source, atol=1e-12)
                np.testing.assert_allclose(apply_nominal([[0,0,0]], model, "innolidar"), [[0,0,height]])

    def test_scalar_formula_non_ground_points_N01(self):
        points = np.array([[2, -1, -.5], [0, 1, 2]], dtype=float)
        a = math.radians(26)
        expected = np.array([[math.cos(a)*x+math.sin(a)*z,y,-math.sin(a)*x+math.cos(a)*z+1.1] for x,y,z in points])
        np.testing.assert_allclose(apply_nominal(points, build_nominal_model(26,1.1,"innolidar"), "innolidar"), expected)

    def test_bad_values_frames_schema_units_Q01_Q03(self):
        for pitch,height in [(True,1.1),("26",1.1),(float('nan'),1.1),(26,float('inf')),(26,-1),(100,1),(26,1100)]:
            with self.subTest(pitch=pitch,height=height),self.assertRaises(ValueError):
                build_nominal_model(pitch,height,"innolidar")
        with self.assertRaises(ValueError):build_nominal_model(26,1.1,"same","same")
        model=build_nominal_model(26,1.1,"innolidar")
        for field,value in [("schema",True),("schema",2),("units",{"length":"mm","angle":"rad"}),
                            ("direction","inverse"),("rotation",np.eye(3).tolist()),("physical_verified",True)]:
            m=copy.deepcopy(model);m[field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):validate_nominal_model(m)
        with self.assertRaises(ValueError):apply_nominal([[1,2,3]],model,"foreign")
        with self.assertRaises(ValueError):inverse_nominal([[1,2,3]],model,"innolidar")
        for points in [[[1,True,0]],[["1",0,0]],[[float('nan'),0,0]],[[1,2]]]:
            with self.assertRaises(ValueError):apply_nominal(points,model,"innolidar")
            with self.assertRaises(ValueError):inverse_nominal(points,model,"ground_nominal")

    def test_viewer_escapes_untrusted_frame_N05(self):
        model=build_nominal_model(26,1.1,"lidar</script><script>alert(1)")
        html=comparison_html(model,[])
        self.assertNotIn("lidar</script>",html)
        self.assertIn("lidar\\u003c/script>",html)

    def test_parameter_change_content_identity_and_caller_Q02(self):
        old=build_nominal_model(26,1.1,"innolidar")
        self.assertEqual(old,build_nominal_model(26,1.1,"innolidar"))
        for pitch,height in [(27,1.1),(26,1.2)]:
            self.assertNotEqual(old['model_id'],build_nominal_model(pitch,height,"innolidar")['model_id'])
        changed=copy.deepcopy(old);changed['pitch_down_deg']=27
        with self.assertRaises(ValueError):apply_nominal([[0,0,0]],changed,"innolidar")
        fresh=validate_nominal_model(old);fresh['height_m']=0
        self.assertEqual(old['height_m'],1.1)

    def test_nominal_not_qualified_runtime_N06_Q05(self):
        m=build_nominal_model(26,1.1,"innolidar")
        self.assertFalse(m['physical_verified']);self.assertFalse(m['runtime_eligible'])
        with self.assertRaises(ValueError):validate_known_transform(m)
        with self.assertRaises(ValueError):validate_geometry_calibration(m)

    def test_source_rows_zeros_outputs_protection_Q02_Q04(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source=root/'source';write_export(source,counts=(4,4,4,4))
            # One invalid zero return; real export bytes preserved by adapter.
            raw=bytearray((source/'points.bin').read_bytes());raw[:12]=bytes(12);(source/'points.bin').write_bytes(raw)
            npz=root/'input.npz';prepare_npz(str(source),'innolidar','m',str(npz))
            out=root/'docs/human_fall/evidence/2026-10-04_gl_n01_r1';out.mkdir(parents=True)
            a=level_capture(npz,out/'a',26,1.1,'innolidar',root)
            self.assertEqual(a['valid_point_count'],15)
            with np.load(out/'a/nominal_leveled.npz',allow_pickle=False) as saved:
                self.assertEqual(saved['source_rows'].tolist(),list(range(1,16)))
                _,points=load_adapted(npz)
                np.testing.assert_allclose(saved['points'],apply_nominal(points[1:],build_nominal_model(26,1.1,'innolidar'),'innolidar'))
            b=level_capture(npz,out/'b',26,1.1,'innolidar',root)
            self.assertEqual(a,b)
            level_capture(npz,out/'new_pitch',40,1.8,'innolidar',root)
            for target in [out/'a',root/'captures/bad',out]:
                with self.assertRaises(ValueError):level_capture(npz,target,26,1.1,'innolidar',root)


if __name__ == "__main__":unittest.main()
