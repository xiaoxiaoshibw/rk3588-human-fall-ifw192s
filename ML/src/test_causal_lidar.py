import tempfile
from pathlib import Path
import unittest
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from train_public_lidar import sequence_feature
from causal_public_lidar import bounds, summarize
from export_lidar_rf import export
from lidar_numpy_runtime import CausalCache, NumpyForest, frame_feature


class CausalLidarTest(unittest.TestCase):
    def test_feature_parity_and_future(self):
        rng=np.random.default_rng(42); frames=[rng.normal(size=(25,3)) for _ in range(70)]
        ff=np.asarray([frame_feature(p) for p in frames])
        for window in [10,20,30,60]:
            for lo,hi in bounds(len(frames),window):
                np.testing.assert_array_equal(summarize(ff[lo:hi]),sequence_feature(frames[lo:hi]))
        cache=CausalCache(10); outputs=[]
        for i,p in enumerate(frames[:15]):outputs.append(cache.push(p,i*.1,'a',1,'c'))
        np.testing.assert_array_equal(outputs[9],sequence_feature(frames[:10]))
        np.testing.assert_array_equal(outputs[14],sequence_feature(frames[5:15]))
        changed=frames[:10]+[p*100+500 for p in frames[10:]]
        other=CausalCache(10);earlier=None
        for i,p in enumerate(changed):
            value=other.push(p,i*.1,'a',1,'c')
            if i==9:earlier=value.copy()
        np.testing.assert_array_equal(outputs[9],earlier)
        self.assertEqual(bounds(31,30),[(0,30)])
        np.testing.assert_array_equal(summarize(ff[:10]),sequence_feature(frames[:10]+[]) )

    def test_history_boundaries(self):
        p=np.zeros((12,3)); c=CausalCache(5)
        for i in range(5):r=c.push(p,i*.1,'a',1,'c')
        self.assertIsNotNone(r)
        for binding in [('b',1,'c'),('b',2,'c'),('b',2,'d')]:
            self.assertIsNone(c.push(p,c.last_time+.1,*binding));self.assertEqual(len(c.frames),1)
        self.assertIsNone(c.push(p,9,'b',2,'d'));self.assertEqual(len(c.frames),1)
        self.assertIsNone(c.push(p,8,'b',2,'d'));self.assertEqual(len(c.frames),1)
        for bad in [np.full((12,3),np.nan),np.zeros((9,3)),np.zeros((12,4))]:
            with self.assertRaises(ValueError):c.push(bad,9,'b',2,'d')
            self.assertEqual(len(c.frames),0)
        with self.assertRaises(ValueError):c.push(p,float('inf'),'b',2,'d')
        with self.assertRaises(ValueError):c.push(p,9,None,2,'d')

    def test_rf_threshold_and_reload(self):
        rng=np.random.default_rng(5); X=rng.normal(size=(100,114)).astype(np.float32);y=np.arange(100)%3
        m=RandomForestClassifier(n_estimators=9,max_depth=4,random_state=42,n_jobs=1).fit(X,y)
        probes=[*X]
        for tree in m.estimators_:
            for f,t in zip(tree.tree_.feature,tree.tree_.threshold):
                if f<0:continue
                for value in [t,np.nextafter(np.float32(t),np.float32(-np.inf)),np.nextafter(np.float32(t),np.float32(np.inf))]:
                    row=np.zeros(114);row[f]=value;probes.append(row)
        probes=np.asarray(probes)
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'model.npz';export(m,path);a=NumpyForest(path);b=NumpyForest(path)
            np.testing.assert_allclose(m.predict_proba(probes),a.predict_proba(probes),atol=1e-15,rtol=0)
            np.testing.assert_array_equal(m.predict(probes),a.predict(probes))
            np.testing.assert_array_equal(a.predict_proba(probes),b.predict_proba(probes))
            for value in [float('nan'),float('inf'),1e100]:
                bad=X[:1].astype(float);bad[0,0]=value
                with self.assertRaises(ValueError):a.predict_proba(bad)
            with self.assertRaises(ValueError):a.predict_proba(np.zeros((1,2)))
            with self.assertRaises(FileExistsError):export(m,path)
            with np.load(path,allow_pickle=False) as source:
                corrupted={k:source[k].copy() for k in source.files}
            corrupted['left'][0]=0
            bad_path=Path(tmp)/'corrupt.npz';np.savez_compressed(bad_path,**corrupted)
            with self.assertRaises(ValueError):NumpyForest(bad_path)


if __name__=='__main__':unittest.main()
