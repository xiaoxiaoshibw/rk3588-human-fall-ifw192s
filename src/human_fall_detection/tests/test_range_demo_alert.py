"""Same-frame geometric hint; synthetic checks are not human ground truth."""
import math
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.range_demo_alert import DemoAlert

class DemoObserverTests(unittest.TestCase):
    def row(self, i, **changes):
        row = dict(i=i, t=i*.1, tid='a', n=40, hm=.4, ht=.6, sp=.6,
                   generation=1, binding=('sensor','ground'), reset=False)
        row.update(changes)
        return row

    def test_two_stages_and_breaks(self):
        obs = DemoAlert()
        self.assertEqual([obs.update(self.row(i)) for i in range(31)], [0]*15+[1]*15+[2])
        for changes in (dict(tid=None,n=0), dict(hm=math.nan), dict(ht=.701), dict(sp=.499),
                        dict(generation=2), dict(binding=('other',)), dict(reset=True)):
            obs = DemoAlert()
            for i in range(16): obs.update(self.row(i))
            self.assertEqual(obs.update(self.row(16, **changes)), 0)
            self.assertEqual(obs.duration, 0.)
        obs=DemoAlert()
        for i in range(16):obs.update(self.row(i))
        self.assertEqual(obs.update(self.row(18)),0)
        self.assertEqual(obs.update(self.row(19,t=2.2)),0)

    def test_equal_thresholds_and_same_frame_requirement(self):
        obs=DemoAlert()
        for i in range(16):
            level=obs.update(self.row(i,hm=.5,ht=.7,sp=.5))
        self.assertEqual(level,1)
        self.assertEqual(obs.update(self.row(16,tid='b')),0)
        row=self.row(17); row['i']=None
        self.assertEqual(obs.update(row),0)

if __name__ == '__main__': unittest.main()
