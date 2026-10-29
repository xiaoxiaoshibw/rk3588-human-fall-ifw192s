import tempfile
import io
import pickle
from pathlib import Path
import unittest
import numpy as np
import torch
from train_deep_lidar import CausalPointNet,batch,last_step,windows
from audit_momo import decode,NumericUnpickler


class DeepLidarTest(unittest.TestCase):
    def setUp(self):
        torch.set_num_threads(2);torch.manual_seed(12)

    def test_future_does_not_change_earlier_outputs(self):
        m=CausalPointNet();x=torch.randn(2,30,16,3);other=x.clone();other[:,20:]=torch.randn_like(other[:,20:])*100
        for training in [True,False]:
            m.train(training)
            with torch.no_grad():
                a=m(x);b=m(other)
            torch.testing.assert_close(a[:,:20],b[:,:20],atol=0,rtol=0)
            self.assertFalse(torch.allclose(a[:,20:],b[:,20:]))

    def test_point_permutation_and_translation(self):
        m=CausalPointNet().eval();x=torch.randn(2,10,16,3)
        with torch.no_grad():
            a=m(x);b=m(x[:,:,torch.arange(15,-1,-1)]);c=m(x+torch.tensor([5.,2.,3.]))
        torch.testing.assert_close(a,b,atol=2e-6,rtol=1e-5)
        torch.testing.assert_close(a,c,atol=2e-6,rtol=1e-5)

    def test_backward_reload_and_invalid(self):
        m=CausalPointNet();x=torch.randn(2,10,16,3);target=torch.tensor([2,2]);opt=torch.optim.AdamW(m.parameters(),lr=.001)
        before=float(torch.nn.functional.cross_entropy(m(x)[:,-1],target).detach())
        for _ in range(4):
            opt.zero_grad(set_to_none=True);loss=torch.nn.functional.cross_entropy(m(x)[:,-1],target)
            loss.backward();self.assertTrue(all(torch.isfinite(p.grad).all() for p in m.parameters() if p.grad is not None));opt.step()
        self.assertLess(float(torch.nn.functional.cross_entropy(m(x)[:,-1],target).detach()),before)
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'weights.pt';torch.save(m.state_dict(),path)
            loaded=CausalPointNet();loaded.load_state_dict(torch.load(path,weights_only=True,map_location='cpu'))
            with torch.no_grad():torch.testing.assert_close(m(x),loaded(x),atol=0,rtol=0)
        for bad in [torch.zeros(2,3),torch.full((1,30,16,3),float('nan')),torch.zeros(1,0,16,3)]:
            with self.assertRaises(ValueError):m(bad)

    def test_short_sequence_keeps_one_causal_window(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'cache.npz'
            np.savez(path,**{'E01/S01/A01':np.zeros((20,8,3),np.float32),
                             'E01/S01/A02':np.zeros((45,8,3),np.float32)})
            with np.load(path,allow_pickle=False) as cache:arrays,rows=windows(cache)
        short=[(r['begin_index'],r['end_index_exclusive']) for r in rows if r['sequence'].endswith('A01')]
        long=[(r['begin_index'],r['end_index_exclusive']) for r in rows if r['sequence'].endswith('A02')]
        self.assertEqual(short,[(0,20)])
        self.assertEqual(long,[(0,30),(10,40)])
        self.assertTrue(all(r['label_kind']=='inherited_sequence_action' for r in rows))

    def test_padded_batch_matches_separate_runs(self):
        m=CausalPointNet().eval()
        lengths=torch.tensor([12,25])
        arrays={'a':torch.randn(12,8,3),'b':torch.randn(25,8,3)}
        rows=[{'sequence':'a','begin_index':0,'end_index_exclusive':12,'truth':1},
              {'sequence':'b','begin_index':0,'end_index_exclusive':25,'truth':2}]
        x,_,padded_lengths=batch(arrays,rows,[0,1])
        self.assertEqual(x.shape,(2,25,8,3));torch.testing.assert_close(padded_lengths,lengths)
        with torch.no_grad():
            joint=m(x);separate=[m(arrays['a'][None]),m(arrays['b'][None])]
            torch.testing.assert_close(joint[0,:12],separate[0][0],atol=1e-6,rtol=1e-5)
            torch.testing.assert_close(last_step(joint,lengths)[0],separate[0][0,-1],atol=1e-6,rtol=1e-5)
            torch.testing.assert_close(last_step(joint,lengths)[1],separate[1][0,-1],atol=1e-6,rtol=1e-5)

    def test_numeric_dataset_reader_rejects_executable_globals(self):
        frames=[np.zeros((12,3),dtype=np.float64),np.ones((16,3),dtype=np.float64)]
        result=decode(pickle.dumps(frames,protocol=4))
        for expected,actual in zip(frames,result):np.testing.assert_array_equal(expected,actual)
        # GLOBAL builtins.eval is rejected before any call; no executable dataset code is loaded.
        with self.assertRaises(pickle.UnpicklingError):NumericUnpickler(io.BytesIO(b'cbuiltins\neval\n.')).load()
        with self.assertRaises(ValueError):decode(pickle.dumps([]))
        model=CausalPointNet(classes=30)
        with torch.no_grad():self.assertEqual(tuple(model(torch.zeros(1,20,64,3)).shape),(1,20,30))


if __name__=='__main__':unittest.main()
