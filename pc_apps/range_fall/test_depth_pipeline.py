"""Synthetic ray/object pipeline check; no human identity or physical-fall GT."""
from pathlib import Path
import sys
import tempfile
import unittest

import numpy as np

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src/human_fall_detection'))
sys.path.insert(0,str(ROOT/'src/human_fall_detection/scripts'))
from core.capture_input import ROW_DTYPE
from core.range_image import ScanGrid
from core.range_runtime import RangeRuntime
from core.range_posture import PostureObserver
from replay_range_frontend import CALIBRATION
from depth import export_depth
from test_depth import pixels


class TestRayPipeline(unittest.TestCase):
    def test_laterally_lying_object_from_raw_rays_to_same_frame_export(self):
        grid=ScanGrid.from_csv(CALIBRATION/'ifw192s_azimuth_192x256.csv',CALIBRATION/'ifw192s_elevation_192x256.csv')
        az,el=np.radians(grid.azimuth_deg.ravel()),np.radians(grid.elevation_deg.ravel())
        directions=np.column_stack((np.cos(el)*np.cos(az),np.cos(el)*np.sin(az),np.sin(el)))
        identity=dict(session='synthetic',meta_sha256='a'*64,points_sha256='b'*64,coordinate='RAW/innolidar',
                      units='m',coordinate_transform='identity',grid_sha256=grid.sha256,epoch='source_header_epoch')
        ground=dict(status='valid',normal=[0,0,1],offset_m=1,frame='innolidar',binding=identity)
        runtime=RangeRuntime(grid,identity,empty_prefix_frames=3,ground=ground,ground_sha='synthetic-plane')
        observer=PostureObserver()
        raw=np.zeros(len(az),dtype=ROW_DTYPE);raw['ring']=np.repeat(np.arange(192),256)
        # Slab intersection with a fixed, explicitly non-human cuboid above z=-1 ground.
        a=np.array([2.7,-.8,-.9])/directions;b=np.array([3.,.8,-.6])/directions
        near=np.minimum(a,b).max(axis=1);far=np.maximum(a,b).min(axis=1)
        hit=(far>=near)&(near>.1)
        for i in range(35):
            distance=np.full(len(az),6.)
            if i>=3:distance[hit]=near[hit]
            xyz=directions*distance[:,None]
            for c,name in enumerate(('x','y','z')):raw[name]=xyz[:,c]
            raw['timestamp']=i*.1
            result,frame,_=runtime.update(raw.tobytes(),i*.1,i)
            pose=observer.update(result['rule']['features'],result['tracking'],frame.binding)
            self.assertNotIn(result['rule']['state']['state'],('suspected','confirmed'))
            if i==19:self.assertEqual(pose['state'],'lying_pending')
            if i>=20:self.assertEqual(pose['state'],'lying_candidate')
        self.assertEqual(pose['humanSemantic'],'UNKNOWN')
        with tempfile.TemporaryDirectory() as tmp:
            import hashlib
            d=export_depth(frame,result['tracking']['target_source_rows'],tmp,34,3.4,
                           hashlib.sha256(raw.tobytes()).hexdigest(),identity)
            mask=pixels((Path(tmp)/d['mask']['path']).read_bytes())
            expected=np.isin(frame.source_rows,result['tracking']['target_source_rows']) & frame.valid
            np.testing.assert_array_equal(mask[::-1,::-1]==255,expected)
            self.assertEqual(d['targetPixels'],796)


if __name__=='__main__':unittest.main()
