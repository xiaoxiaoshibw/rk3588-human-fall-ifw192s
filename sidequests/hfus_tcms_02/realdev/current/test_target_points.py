"""Synthetic source membership: competition must never pick the largest component."""

# Explicit legacy acquisition keeps these original lifecycle contracts covered.
import unittest
import numpy as np
from target_points import components
from project_fall import FallRuntime


class IdentityCoordinates:
    def points(self, points):return np.asarray(points)


class TargetPoints(unittest.TestCase):
    def test_components_partition_every_source_row_and_reject_noise(self):
        body=np.stack(np.meshgrid(np.linspace(0,.2,6),np.linspace(0,.2,6),
                                  np.linspace(.1,1.6,32)), -1).reshape(-1,3)
        points=np.vstack([body+[2,0,0],body+[4,0,0],[[6,0,0]]])
        rows=np.arange(len(points))+123
        candidates,ledger=components(points,rows,IdentityCoordinates())
        self.assertEqual(len(candidates),2)
        self.assertEqual(sorted(i for c in ledger for i in c['source_rows']),rows.tolist())
        self.assertEqual(ledger[-1]['reason'],'insufficient_support')
        runtime=FallRuntime('synthetic','g', acquisition_settings={'human_entry_gate': False})
        for i in range(12):
            output=runtime.step(i*.1,candidates)
            self.assertEqual(output['acquisition']['status'],'ambiguous')
            self.assertEqual(output['target_rows'],[])
        for i in range(7):output=runtime.step(2+i*.1,candidates[:1])
        self.assertEqual(output['track']['status'],'locked')
        self.assertEqual(output['target_rows'],candidates[0]['source_rows'])


if __name__=='__main__':unittest.main()
