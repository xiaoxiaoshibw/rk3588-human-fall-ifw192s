"""GL-S01 独审自写边界探针：不照抄作者断言，另挑判据字面边界。

判据字面（v2_candidate）：
- full_height_preserved == True
- uses_manual_reference == False
- kind == 'lowest_floor_sheet_v2'
- regions 4 个且不重叠
- B 层门：min_sep >= 0.50m / independent == 4 / condition >= 0.10
探针角度：
 P1: min_sep 恰好 = 0.50m（边界 = 应通过；0.499m 应失败）
 P2: condition 恰好 = 0.10（边界 = ）
 P3: v2 成功时 full_height_preserved / uses_manual_reference 字面 True/False
 P4: v1 抛错前缀 'floor_regions_invalid' 时 v2 接管，否则原样抛
"""
import sys, unittest
import numpy as np
sys.path.insert(0, 'pc_apps/human_replay')
from floor_detector import PROFILE, detect_floor_regions
from floor_sheet import SHEET_PROFILE, _roi_metrics, _clean_cells, detect_floor_regions_v2
from leveling_quality import rotation

R = rotation(26, 0)
PLANE = {"normal": (R.T @ np.array([0., 0., 1.])).tolist(), "offset_m": 1.3}


class Probes(unittest.TestCase):
    def test_p1_min_sep_boundary(self):
        # 四格坐标，距离矩阵最小边恰好 = 0.50m / 0.25 = 2 格
        # (0,0) (2,0) (0,2) (2,2) -> 最近对距离=2格=0.50m，刚好达到
        clean = [{"key":[0,0],"count":40,"min_frame_count":30,"height_span_m":0.01,"local_rms_m":0.01,"local_normal_z":0.99},
                 {"key":[2,0],"count":40,"min_frame_count":30,"height_span_m":0.01,"local_rms_m":0.01,"local_normal_z":0.99},
                 {"key":[0,2],"count":40,"min_frame_count":30,"height_span_m":0.01,"local_rms_m":0.01,"local_normal_z":0.99},
                 {"key":[2,2],"count":40,"min_frame_count":30,"height_span_m":0.01,"local_rms_m":0.01,"local_normal_z":0.99}]
        roi = _roi_metrics(clean)
        self.assertAlmostEqual(roi["min_sep_m"], 0.50, places=6)
        self.assertTrue(roi["ok"], msg=(f"判据说 min_sep >= 0.50 即可；当前={roi}"))
        self.assertEqual(roi["independent_count"], 4)
        # 距离 0.49m 必失败
        clean[1]["key"] = [1, 0]
        clean[2]["key"] = [0, 1]
        clean[3]["key"] = [1, 1]
        self.assertFalse(_roi_metrics(clean)["ok"])

    def test_p2_condition_boundary(self):
        # 让四格落在 (0,0) (4,0) (0,4) (4,4)：cond 接近 1，通过
        clean = [{"key":[kx,ky],"count":40,"min_frame_count":30,"height_span_m":0.01,"local_rms_m":0.01,"local_normal_z":0.99}
                 for kx,ky in ((0,0),(4,0),(0,4),(4,4))]
        roi = _roi_metrics(clean)
        self.assertGreaterEqual(roi["condition"], 0.10)
        self.assertTrue(roi["ok"])
        # 几乎共线 (0,0) (1,0) (2,0) (3,0)：cond ≈ 0，应失败
        clean = [{"key":[k,0],"count":40,"min_frame_count":30,"height_span_m":0.01,"local_rms_m":0.01,"local_normal_z":0.99}
                 for k in (0,1,2,3)]
        roi = _roi_metrics(clean)
        self.assertLess(roi["condition"], 0.10)
        self.assertFalse(roi["ok"])

    def test_p3_v2_candidate_fields_literal(self):
        # 用与作者 test_scattered_clean_cells_on_one_sheet_succeed 一起复用的可靠场景构造器
        # （在 6x6 网格 4 角留干净，v1 25cm 拒绝但 v2 应通过）——另选 seed 区别于作者
        sys.path.insert(0, 'pc_apps/human_replay')
        from floor_sheet_test import posts_floor
        P, I = posts_floor(6, 6, {(0, 0), (2, 0), (0, 2), (2, 2)}, seed=99)
        # 先确认 v1 greedy path rejects
        with self.assertRaises(ValueError) as ctx:
            detect_floor_regions(P, I, 26, 0)
        self.assertTrue(str(ctx.exception).startswith("floor_regions_invalid"),
                        msg="预期 v1 拒绝；实际=" + str(ctx.exception))
        # v2 接管成功
        got = detect_floor_regions_v2(P, I, 26, 0)
        c = got["candidate"]
        self.assertEqual(c["kind"], "lowest_floor_sheet_v2")
        self.assertIs(c["full_height_preserved"], True)
        self.assertIs(c["uses_manual_reference"], False)
        self.assertEqual(len(got["regions"]), 4)

    def test_p4_v1_non_floor_invalid_does_not_take_over(self):
        # 喂一个"完全错误"的输入：v1 应抛非 floor_regions_invalid 的错（如 floor_auto_candidate_invalid）
        # v2 应原样抛错，不得接管。
        P = np.empty((0, 3)); I = np.empty((0,), dtype="i4")
        with self.assertRaises(ValueError) as c1:
            detect_floor_regions(P, I, 26, 0)
        msg = str(c1.exception)
        with self.assertRaises(ValueError) as c2:
            detect_floor_regions_v2(P, I, 26, 0)
        self.assertEqual(str(c2.exception), msg, "v2 在 v1 非 floor_regions_invalid 错误时应原样抛错")


if __name__ == "__main__":
    unittest.main(verbosity=2)
