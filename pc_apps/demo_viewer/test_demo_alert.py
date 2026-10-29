import math
import unittest
from demo_alert import DemoAlert
from render_video import SOURCE, SESSIONS, load_records


class DemoAlertTest(unittest.TestCase):
    def test_continuity_and_invalid_measurements(self):
        observer = DemoAlert()
        row = dict(i=0,t=0.,tid='a',n=100,hm=.25,ht=.4,sp=.8)
        for i in range(15):
            self.assertFalse(observer.update(dict(row,i=i,t=i*.1)))
        self.assertTrue(observer.update(dict(row,i=15,t=1.5)))
        for i in range(16,30): self.assertEqual(observer.update(dict(row,i=i,t=i*.1)),1)
        self.assertEqual(observer.update(dict(row,i=30,t=3.)),2)
        self.assertFalse(observer.update(dict(row,i=31,t=3.1,tid='b')))
        self.assertFalse(observer.update(dict(row,i=32,t=3.2,hm=math.nan)))
        self.assertFalse(observer.update(dict(row,i=34,t=3.4)))
        self.assertFalse(observer.update(dict(row,i=35,t=None)))
        self.assertFalse(observer.update(dict(row,i=36,t=3.6)))

    def test_four_recordings_offline(self):
        # Development examples, not independent accuracy evaluation.
        for name, _ in SESSIONS:
            rows = load_records(SOURCE/('replay_'+name)/'data/frames.js')
            observer = DemoAlert()
            levels = [observer.update(r) for r in rows]
            if name == 'jixiedaiwanyao':
                self.assertNotIn(1, levels)
                self.assertNotIn(2, levels)
            else:
                self.assertIn(1, levels, name)
                self.assertIn(2, levels, name)


if __name__ == '__main__':
    unittest.main()
