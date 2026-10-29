"""离线整段输入模型：非因果背景与离线地面只能显式安装，不进入在线默认链。"""
import unittest
from types import SimpleNamespace

import numpy as np

from test_range_frontend import scene
from core.range_contract import binding_tuple
from core.range_features import bound_ground
from core.range_offline import QuantileBackground, fit_declared_plane
from core.range_runtime import RangeRuntime


def fake_frame(range_m, sha='grid', binding=('b',)):
    return SimpleNamespace(range_m=np.asarray(range_m,dtype=float),
        valid=np.isfinite(np.asarray(range_m,dtype=float)),
        grid=SimpleNamespace(shape=np.shape(range_m),sha256=sha),binding=binding)


class QuantileBackgroundTests(unittest.TestCase):
    def test_quantile_keeps_far_surface_and_marks_unobserved_rays_unknown(self):
        stack=np.full((25,8,24),4.0,dtype=np.float32)
        stack[0:2,0,0]=2.0        # 人只挡 2 帧 → 背景仍是 4 m
        stack[:,0,1]=1.0          # 一直很近的静态物体 → 背景 1 m
        stack[:,0,3]=np.nan       # 从未观测 → unknown
        observed=np.isfinite(stack).sum(axis=0).astype(np.int32)
        background=QuantileBackground.from_stack(stack,observed,binding=('b',),grid_sha256='grid')
        self.assertTrue(background.known[0,0] and background.known[0,1])
        self.assertAlmostEqual(float(background.mean_m[0,0]),4.0,places=6)
        self.assertAlmostEqual(float(background.mean_m[0,1]),1.0,places=6)
        self.assertFalse(background.known[0,3])
        self.assertTrue(np.isnan(background.mean_m[0,3]))

    def test_foreground_only_accepts_closer_returns_and_rejects_other_binding(self):
        background=QuantileBackground(np.full((8,24),4.0),np.ones((8,24),bool),
            binding=('b',),grid_sha256='grid')
        depth=np.full((8,24),4.0); depth[0,0]=3.5; depth[0,1]=4.5
        result=background.foreground(fake_frame(depth))
        self.assertTrue(result['mask'][0,0])        # 明显更近 → 前景
        self.assertFalse(result['mask'][0,1])       # 更远不算前景（离线声明的更近判据）
        self.assertFalse(result['mask'][1,1])
        self.assertEqual(result['status'],'ready')
        with self.assertRaises(ValueError):
            background.foreground(fake_frame(depth,binding=('other',)))

    def test_missing_declaration_is_rejected_by_construction(self):
        with self.assertRaises(ValueError):
            QuantileBackground(np.zeros((2,2)),np.ones((2,2),bool),binding=('b',),grid_sha256='g',
                               quantile=.5)
        with self.assertRaises(ValueError):
            QuantileBackground.from_stack(np.zeros((1,2,2),dtype=np.float32),
                np.zeros((2,2),dtype=np.int32),binding=('b',),grid_sha256='g')


class InstalledBackgroundRuntimeTests(unittest.TestCase):
    def setup(self):
        grid,raw,_=scene(np.full((8,24),3.))
        identity=dict(session='offline',coordinate='RAW/lidar',grid_sha256=grid.sha256)
        background=QuantileBackground(np.full((8,24),3.0),np.ones((8,24),bool),
            binding=binding_tuple(identity),grid_sha256=grid.sha256)
        return grid,raw,identity,background

    def runtime(self,background):
        grid,raw,identity,_=self.setup()
        return RangeRuntime(grid,identity,empty_prefix_frames=None,background=background),raw

    def test_installed_background_needs_explicit_non_causal_model(self):
        grid,raw,identity,background=self.setup()
        with self.assertRaises(ValueError):
            RangeRuntime(grid,identity,empty_prefix_frames=None,background=object())
        with self.assertRaises(ValueError):
            RangeRuntime(grid,identity,empty_prefix_frames=2,background=background)
        wrong=QuantileBackground(np.full((8,24),3.0),np.ones((8,24),bool),
            binding=('other',),grid_sha256=grid.sha256)
        with self.assertRaises(ValueError):
            RangeRuntime(grid,identity,empty_prefix_frames=None,background=wrong)

    def test_installed_background_produces_targets_without_prefix(self):
        background=self.setup()[3]
        runtime,raw=self.runtime(background)
        result=None
        for i in range(8):
            depth=np.full((8,24),3.)
            if i>=2:depth[2:6,8:14]=2.
            grid,packed,_=scene(depth)
            result,_,_=runtime.update(packed,i*.1,i)
        self.assertEqual(result['status'],'ready')
        self.assertTrue(result['tracking']['target_source_rows'])
        self.assertIsNone(result['rule']['state']['new_event'])

    def test_declared_background_survives_time_gap_but_not_binding_change(self):
        background=self.setup()[3]
        runtime,raw=self.runtime(background)
        for i in range(3):runtime.update(raw,i*.1,i)
        result,_,_=runtime.update(raw,5.0,3)
        self.assertEqual(result['tracking']['reset_reason'],'stream_gap')
        self.assertIs(runtime.background,background)
        self.assertEqual(result['status'],'ready')
        changed=dict(runtime.identity);changed['session']='other'
        result,_,_=runtime.update(raw,5.1,4,identity=changed)
        self.assertIsNone(runtime.background)
        self.assertEqual(result['status'],'background_requires_explicit_rebind')


class OfflinePlaneTests(unittest.TestCase):
    def points(self):
        rng=np.random.default_rng(4)
        xy=rng.uniform(-2,2,size=(4000,2))
        return np.c_[xy,np.full(4000,1.2)]

    def test_plane_is_bound_but_never_runtime_eligible(self):
        grid,raw,_=scene(np.full((8,24),3.))
        identity=dict(session='offline',coordinate='RAW/lidar',grid_sha256=grid.sha256)
        ground=fit_declared_plane(self.points(),binding=identity,frame='lidar')
        self.assertEqual(ground['status'],'valid')
        self.assertAlmostEqual(ground['offset_m'],1.2,places=2)
        self.assertTrue(ground['offline_only'])
        self.assertFalse(ground['runtime_eligible'])
        self.assertFalse(ground['physical_verified'])
        self.assertEqual(ground['binding'],identity)
        frame=grid.decode(raw,binding_tuple(identity))
        self.assertIs(bound_ground(frame,ground),ground)

    def test_degenerate_or_unbound_input_rejected(self):
        with self.assertRaises(ValueError):fit_declared_plane(np.zeros((10,3)))
        with self.assertRaises(ValueError):fit_declared_plane(np.full((500,3),np.nan))


if __name__=='__main__':unittest.main()