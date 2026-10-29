import unittest
import io
import tempfile
from pathlib import Path
import zipfile
import numpy as np
from train_public_lidar import frame_feature, sequence_feature, ordered_names, synthetic_xyz, collect
from sklearn.model_selection import StratifiedGroupKFold


class PublicLidarTest(unittest.TestCase):
    def test_geometry_and_temporal_contract(self):
        rng=np.random.default_rng(12)
        p=rng.normal(size=(200,3))
        np.testing.assert_allclose(frame_feature(p),frame_feature(p[::-1]),atol=1e-12)
        frames=[p+[i*.1,0,i*.02] for i in range(10)]
        np.testing.assert_allclose(sequence_feature(frames),sequence_feature([f+[5,7,9] for f in frames]),atol=1e-6)
        self.assertFalse(np.allclose(sequence_feature(frames),sequence_feature(frames[::-1])))
        for bad in [np.zeros((9,3)),np.full((20,3),np.nan),np.zeros((20,4))]:
            with self.assertRaises(ValueError):frame_feature(bad)

    def test_order_and_group_isolation(self):
        self.assertEqual(ordered_names(['a/lidar/frame010.bin','a/lidar/frame002.bin'],'mmfi')[0],'a/lidar/frame002.bin')
        groups=np.repeat(np.arange(10),2); y=np.tile([0,1],10); X=np.zeros((20,1))
        seen=[]
        for tr,te in StratifiedGroupKFold(5,shuffle=True,random_state=42).split(X,y,groups):
            self.assertFalse(set(groups[tr]) & set(groups[te])); seen.extend(te)
        self.assertEqual(sorted(seen),list(range(20)))

    def test_synthetic_parser_rejects_silent_row_loss(self):
        header='categoryID;partID;X;Y;Z;distance;X_noise;Y_noise;Z_noise;distance_noise;intensity\n'
        valid='5;0;1;2;3;4;1;2;3;4;1\n'
        np.testing.assert_array_equal(synthetic_xyz((header+valid).encode()),[[1,2,3]])
        with self.assertRaises(ValueError):synthetic_xyz((header+valid+'bad;row\n').encode())
        with self.assertRaises(ValueError):synthetic_xyz(b'')

    def test_zero_extent_and_frame_order(self):
        self.assertTrue(np.isfinite(sequence_feature([np.zeros((12,3)) for _ in range(6)])).all())
        names=['pose/frame_10_frame_10.csv','pose/frame_2_frame_2.csv']
        self.assertEqual(ordered_names(names,'synthetic'),names[::-1])

    def test_ground_truth_never_enters_features(self):
        rng=np.random.default_rng(2)
        frames=[rng.normal(size=(15,3)).astype('<f8') for _ in range(5)]
        features=[]
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for v in [0,1]:
                archive=root/('%d.zip'%v);out=root/str(v);out.mkdir()
                with zipfile.ZipFile(archive,'w') as z:
                    for i,p in enumerate(frames):z.writestr('E01/S01/A01/lidar/frame%03d.bin'%i,p.tobytes())
                    b=io.BytesIO();np.save(b,np.full((5,17,3),v,dtype=np.float32))
                    z.writestr('E01/S01/A01/ground_truth.npy',b.getvalue())
                features.append(collect([archive],'mmfi',out)[0])
        np.testing.assert_array_equal(*features)


if __name__=='__main__':unittest.main()
