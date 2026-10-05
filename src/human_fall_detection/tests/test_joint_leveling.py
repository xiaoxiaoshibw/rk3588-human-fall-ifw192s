"""Joint pose GT and independent fixed-FIT holdout invariants."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from core.capture_input import prepare_npz,load_adapted,ROW_DTYPE
from core.calibration import validate_known_transform,validate_geometry_calibration
from core.joint_leveling import (joint_rotation,freeze_joint_selection,solve_joint_leveling,
                                 validate_joint_model)
from core.ground_evidence import digest
from fit_joint_leveling import fit_capture_joint
from test_gli01_capture_input import write_export


class JointLevelingTest(unittest.TestCase):
    def fixture(self,root,pitch=26.234,roll=-1.322,height=1.322,offsets=(0,0,0,0),noise_std=0):
        directory=root/'source';write_export(directory,counts=(121,121,121,121))
        # Independent explicit inverse scalar rotation of a known ground grid.
        p=np.deg2rad(pitch);r=np.deg2rad(roll);c,s,cr,sr=np.cos(p),np.sin(p),np.cos(r),np.sin(r)
        raw=np.zeros(484,dtype=ROW_DTYPE);k=0;rng=np.random.RandomState(41)
        for dz in offsets:
            for x in np.linspace(.5,3,11):
                for y in np.linspace(-1,1,11):
                    z=dz+rng.normal(0,noise_std)
                    yy=cr*y+sr*(z-height);zz=-sr*y+cr*(z-height)
                    raw['x'][k]=c*x-s*zz;raw['y'][k]=yy;raw['z'][k]=s*x+c*zz;k+=1
        (directory/'points.bin').write_bytes(raw.tobytes())
        npz=root/'source.npz';prepare_npz(str(directory),'innolidar','m',str(npz));m,pts=load_adapted(npz)
        initial={'pitch_deg':26.0,'roll_deg':0.0,'tz_m':1.34,'from_frame':'innolidar',
                 'to_frame':'ground_joint_estimate','provenance':'synthetic test initial'}
        regions=[dict(region_id='r%d'%i,role='fit' if i==0 else 'validation',frame_group=gid,
                      x_min_m=-10.,x_max_m=10.,y_min_m=-10.,y_max_m=10.) for i,gid in enumerate(m['frame_groups'])]
        selection=freeze_joint_selection(pts,m,initial,regions)
        return npz,m,pts,initial,regions,selection

    def test_gt_joint_parameters_noise_free_and_pose_invariance_C01_C05(self):
        for p,r,h in [(26.234,-1.322,1.322),(0,0,1.1),(40,8,1.8),(-10,-5,.7)]:
            with self.subTest(p=p,r=r,h=h),tempfile.TemporaryDirectory() as tmp:
                _,m,points,_,_,sel=self.fixture(Path(tmp),p,r,h)
                model,report=solve_joint_leveling(points,m,sel)
                self.assertAlmostEqual(model['pitch_deg'],p,places=4);self.assertAlmostEqual(model['roll_deg'],r,places=4)
                self.assertAlmostEqual(model['tz_m'],h,places=5);self.assertEqual(report['validation_quality'],'PASS')
                self.assertLess(report['orthogonal_residual_invariance_max_difference_m'],1e-12)

    def test_local_self_fit_cannot_replace_one_FIT_plane_C04(self):
        with tempfile.TemporaryDirectory() as tmp:
            _,m,points,_,_,sel=self.fixture(Path(tmp),offsets=(0,.06,.06,.06))
            _,report=solve_joint_leveling(points,m,sel)
            self.assertEqual(report['validation_quality'],'FAIL')
            for r in report['regions'][1:]:
                self.assertGreater(r['same_FIT_plane_full_point_stats']['rms_m'],.059)
                self.assertLess(r['local_self_fit_diagnostic_only']['rms_m'],1e-6)
                self.assertEqual(r['fixed_plane_quality'],'FAIL')

    def test_noisy_ground_and_collinear_FIT_C01_C04(self):
        with tempfile.TemporaryDirectory() as tmp:
            npz,m,points,initial,regions,sel=self.fixture(Path(tmp),noise_std=.008)
            model,report=solve_joint_leveling(points,m,sel)
            self.assertEqual(report['validation_quality'],'PASS')
            self.assertLess(abs(model['tz_m']-1.322),.01)
            raw=np.zeros(484,dtype=ROW_DTYPE);raw['x']=np.tile(np.linspace(.5,3,121),(4,)).ravel();raw['z']=-1
            (Path(tmp)/'source/points.bin').write_bytes(raw.tobytes())
            changed=Path(tmp)/'line.npz';prepare_npz(str(Path(tmp)/'source'),'innolidar','m',str(changed))
            mm,pp=load_adapted(changed)
            gg=list(mm['frame_groups']);new_regions=[dict(r,frame_group=gg[i]) for i,r in enumerate(regions)]
            frozen=freeze_joint_selection(pp,mm,initial,new_regions)
            with self.assertRaises(ValueError):solve_joint_leveling(pp,mm,frozen)

    def test_frozen_rows_same_ID_caller_modification_alias_and_Z_cut_C02_C03_C07(self):
        with tempfile.TemporaryDirectory() as tmp:
            _,m,points,initial,regions,sel=self.fixture(Path(tmp))
            for change in [lambda s:s['fit']['indices'].pop(),lambda s:s.update(schema=True),
                           lambda s:s['binding'].update(units='mm')]:
                bad=copy.deepcopy(sel);change(bad)
                with self.assertRaises(ValueError):solve_joint_leveling(points,m,bad)
            changed=points.copy();changed[0,2]+=.1
            with self.assertRaises(ValueError):solve_joint_leveling(changed,m,sel)
            for change in [lambda r:r[1].update(frame_group=r[0]['frame_group']),
                           lambda r:r[1].update(region_id=r[0]['region_id']),lambda r:r[1].update(z_min_m=-.15)]:
                rr=copy.deepcopy(regions);change(rr)
                with self.assertRaises(ValueError):freeze_joint_selection(points,m,initial,rr)
            for value in (True,'26',float('nan')):
                bad=copy.deepcopy(initial);bad['pitch_deg']=value
                with self.assertRaises(ValueError):freeze_joint_selection(points,m,bad,regions)

    def test_quality_failure_no_runtime_or_physical_promotion_C06(self):
        with tempfile.TemporaryDirectory() as tmp:
            npz,m,points,_,_,sel=self.fixture(Path(tmp),offsets=(0,.06,.06,.06))
            model,_=solve_joint_leveling(points,m,sel)
            with self.assertRaises(ValueError):validate_known_transform(model)
            with self.assertRaises(ValueError):validate_geometry_calibration(model)
            for key in ('physical_verified','runtime_eligible','candidate_eligible'):
                bad=copy.deepcopy(model);bad[key]=True;bad['model_id']='joint:'+digest({k:v for k,v in bad.items() if k!='model_id'})
                with self.assertRaises(ValueError):validate_joint_model(bad)
            out=Path(tmp)/'docs/human_fall/evidence/2026-10-04_gl_c01_r1';out.mkdir(parents=True)
            sp=Path(tmp)/'selection.json';sp.write_text(json.dumps(sel),encoding='utf8')
            result=fit_capture_joint(npz,sp,out/'run',tmp)
            self.assertEqual(result['validation_quality'],'FAIL');self.assertFalse(result['candidate_eligible'])
            for target in (out/'run',Path(tmp)/'captures/bad',out):
                with self.assertRaises(ValueError):fit_capture_joint(npz,sp,target,tmp)


if __name__=='__main__':unittest.main()
