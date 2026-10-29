import copy
import tempfile
import unittest
from pathlib import Path

import numpy as np

from body_parts import BodyStore, map_region, map_pixels, geometry
from body_branches import propose, thin, graph, shortest, torso_root, central_body_regions
from core.range_image import ScanGrid
from core.capture_input import ROW_DTYPE


class BodyTests(unittest.TestCase):
    def test_precomputed_candidates_load_without_inference_and_never_overwrite_human(self):
        import hashlib
        from unittest.mock import patch
        from body_parts import ROOT
        from body_branches import METHOD
        cached=dict(method=METHOD,semantic='UNKNOWN',orientation='native_grid_rotated_180_for_view',
            sourceSha256=hashlib.sha256((ROOT/'pc_apps/annotator_v2/body_branches.py').read_bytes()).hexdigest(),
            parts=[dict(part='head',state='visible',rect=None,pixels=[0],sourceRows=[0],
                origin=dict(kind='automatic',method=METHOD,uncertainty=['unverified']))])
        self.context['bodyCandidates']=cached
        with patch('body_parts.propose',side_effect=AssertionError('must use precomputed')):
            result=self.store.load(self.context,self.xyz,self.indices)
        self.assertEqual(result['version'],0)
        self.assertEqual(result['doc']['parts'][0]['mapping']['sourceRows'],[0])
        human=self.compute()
        self.store.save(self.context,self.xyz,self.indices,dict(doc=human,baseVersion=0))
        self.assertEqual(self.store.load(self.context,self.xyz,self.indices)['doc'],human)
        cached['parts'][0]['sourceRows']=[1]
        with self.assertRaisesRegex(ValueError,'pixel/source'):
            self.store.suggest(self.context,self.xyz,self.indices)

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = BodyStore(None, self.tmp.name, grid=object())
        self.xyz = np.array([[1., 2, 3], [4, 5, 6], [8, 9, 10]])
        self.indices = np.array([[0, -1], [1, 2]])
        self.context = dict(binding=dict(sessionId='cap_test', frameIndex=0, personId='P1', rawSha256='a'*64,
            orientation='native_grid_rotated_180_for_view', calibration={'grid':'x'}),
            targetRows=[0, 1], trackId='t1', generation=2)
        self.doc = dict(format='body_parts_v1', binding=self.context['binding'],
            scope=dict(kind='automatic_target', trackId='t1', generation=2),
            parts=[dict(part='head', state='visible', rect=[0, 0, 2, 2],
                origin=dict(kind='human', method='rectangle', uncertainty=['manual_semantics']))])

    def compute(self, doc=None):
        return self.store.compute(self.context, self.xyz, self.indices, doc or self.doc)

    def test_roundtrip_invalid_background_empty_and_orientation(self):
        m = self.compute()['parts'][0]['mapping']
        self.assertEqual(m['sourceRows'], [0, 1])
        self.assertEqual(m['imagePixels'], [[0, 0], [0, 1]])
        self.assertEqual(m['xyz'], self.xyz[[0, 1]].tolist())
        self.assertEqual((m['invalidPixels'], m['excludedOutsideScope']), (1, 1))
        for row, (x, y) in zip(m['sourceRows'], m['imagePixels']):
            self.assertEqual(self.indices[y, x], row)
        native = self.indices[::-1, ::-1]
        self.assertEqual(map_region(native, self.xyz, [1, 1, 2, 2], [0])['sourceRows'], [0])
        self.assertEqual(map_region(self.indices, self.xyz, [1, 0, 2, 1], [0])['sourceRows'], [])

    def test_reject_conflicting_indices_overlapping_parts_and_bad_regions(self):
        with self.assertRaisesRegex(ValueError, 'conflict'):
            map_region(np.array([[0, 0], [1, -1]]), self.xyz, [0, 0, 2, 2], [0, 1])
        doc = copy.deepcopy(self.doc)
        doc['parts'].append(dict(doc['parts'][0], part='torso'))
        with self.assertRaisesRegex(ValueError, 'overlap'):
            self.compute(doc)
        for rect in ([0, 0, 3, 2], [1, 0, 0, 2], [False, 0, 1, 1], [0., 0, 1, 1]):
            with self.assertRaises(ValueError):
                map_region(self.indices, self.xyz, rect, [0])

    def test_occlusion_does_not_invent_points(self):
        doc = copy.deepcopy(self.doc)
        doc['parts'][0].update(state='occluded', rect=[0, 0, 1, 1])
        self.assertEqual(self.compute(doc)['parts'][0]['mapping']['sourceRows'], [0])
        for state in ('invisible', 'uncertain'):
            doc['parts'][0].update(state=state, rect=None)
            self.assertEqual(self.compute(doc)['parts'][0]['mapping']['sourceRows'], [])
            doc['parts'][0]['rect'] = [0, 0, 1, 1]
            with self.assertRaises(ValueError):
                self.compute(doc)

    def test_binding_tamper_and_reload_conflict(self):
        for field, value in [('frameIndex', 1), ('rawSha256', 'b'*64), ('orientation', 'native'),
                             ('personId', 'P2'), ('sessionId', 'other'), ('calibration', {})]:
            doc = copy.deepcopy(self.doc)
            doc['binding'][field] = value
            with self.assertRaisesRegex(ValueError, 'mismatch'):
                self.compute(doc)
        saved = self.store.save(self.context, self.xyz, self.indices, dict(doc=self.doc, baseVersion=0))
        self.assertEqual(saved, self.store.load(self.context, self.xyz, self.indices))
        with self.assertRaisesRegex(ValueError, 'version conflict'):
            self.store.save(self.context, self.xyz, self.indices, dict(doc=self.doc, baseVersion=0))
        path = self.store.path(self.context)
        import json
        env = json.loads(path.read_text('utf-8'))
        env['doc']['parts'][0]['mapping']['sourceRows'] = [2]
        path.write_text(json.dumps(env), 'utf-8')
        with self.assertRaisesRegex(ValueError, 'tampered'):
            self.store.load(self.context, self.xyz, self.indices)

    def test_person_box_and_propagation_provenance(self):
        doc = copy.deepcopy(self.doc)
        doc['scope'] = dict(kind='person_box', boxId='b1', box=dict(x=1, y=2, w=1, h=1, zMin=2, zMax=4))
        doc['parts'][0]['origin'] = dict(kind='propagated', method='explicit_copy', uncertainty=['not_observed'], fromBinding={'frameIndex':9})
        mapped = self.compute(doc)
        self.assertEqual(mapped['parts'][0]['mapping']['sourceRows'], [0])
        self.assertEqual(mapped['parts'][0]['origin'], doc['parts'][0]['origin'])

    def test_geometry_is_intrinsic_no_ground_or_semantic_claim(self):
        points = [[float(i)/10, 0., 0.] for i in range(10)]
        parts = [dict(part=name, mapping=dict(xyz=points), origin=dict(kind='human')) for name in ('head', 'torso', 'upper_arm_1')]
        features = geometry(parts)
        self.assertEqual(features['parts']['torso']['principalAxis'], [1., 0., 0.])
        self.assertEqual(features['segmentAxisAnglesDeg']['torso:upper_arm_1'], 0.)
        self.assertEqual(features['headTorso']['distanceM'], 0.)
        self.assertEqual(features['standing'], 'UNKNOWN')
        self.assertEqual(features['fallEvent'], 'UNKNOWN')
        self.assertFalse(features['alarmChanged'])

    def test_automatic_empty_target_and_hypothesis_origin(self):
        c = dict(self.context, targetRows=[])
        result = self.store.suggest(c, self.xyz, self.indices)
        self.assertTrue(all(part['state'] == 'uncertain' and not part['mapping']['sourceRows'] for part in result['parts']))
        self.assertEqual(result['geometry']['bodySemanticAccuracy'], 'UNKNOWN')

    def test_duplicate_echo_selects_only_nearest_representative(self):
        grid = ScanGrid([[-5., 5.], [-5., 5.]], [[-2., -2.], [2., 2.]])
        records = np.zeros(3, dtype=ROW_DTYPE)
        for i, radius in enumerate([2., 4., 2.]):
            az, el = np.radians([-5., -2.])
            records[i]['x'] = radius*np.cos(el)*np.cos(az)
            records[i]['y'] = radius*np.cos(el)*np.sin(az)
            records[i]['z'] = radius*np.sin(el)
        decoded = grid.decode(records, ('test',))
        self.assertEqual(decoded.rejected['duplicate_rows'].tolist(), [2, 1])
        indices = decoded.source_rows[::-1, ::-1]
        mapping = map_region(indices, decoded.xyz, [1, 1, 2, 2], [0, 1, 2])
        self.assertEqual(mapping['sourceRows'], [0])
        self.assertEqual(mapping['imagePixels'], [[1, 1]])

    def test_sparse_regions_foot_save_occlusion_and_invalid_pixel_rejection(self):
        doc = copy.deepcopy(self.doc)
        doc['parts'][0].update(part='foot_1', rect=None, pixels=[0, 1, 2, 3], state='occluded')
        result = self.compute(doc)
        self.assertEqual(result['parts'][0]['mapping']['sourceRows'], [0, 1])
        self.assertEqual(result['parts'][0]['mapping']['imagePixels'], [[0, 0], [0, 1]])
        self.assertEqual(result['parts'][0]['mapping']['invalidPixels'], 1)
        saved = self.store.save(self.context, self.xyz, self.indices, dict(doc=doc, baseVersion=0))
        self.assertEqual(saved, self.store.load(self.context, self.xyz, self.indices))
        for pixels in ([0, 0], [-1], [4], [True], [1.5]):
            with self.assertRaises(ValueError):
                map_pixels(self.indices, self.xyz, pixels, [0, 1])
        doc['parts'][0]['state'] = 'invisible'
        with self.assertRaisesRegex(ValueError, 'must not invent'):
            self.compute(doc)


def synthetic_body(feet=True):
    mask = np.zeros((90, 90), dtype=bool)
    yy, xx = np.indices(mask.shape)
    mask |= (xx-45)**2+(yy-12)**2 < 6**2
    mask[16:24, 43:48] = True
    mask[24:51, 37:54] = True
    mask[25:30, 13:78] = True
    mask[49:78, 37:43] = True
    mask[49:78, 49:55] = True
    if feet:
        mask[73:79, 29:43] = True
        mask[73:79, 49:63] = True
    indices = np.full(mask.shape, -1, dtype=int)
    y, x = np.nonzero(mask)
    indices[y, x] = np.arange(len(x))
    xyz = np.column_stack((np.full(len(x), 2.), x*.025, -y*.025))
    return mask, indices, xyz


class BranchTests(unittest.TestCase):
    def test_raised_arms_do_not_erase_central_cap_or_turn_trunk_into_a_ridge_strip(self):
        mask = np.zeros((100, 100), dtype=bool)
        y, x = np.indices(mask.shape)
        mask |= (x-50)**2+(y-24)**2 < 7**2
        mask[30:65, 41:60] = True
        mask[64:95, 41:48] = True
        mask[64:95, 53:60] = True
        for t in range(30):
            row = t
            for col in (int(round(22+t*.75)), int(round(78-t*.75))):
                mask[max(0,row-2):row+3, col-2:col+3] = True
        head, trunk, hi, ti = central_body_regions(mask, mask)
        self.assertGreater(np.count_nonzero(head & ((x-50)**2+(y-24)**2 < 6**2)), 50)
        self.assertGreater(np.count_nonzero(trunk[40:60, 42:59]), 300)
        self.assertFalse(np.any((head | trunk) & ~mask))
        self.assertIn('cap', hi['reason'])
        self.assertIn('cross_sections', ti['reason'])

    def test_cap_must_be_depth_connected_and_cannot_consume_a_compact_body(self):
        mask, _, _ = synthetic_body()
        reachable = mask.copy()
        reachable[:22] = False
        head, trunk, _, _ = central_body_regions(mask, reachable)
        self.assertFalse(head.any())
        self.assertFalse(np.any(trunk & ~reachable))
        compact = np.zeros((60,80), bool)
        y,x = np.indices(compact.shape)
        compact |= ((x-40)/20)**2+((y-25)/18)**2 <= 1
        head, _, _, _ = central_body_regions(compact, compact)
        self.assertFalse(head.any())

    def test_root_does_not_lock_on_small_disconnected_pore_at_image_center(self):
        x, y = np.array([5, 7, 8, 9]), np.array([5, 4, 5, 6])
        adjacency = [[], [(2, .1)], [(1, .1), (3, .1)], [(2, .1)]]
        self.assertEqual(torso_root(x, y, adjacency, 5., 5.), 1)

    def test_measured_paths_limbs_and_turned_foot_support_without_fabrication(self):
        mask, indices, xyz = synthetic_body()
        result = propose(indices, xyz, list(range(len(xyz))))
        parts = {part['part']:part for part in result}
        for name in ('upper_arm_1', 'forearm_1', 'upper_arm_2', 'forearm_2', 'thigh_1', 'shin_1', 'thigh_2', 'shin_2'):
            self.assertTrue(parts[name].get('pixels'), name)
        self.assertTrue(parts['foot_1'].get('pixels') or parts['foot_2'].get('pixels'))
        pixels = [pixel for part in result for pixel in part.get('pixels', [])]
        self.assertEqual(len(pixels), len(set(pixels)))
        self.assertTrue(all(indices.ravel()[pixel] >= 0 for pixel in pixels))
        self.assertTrue(np.all(thin(mask) <= mask))
        for part in result:
            self.assertEqual(part['origin']['kind'], 'automatic')
            self.assertIn('image_up_not_gravity', part['origin']['uncertainty'])
            if part['part'].startswith('foot') and part.get('pixels'):
                self.assertGreaterEqual(part['origin']['evidence']['terminalTurnDeg'], 30.)

    def test_raw_rotation_does_not_change_branch_selection_and_straight_end_is_not_foot(self):
        _, indices, xyz = synthetic_body(False)
        first = propose(indices, xyz, list(range(len(xyz))))
        rotation = np.array([[0., 0., 1.], [1., 0., 0.], [0., 1., 0.]])
        second = propose(indices, xyz@rotation+np.array([4., 2., 7.]), list(range(len(xyz))))
        self.assertEqual({p['part']:p.get('pixels') for p in first}, {p['part']:p.get('pixels') for p in second})
        self.assertTrue(all(not p.get('pixels') for p in first if p['part'].startswith('foot')))

    def test_depth_edge_and_missing_pixels_are_not_bridged(self):
        mask = np.ones((3, 7), dtype=bool)
        indices = np.arange(21).reshape(3, 7)
        y, x = np.indices(mask.shape)
        xyz = np.column_stack((np.where(x.ravel() < 3, 1., 3.), x.ravel()*.01, y.ravel()*.01))
        _, _, _, lookup, adjacency = graph(mask, indices, xyz)
        distances, _, _ = shortest(adjacency, [(int(lookup[1, 1]), 0)])
        self.assertTrue(np.isinf(distances[lookup[:, 3:]]).all())
        xyz[:, 0] = 1.
        mask[:, 3] = False
        _, _, _, lookup, adjacency = graph(mask, indices, xyz)
        distances, _, _ = shortest(adjacency, [(int(lookup[1, 1]), 0)])
        self.assertTrue(np.isinf(distances[lookup[:, 4:]]).all())

    def test_bent_compact_and_occluded_shape_leave_unresolved_labels_empty(self):
        indices = np.arange(400).reshape(20, 20)
        xyz = np.column_stack((np.ones(400), np.tile(np.arange(20),20)*.01, np.repeat(np.arange(20),20)*.01))
        parts = propose(indices, xyz, list(range(400)))
        self.assertTrue(all(p['state'] == 'uncertain' and not p.get('pixels') for p in parts))
        self.assertTrue(all('upright_image_hypothesis_not_supported' in p['origin']['evidence']['reason'] for p in parts))


if __name__ == '__main__':
    unittest.main()
