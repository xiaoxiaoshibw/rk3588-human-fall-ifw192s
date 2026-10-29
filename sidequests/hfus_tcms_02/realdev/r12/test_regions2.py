"""Synthetic boundary tests for the S07F branch-band variant (regions2)."""
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'r11'))

import numpy as np
from regions2 import estimate as estimate2
from regions import estimate as estimate11
from common2 import SK
from support_geometry import comps


def plane():
    u, d, z = np.meshgrid(np.linspace(-.49, .49, 35), [-.03, 0, .03], np.linspace(-.82, .82, 63), indexing='ij')
    axis = np.array([-.3, 0, np.sqrt(.91)])
    lat = np.array([np.sqrt(.91), 0, .3])
    dep = np.cross(lat, axis)
    return np.array([1.55, 1.275, .7]) + u.reshape(-1, 1) * lat + d.reshape(-1, 1) * dep + z.reshape(-1, 1) * axis


def two_pop_cloud():
    """Body column + two lateral clusters: one in the lower band, one in the upper band.

    Only the upper-band cluster is inside the UPPER branch band [0.52,0.88).
    """
    rng = np.random.default_rng(11)
    z = np.linspace(-.78, .78, 40)
    body = np.column_stack([1.50 + .01 * rng.standard_normal(40), 1.27 + .02 * rng.standard_normal(40), .75 + z])
    i = np.arange(32)
    ux = -.26 - .10 * i / 31.0
    uz = .34 + .16 * ((i * 11) % 32) / 31.0
    upper = np.column_stack([1.50 + ux + .003 * rng.standard_normal(32), 1.27 + .02 * rng.standard_normal(32), .75 + uz])
    j = np.arange(6)
    lx = -.35 - .015 * j / 5.0
    lz = -.26 + .16 * ((j * 5) % 6) / 5.0
    lower = np.column_stack([1.50 + lx + .003 * rng.standard_normal(6), 1.27 + .02 * rng.standard_normal(6), .75 + lz])
    p = np.vstack([body, upper, lower])
    idx_lower = np.arange(len(body) + len(upper), len(p))
    return p, idx_lower


def call(p, est, **kw):
    return est(p, list(range(len(p))), coordinate_version=kw.get('coordinate', 'RAW/innolidar'), session_id=kw.get('sid', 'SYNTHETIC_IN_CONTRACT'))[0]


class S07FRegionTests(unittest.TestCase):
    def test_dual_population_band_exclusion(self):
        p, idx_lower = two_pop_cloud()
        a = call(p, estimate11)
        b = call(p, estimate2)
        self.assertTrue(a['nodes']['OUTER_A']['valid'])
        self.assertTrue(b['nodes']['OUTER_A']['valid'])
        sup_a = set(a['nodes']['OUTER_A']['support_rows'])
        sup_b = set(b['nodes']['OUTER_A']['support_rows'])
        self.assertNotEqual(sup_a & set(idx_lower.tolist()), set())
        self.assertEqual(sup_b & set(idx_lower.tolist()), set())
        za = float(np.asarray(a['nodes']['OUTER_A']['xyz'])[2])
        zb = float(np.asarray(b['nodes']['OUTER_A']['xyz'])[2])
        self.assertLess(za, zb)
        pts = np.asarray(p)[sorted(sup_b)]
        self.assertEqual(len(comps(pts, .30)), 1)
        for k in SK.SLOTS:
            if k.startswith('OUTER_'):
                continue
            self.assertEqual(a['nodes'][k]['valid'], b['nodes'][k]['valid'], k)
            if a['nodes'][k]['valid']:
                self.assertTrue(np.allclose(a['nodes'][k]['xyz'], b['nodes'][k]['xyz'], atol=0, rtol=0), k)

    def test_plane_all_nodes_and_source_support(self):
        p = plane()
        before = p.copy()
        out = call(p, estimate2)
        self.assertEqual(sum(n['valid'] for n in out['nodes'].values()), 13)
        for n in out['nodes'].values():
            self.assertTrue(np.allclose(n['xyz'], np.median(p[n['support_rows']], 0), atol=1e-12, rtol=0))
        self.assertTrue(np.array_equal(p, before))

    def test_order_and_no_history(self):
        p = plane()
        rows = np.arange(len(p))
        order = np.random.default_rng(7).permutation(len(p))
        a = call(p, estimate2)
        b = estimate2(p[order], rows[order].tolist(), coordinate_version='RAW/innolidar', session_id='SYNTHETIC_IN_CONTRACT')[0]
        for k in SK.SLOTS:
            self.assertEqual(a['nodes'][k]['valid'], b['nodes'][k]['valid'])
            self.assertTrue(np.allclose(a['nodes'][k]['xyz'], b['nodes'][k]['xyz'], atol=1e-12, rtol=0))
            self.assertEqual(set(a['nodes'][k]['support_rows']), set(b['nodes'][k]['support_rows']))

    def test_sparse_degenerate_and_contract(self):
        self.assertEqual(call(plane()[:5], estimate2)['reason'], 'LOW_OR_INVALID_SUPPORT')
        self.assertEqual(call(np.repeat([[1.5, 1.2, .5]], 50, 0), estimate2)['reason'], 'AMBIGUOUS_BODY_AXIS')
        p = plane()
        for kw in (dict(coordinate='S3'), dict(sid='cap_20261017_113516')):
            with self.assertRaises(ValueError):
                call(p, estimate2, **kw)
        with self.assertRaises(ValueError):
            estimate2(p, [0] * len(p), coordinate_version='RAW/innolidar', session_id='SYNTHETIC_IN_CONTRACT')
        with self.assertRaises(ValueError):
            call(p + np.array([10, 0, 0]), estimate2)
        p[0] = np.nan
        self.assertEqual(call(p, estimate2)['reason'], 'LOW_OR_INVALID_SUPPORT')

    def test_unchanged_conflict_gate_and_contracts(self):
        params = SK.PARAMS
        self.assertEqual(params['node_max_xy_span_m'], .8)
        xyz = np.array([[-.5, 0, .1], [.5, 0, .2], [-.5, 0, .3], [.5, 0, .4], [-.5, 0, .5], [.5, 0, .6]])
        rows = list(range(len(xyz)))
        norm = SK.G.normalize(dict(receipt=dict(rows=rows), global_rows=rows, xyz=xyz.tolist(), invalid_source_rows=[]), params)
        self.assertEqual(SK.G.observe(norm, rows, params)['reason'], 'CONFLICTING_SPATIAL_SUPPORT')
        theta, z = np.meshgrid(np.linspace(0, 2 * np.pi, 32, endpoint=False), np.linspace(-.7, .7, 40))
        q = np.column_stack([1.55 + .15 * np.cos(theta.ravel()), 1.275 + .15 * np.sin(theta.ravel()), .7 + z.ravel()])
        self.assertEqual(call(q, estimate2)['reason'], 'AMBIGUOUS_TRANSVERSE_PLANE')
        p = plane()
        center = p.mean(0)
        qq = p - center
        qq[:, [0, 2]] = qq[:, [2, 0]]
        qq *= .8
        self.assertEqual(call(qq + center, estimate2)['reason'], 'OUTSIDE_UPRIGHT_RAW_CONTRACT')


if __name__ == '__main__':
    unittest.main()
