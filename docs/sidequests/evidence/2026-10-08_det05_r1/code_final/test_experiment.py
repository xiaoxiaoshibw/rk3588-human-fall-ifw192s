import json
from pathlib import Path
import tempfile
import unittest

import numpy as np
import torch
from cpu_pointpillars import Voxelization, nms_cuda
from experiment import adapt, read_frame
from audit_truth import covers_xy


class ExperimentTests(unittest.TestCase):
    def fixture(self, root, stride):
        pts=np.array([[1,2,3,740],[4,5,6,978]],dtype="<f4")
        data=bytearray(stride*len(pts))
        np.ndarray(pts.shape,dtype="<f4",buffer=data,strides=(stride,4))[:]=pts
        layout=dict(fields=["x","y","z","intensity"],dtype="<f4",stride_points=4)
        if stride==28:
            # Deliberately poison ring/padding/time: these bytes must never become XYZI.
            data[16:28]=b'\xff'*12
            layout=dict(fields=["x","y","z","intensity","ring","timestamp"],
                        dtypes=["<f4"]*4+["<u2","<f4"],endian="little",stride_bytes=28)
        meta=dict(format="human_capture_session",format_version=1,point_file="points.bin",
                  point_stride_bytes=stride,point_layout=layout,frames=[dict(seq=5,offset_points=0,count_points=2)])
        (root/"meta.json").write_text(json.dumps(meta),encoding="utf-8")
        (root/"points.bin").write_bytes(data)
        return pts,meta

    def test_both_layouts(self):
        for stride in (16,28):
            with tempfile.TemporaryDirectory() as d:
                root=Path(d); expected,_=self.fixture(root,stride)
                np.testing.assert_array_equal(read_frame(root,0)[0],expected)

    def test_reject_bad_layout_length_and_frame(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); _,meta=self.fixture(root,28)
            for index in (-1,1,True):
                with self.assertRaises(ValueError):read_frame(root,index)
            meta["point_layout"]["endian"]="big"
            (root/"meta.json").write_text(json.dumps(meta),encoding="utf-8")
            with self.assertRaises(ValueError):read_frame(root,0)
            self.fixture(root,28)
            with (root/"points.bin").open("ab") as f:f.write(b'\x00')
            with self.assertRaises(ValueError):read_frame(root,0)

    def test_reject_nonfinite(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); self.fixture(root,16)
            np.full((2,4),np.nan,dtype="<f4").tofile(root/"points.bin")
            with self.assertRaises(ValueError):read_frame(root,0)

    def test_transform_and_intensity(self):
        p=np.array([[1,0,2,1023]],dtype=np.float32)
        t=dict(R=[[0,-1,0],[1,0,0],[0,0,1]],t=[0,0,1])
        np.testing.assert_allclose(adapt(p,t,-1.73,1023),[[0,1,1.27,1]],atol=1e-6)
        with self.assertRaises(ValueError):adapt(p,t,0,0)
        t["R"][0][1]=1
        with self.assertRaises(ValueError):adapt(p,t,0,1)

    def test_zero_xyz_removed_before_translation(self):
        points=np.array([[0,0,0,978],[2,1,1,1023]],dtype=np.float32)
        t=dict(R=np.eye(3).tolist(),t=[0,0,1.36])
        np.testing.assert_allclose(adapt(points,t,-1.73,1023),[[2,1,.63,1]],atol=1e-6)
        with self.assertRaises(ValueError):adapt(points[:1],t,-1.73,1023)

    def test_voxel_first_seen_and_capacity(self):
        v=Voxelization([1,1,1],[0,0,0,3,3,3],2,(2,2))
        pts=torch.tensor([[1.1,.1,.1,1],[1.2,.1,.1,2],[1.3,.1,.1,3],
                          [.1,.1,.1,4],[2.1,.1,.1,5],[1.4,.1,.1,6],[3,0,0,7]],dtype=torch.float32)
        vox,coords,counts=v(pts)
        self.assertEqual(coords.tolist(),[[1,0,0],[0,0,0]])
        self.assertEqual(counts.tolist(),[2,1])
        self.assertEqual(vox[0,:,3].tolist(),[1,2])
        with self.assertRaises(ValueError):v(torch.tensor([[3.,0,0,1]]))

    def test_rotated_nms(self):
        # Thin perpendicular boxes have IoU ~0.026, unlike identical axis-aligned boxes.
        boxes=torch.tensor([[-2,-.1,2,.1,0],[-2,-.1,2,.1,np.pi/2],[-2,-.1,2,.1,0]],dtype=torch.float32)
        scores=torch.tensor([.9,.8,.7])
        self.assertEqual(nms_cuda(boxes,scores,.1).tolist(),[0,1])
        self.assertEqual(nms_cuda(boxes,scores,.1,post_max_size=1).tolist(),[0])
        self.assertEqual(nms_cuda(boxes[:0],scores[:0],.1).tolist(),[])

    def test_pinned_upstream_clockwise_yaw(self):
        boxes=torch.tensor([[-2,-.1,2,.1,np.pi/4],[-1.5,-.6,2.5,-.4,np.pi/4]],dtype=torch.float32)
        scores=torch.tensor([.9,.8])
        self.assertEqual(nms_cuda(boxes,scores,.01).tolist(),[0])
        self.assertEqual(nms_cuda(boxes,scores,.01,clockwise=False).tolist(),[0,1])
        box=[0,0,-.6,4,.2,1.73,np.pi/4]
        self.assertTrue(covers_xy(box,[1,-1]))
        self.assertFalse(covers_xy(box,[1,1]))

    def test_det04_delete_frozen_and_zero_counts(self):
        from det04 import DeletionProbe, assert_frozen
        base=Voxelization([1,1,4],[0,0,-3,4,4,1],32,(16,16))
        points=torch.tensor([[.1,.1,-1,1],[.2,.1,-.5,2],[1.1,.1,-1,3]],dtype=torch.float32)
        canonical=base(points)
        keep=np.array([True,False])
        probe=DeletionProbe(base,canonical,keep)
        v,c,n=probe(points)
        np.testing.assert_array_equal(v.numpy(),canonical[0].numpy()[keep])
        self.assertEqual(n.tolist(),[2])
        self.assertEqual(probe.last[2].tolist(),[2,0])
        bad=(probe.last[0].clone(),probe.last[1].clone(),probe.last[2].clone())
        bad[0][0,0,2]+=1
        with self.assertRaises(AssertionError):assert_frozen(canonical,bad,keep)
        bad=(probe.last[0].clone(),probe.last[1].clone(),probe.last[2].clone())
        bad[2][1]=1
        with self.assertRaises(AssertionError):assert_frozen(canonical,bad,keep)

    def test_det04_ground_band_whole_pillar_and_receptive_field(self):
        from det04 import masks, adapted, receptive_bounds, corr
        base=Voxelization([1,1,4],[0,0,-3,4,4,1],32,(16,16))
        cloud=np.array([[.1,.1,.05,1],[1.1,.1,-.15,1],[1.2,.1,.30,1],
                        [2.1,.1,.20,1],[2.2,.1,.31,1]],dtype='f4')
        v,c,n=base(torch.from_numpy(adapted(cloud)))
        local,ground,_=masks(cloud,c.numpy(),base,[.1,.1])
        self.assertEqual(local.tolist(),[True,False,False])
        self.assertEqual(ground.tolist(),[True,True,False])
        # head (x=8,y=12), deepest path maps to canvas center(16,24), radius73.
        bounds=receptive_bounds((12*216+8)*6)
        self.assertEqual(bounds[-1],[[-57,-49],[89,97]])
        self.assertIsNone(corr([1,1,1],[1,2,3]))
        self.assertAlmostEqual(corr([1,1,2],[1,1,3],True),1)


    def test_det05_purity_rule(self):
        from det05 import classify_pillars
        groups={(0,0,0):[0,1],(1,0,0):[2,3],(2,0,0):[4],(3,0,0):[5,6],(4,0,0):[7]}
        ids=np.arange(8,dtype='i8')
        label_map={0:'human',1:'human',2:'human',3:'furniture',4:None,5:'human',6:'mixed_uncertain',7:'human'}
        out=classify_pillars(groups,ids,label_map)
        self.assertTrue(out[(0,0,0)]['pure']);self.assertEqual(out[(0,0,0)]['reason'],'pure')
        self.assertEqual(out[(1,0,0)]['reason'],'furniture')
        self.assertEqual(out[(2,0,0)]['reason'],'unlabeled')
        self.assertEqual(out[(3,0,0)]['reason'],'mixed_uncertain')
        self.assertTrue(out[(4,0,0)]['pure'])
        self.assertEqual(out[(3,0,0)]['human'],1)

    def test_det05_pure_switch_only_pure_pillars(self):
        from diagnose_low_scores import SamplingProbe
        from det05 import PureSwitchProbe
        base=Voxelization([1,1,4],[0,0,-3,4,4,1],32,(16,16))
        zs=np.linspace(-2,.9,40)
        pts=np.array([[.1,.1,z,1] for z in zs]+[[1.1,.1,-1,2],[2.1,.1,-1,3]],dtype='f4')
        t=torch.from_numpy(pts)
        s32=SamplingProbe(base);s32.mode='first32'
        v1,c1,n1=s32(t)
        key=tuple(int(x) for x in c1[0])
        sw=PureSwitchProbe(base,[key])
        v2,c2,n2=sw(t)
        np.testing.assert_array_equal(c1.numpy(),c2.numpy())
        np.testing.assert_array_equal(n1.numpy(),n2.numpy())
        changed=[j for j in range(len(v1)) if not torch.equal(v1[j],v2[j])]
        self.assertEqual(changed,[0])
        self.assertEqual(sw.switched,[0])
        self.assertEqual(int(n1[0]),32)
        self.assertFalse(torch.equal(v2[0,:32,2],v1[0,:32,2]))
        self.assertTrue(torch.equal(v2[1],v1[1]) and torch.equal(v2[2],v1[2]))
        self.assertEqual(int(s32.last[3][0]),40)


if __name__=="__main__":unittest.main()

