import copy
import tempfile
import unittest
from pathlib import Path
import numpy as np
from contracts import universe, project, resolve_queries, Revisions, trusted_labels, semantic_metrics, joint_adapter, label_gate, sha
from models import Frontend, point_inputs, image_inputs, state_sha, gated_loss, load_bound_weights
from temporal import Association, CausalGRU
import torch


class Contracts(unittest.TestCase):
    def test_profile_source_and_raw_schema_guards(self):
        import importlib.util
        from unittest.mock import patch
        spec = importlib.util.spec_from_file_location('profile_guard_test', Path(__file__).with_name('run.py'))
        runner = importlib.util.module_from_spec(spec); spec.loader.exec_module(runner)
        manifest = dict(sources={'s':dict(sha256={'meta':'expected', 'points':'expected'})}, split=dict(folds=[{}, {}, dict(train_sids=['s'])]))
        def fake_read(path):
            if Path(path).name == 'RUN_MANIFEST.json': return manifest
            if Path(path).name == 'ANNOTATION_QUEUE_V2.json': return dict(tasks={'s':dict(core_review=[0])})
            return dict(frames=[dict(count_points=1)])
        with patch.object(runner, 'read', side_effect=fake_read), patch.object(runner, 'load', return_value=({}, np.zeros((1, 3)), {'meta':'drift', 'points':'drift'})):
            with self.assertRaisesRegex(ValueError, 'Resource probe source drift'): runner.profile_one(Path('not_real'), 'L3D', 0, 128)
        good = dict(format='human_capture_session', format_version=1, point_stride_bytes=28, total_points=1,
                    frames=[dict(offset_points=0, count_points=1, stamp_sec=1, stamp_nanosec=0)])
        runner.validate_meta(good, 28)
        with self.assertRaises(ValueError): runner.validate_meta(good, 27)
        bad = copy.deepcopy(good); bad['frames'][0]['offset_points'] = True
        with self.assertRaises(ValueError): runner.validate_meta(bad, 28)
        bad = copy.deepcopy(good); bad['format_version'] = 99
        with self.assertRaises(ValueError): runner.validate_meta(bad, 28)

    def test_query_reorder_split_weak_prefix(self):
        track = Association()
        a = dict(center=[0., 0, 0], rows=[0], reliable=True)
        b = dict(center=[2., 0, 0], rows=[1], reliable=True)
        first = track.update(0, [a, b]); reorder = track.update(.1, [b, a])
        self.assertEqual([r['identity'] for r in reorder], [first[1]['identity'], first[0]['identity']])
        weak = dict(a, reliable=False)
        self.assertEqual(track.update(.2, [weak])[0]['event_rows'], [])
        split = track.update(.3, [a, dict(a, rows=[2])])
        self.assertTrue(all(x['identity'] is None for x in split))
        self.assertTrue(track.update(-1, [a])[0]['reset'])
        torch.manual_seed(19); net = CausalGRU(); baseline = copy.deepcopy(net)
        with torch.no_grad():
            prefix = [net.step(i*.1, 1, np.ones(8)*i).clone() for i in range(15)]
            for i in range(15): self.assertTrue(torch.equal(prefix[i], baseline.step(i*.1, 1, np.ones(8)*i)))
        self.assertLessEqual(len(net.history), 8)
        self.assertIsNone(net.step(2, None, np.zeros(8)))

    def test_universe_and_two_depths(self):
        raw = np.array([[1., .01, 0], [1.00001, 0, 0], [0, 0, 0], [np.nan, 0, 0], [15, 0, 0], [.2, 0, 0]])
        self.assertEqual(np.flatnonzero(universe(raw)).tolist(), [0, 1])
        template = dict(bounds_radians=[[-1, 1], [-1, 1]])
        a = project(raw, template, 128, 512, 'range'); b = project(raw, template, 128, 512, 'axial')
        # Put distinct rays strictly in the same pixel (avoid an exact boundary).
        raw[:2, 1] = [.002, .0001]
        a = project(raw, template, 128, 512, 'range'); b = project(raw, template, 128, 512, 'axial')
        self.assertEqual(a['layers'][0, 0], 0 if np.linalg.norm(raw[0]) < np.linalg.norm(raw[1]) else 1)
        raw = np.array([[1., .003, 0], [1.000001, .00001, 0], [2., 0, 0], [-2, 0, 0]])
        a = project(raw, template, 128, 512, 'range'); b = project(raw, template, 128, 512, 'axial')
        self.assertEqual(a['members'][0], 1); self.assertEqual(b['members'][0], 0)
        self.assertEqual(len(a['outside']), 1)
        self.assertEqual(len(a['members'])+len(a['outside']), 4)
        self.assertEqual(len(a['members'])-len(a['pixels'])*2, 1)

    def test_semantics_and_queries(self):
        r = semantic_metrics([1, 0, -1], [-1, -1, 1])
        self.assertEqual(r['FN'], 1); self.assertEqual(r['background_abstention'], 1)
        self.assertEqual(r['outside_K_H'], 1); self.assertEqual(r['known_coverage'], 0)
        self.assertIsNone(semantic_metrics([-1], [1])['IoU'])
        masks = np.array([[.9, .9, .1, .1], [.9, .1, .1, .1]])
        self.assertEqual(resolve_queries([1, 1], np.ones(4), masks).tolist(), [-1, 0])
        self.assertEqual(resolve_queries([0, 1], np.ones(4), masks).tolist(), [-1, 0])

    def test_revision_and_disagreement(self):
        with tempfile.TemporaryDirectory() as folder:
            store = Revisions(folder)
            r = dict(schema='hfus-label/1', sid='s', fi=0, source_sha256={'meta':'m', 'points':'p'}, reviewer='human_A',
                     provenance='HUMAN_REVIEW', reason='manual review', parent_revision=0, layer='PRIMARY', visibility='VISIBLE',
                     full_view_reviewed=True, visible_human_coverage=True, instance_exhaustive_verified=False,
                     labels=[dict(row=0, semantic='TRUSTED_HUMAN', instance=None)])
            saved = store.append(r, r['source_sha256'], [0, 1])
            self.assertEqual(trusted_labels([dict(saved, full_view_reviewed=False)], [0, 1]).tolist(), [-1, -1])
            self.assertEqual(trusted_labels([saved], [0, 1], min_coverage=.7).tolist(), [-1, -1])
            with self.assertRaises(ValueError): store.append(r, r['source_sha256'], [0, 1])
            self.assertEqual(trusted_labels([saved], [0, 1], True).tolist(), [-1, -1])
            s = copy.deepcopy(r); s.update(layer='SECONDARY')
            with self.assertRaises(ValueError): store.append(s, r['source_sha256'], [0, 1])
            s.update(reviewer='human_B'); s['labels'][0]['semantic'] = 'VERIFIED_NONHUMAN'
            second = store.append(s, r['source_sha256'], [0, 1])
            with self.assertRaises(ValueError): store.append(dict(r, reviewer='human_B'), r['source_sha256'], [0, 1])
            task = dict(sid='s', fi=0, kind='CORE', role='OOF_DEV', secondary_required=True)
            gate = label_gate([task], {('s', 0):[0, 1]}, {('s', 0):[saved, second]})
            self.assertEqual(gate['status'], 'BLOCKED'); self.assertEqual(gate['eligible_frames_per_sid']['s'], 0)
            self.assertEqual(trusted_labels([saved, second], [0, 1], True).tolist(), [-1, -1])
            r.update(parent_revision=1, reason='undo'); r['labels'] = []
            third = store.append(r, r['source_sha256'], [0, 1]); self.assertEqual(third['revision'], 2)

    def test_models_no_update_and_missing_joints(self):
        torch.set_num_threads(2)
        raw = np.array([[1., 0, 0], [1.1, .01, .2], [1.2, .01, .1]], dtype='f4')
        prs = [project(raw, dict(bounds_radians=[[-1, 1], [-1, 1]]), 128, 512, mode) for mode in ['range', 'axial']]
        point = point_inputs(raw); image, mapping = image_inputs(raw, np.arange(3), prs, 128, 512)
        for family in ['L3D', 'L2D', 'LFUSION']:
            net = Frontend(family); net.eval(); before = state_sha(net)
            out = net(point, image, mapping)
            self.assertEqual(tuple(out['mask_logit'].shape), (3, 4))
            loss = gated_loss(out, torch.tensor([1, 0, -1])); loss.backward()
            self.assertEqual(state_sha(net), before)
            with self.assertRaises(ValueError): gated_loss(out, torch.tensor([1, 0, -1]), True)
            self.assertTrue(torch.isfinite(gated_loss(out, torch.tensor([0, 0, -1]), True, torch.empty(3, 0))))
        with tempfile.TemporaryDirectory() as folder:
            p = Path(folder)/'test_random_state.pt'; net = Frontend('L3D'); torch.save(net.state_dict(), p)
            with self.assertRaises(ValueError): load_bound_weights(net, p, 'wrong_sha')
            load_bound_weights(net, p, sha(p))
            bad = net.state_dict(); bad['query'][0, 0] = float('nan'); torch.save(bad, p)
            with self.assertRaises(ValueError): load_bound_weights(net, p, sha(p))
        self.assertEqual(joint_adapter()['scoring'], 'BLOCKED_NO_JOINT_GT')
        with self.assertRaises(ValueError): joint_adapter(dict(units='cm'))


if __name__ == '__main__': unittest.main()
