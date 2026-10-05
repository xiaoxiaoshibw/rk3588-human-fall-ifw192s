"""GL-B01: scene footprint rows retain mixed heights; human gate is separate."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

import numpy as np

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(PACKAGE));sys.path.insert(0,str(PACKAGE/'scripts'))
from core.capture_input import load_adapted,prepare_npz,sha256_file
from core.nominal_leveling import build_nominal_model,inverse_nominal
from core.ground_region_review import (observe_review_regions,review_binding,plan_id,
                                      legacy_box_diagnostics,validate_confirmed_rows)
from core.ground_evidence import selection_id
from review_ground_regions import prepare_region_review
from test_gli01_capture_input import write_export
from level_capture_nominal import level_capture


class GroundRegionReviewTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.src=self.root/'source';write_export(self.src,counts=(9,9,9,9))
        self.npz=self.root/'source.npz';prepare_npz(str(self.src),'innolidar','m',str(self.npz))
        self.manifest,_=load_adapted(self.npz);self.model=build_nominal_model(26,1.1,'innolidar')
        nominal=np.array([[x,y,z] for x,y,z in [(1,-.3,-.23),(1,.0,-.23),(1,.3,-.23),
                           (1.3,-.3,-.23),(1.3,0,-.23),(1.3,.3,-.23),
                           (1.1,-.1,.8),(1.2,0,1.0),(1.1,.2,1.2)]],dtype=float)
        self.points=np.tile(inverse_nominal(nominal,self.model,'ground_nominal'),(4,1))
        self.plan={'kind':'ground_region_review_plan','schema':1,'plan_id':'',
                   'binding':review_binding(self.manifest,self.model),'cell_m':.25,
                   'regions':[dict(region_id='r%d'%i,role='fit' if i==0 else 'validation',frame_group=gid,
                                   x_min_m=.8,x_max_m=1.5,y_min_m=-.4,y_max_m=.4,description='synthetic physical scene footprint')
                              for i,gid in enumerate(self.manifest['frame_groups'])]}
        self.sign()

    def tearDown(self):self.tmp.cleanup()

    def sign(self):self.plan['plan_id']=plan_id(self.plan)

    def observe(self):return observe_review_regions(self.points,self.manifest,self.model,self.plan)

    def test_all_heights_source_members_mapping_R02_R03(self):
        obs,rows=self.observe()
        self.assertEqual(len(rows),36)
        self.assertEqual(obs['regions'][0]['source_rows'],list(range(9)))
        self.assertEqual(rows[9]['pooled_row'],9);self.assertEqual(rows[9]['source_row'],0)
        self.assertEqual(rows[9]['ordinal'],1);self.assertEqual(rows[9]['seq'],1979001)
        self.assertGreater(rows[8]['nominal_xyz_m'][2],1)
        self.assertEqual(obs['regions'][0]['ground_identity'],'unknown')
        self.assertEqual(obs['membership_gate'],'PASS_source_membership_only_not_ground_identity')
        self.assertFalse(obs['candidate_eligible'])

    def test_plan_types_foreign_alias_same_frame_Z_residual_Q01_Q02_Q03(self):
        original=copy.deepcopy(self.plan)
        changes=[lambda p:p.update(schema=True),lambda p:p.update(cell_m=float('nan')),
                 lambda p:p.update(cell_m=1e-320),
                 lambda p:p['binding'].update(bin_sha256='ab'*32),
                 lambda p:p['binding'].update(model_id='foreign'),
                 lambda p:p['binding'].update(window_bag_time_sec=[0.,1.]),
                 lambda p:p['regions'][1].update(region_id='r0'),
                 lambda p:p['regions'][1].update(frame_group=p['regions'][0]['frame_group']),
                 lambda p:p['regions'][1].update(z_min_m=-.3),
                 lambda p:p['regions'][1].update(selection_method='FIT_residual_band'),
                 lambda p:p['regions'][0].update(x_min_m=True),
                 lambda p:p['regions'][0].update(x_max_m=.5),
                 lambda p:p['regions'][0].update(role='validation')]
        for change in changes:
            self.plan=copy.deepcopy(original);change(self.plan)
            if np.isnan(self.plan['cell_m']):
                with self.assertRaises(ValueError):self.sign()
                continue
            self.sign()
            with self.assertRaises(ValueError):self.observe()
        self.plan=copy.deepcopy(original);self.plan['regions'][0]['description']='caller changed'
        with self.assertRaises(ValueError):self.observe()

    def test_zero_invalid_empty_region_Q04(self):
        self.points[0]=[0,0,0];self.points[1]=[float('inf'),0,0]
        obs,rows=self.observe();self.assertEqual(len(obs['regions'][0]['source_rows']),7)
        self.plan['regions'][0]['x_min_m']=100;self.plan['regions'][0]['x_max_m']=101;self.sign()
        obs,rows=self.observe();self.assertEqual(obs['regions'][0]['observation']['count'],0)
        self.assertIsNone(obs['regions'][0]['observation']['z_stats']);self.assertEqual(obs['membership_gate'],'NOT_RUN_empty_regions')

    def test_legacy_clean_plane_offset_tilt_and_degenerate_R04(self):
        # Only first 6 points form known plane z=-.23. Keep table rows separate;
        # fixed explicit selector has no relation to a fitted residual gate.
        gid=next(iter(self.manifest['frame_groups']))
        report=legacy_box_diagnostics(self.points,self.manifest,self.model,[('fixture',{'frame_group':gid,'indices':list(range(6))})])[0]
        plane=report['pca_scene_plane'];self.assertAlmostEqual(plane['offset_nominal_m'],.23,places=10)
        self.assertLess(plane['tilt_to_nominal_z_deg'],1e-5);self.assertFalse(report['physical_ground_error'])
        empty=legacy_box_diagnostics(self.points,self.manifest,self.model,[('empty',{'frame_group':gid,'indices':[]})])[0]
        self.assertIsNone(empty['pca_scene_plane']);self.assertIsNotNone(empty['pca_reason'])
        line=self.points.copy();line[:3]=[[1,0,0],[2,0,0],[3,0,0]]
        report=legacy_box_diagnostics(line,self.manifest,self.model,[('line',{'frame_group':gid,'indices':[0,1,2]})])[0]
        self.assertIsNone(report['pca_scene_plane'])

    def test_legacy_known_tilt_does_not_modify_nominal_model_Q04(self):
        original=copy.deepcopy(self.model)
        nominal=np.array([[x,y,.02*x-.03*y-.23] for x in (1,1.3,1.6) for y in (-.3,0,.3)])
        source=self.points.copy();source[:9]=inverse_nominal(nominal,self.model,'ground_nominal')
        gid=next(iter(self.manifest['frame_groups']))
        report=legacy_box_diagnostics(source,self.manifest,self.model,[('sloped',{'frame_group':gid,'indices':list(range(9))})])[0]
        plane=report['pca_scene_plane'];expected=np.array([-.02,.03,1]);expected/=np.linalg.norm(expected)
        np.testing.assert_allclose(plane['normal_nominal'],expected,atol=1e-12)
        self.assertEqual(original,self.model);self.assertFalse(report['physical_ground_error'])

    def confirmed(self,obs):
        regions=[]
        for r in obs['regions']:
            regions.append({'region_id':r['region_id'],'frame_group':r['frame_group'],
                'indices':r['source_rows'][:6],'source_sha256':obs['binding']['bin_sha256'],
                'spatial_description':'fixture scene landmarks, independently labeled',
                'selection_method':'independent_manual_source_rows',
                'confirmation':{'status':'user_confirmed','person':'synthetic person','time':'2026-10-04T18:00:00+08:00',
                    'basis':'independent synthetic scene identity','evidence_refs':['fixture'],'landmarks':['known floor vs tabletop edge']}})
        s={'selection_id':'','version':1,'binding':obs['binding'],'fit':regions[0],'validation':regions[1:]};s['selection_id']=selection_id(s);return s

    def test_human_gate_partial_invalid_rows_and_residual_method_Q05(self):
        obs,_=self.observe();s=self.confirmed(obs)
        ready=validate_confirmed_rows(s,obs,self.points,self.manifest,{'fixture':{'path':'fixture','sha256':'ab'*32}},self.model,self.plan)
        self.assertFalse(ready['physical_verified']);self.assertFalse(ready['candidate_eligible'])
        original=copy.deepcopy(s)
        for change in [lambda s:s['fit']['confirmation'].update(status='unknown'),
                       lambda s:s['fit']['confirmation'].update(person=None),
                       lambda s:s['fit']['confirmation'].update(landmarks=[]),
                       lambda s:s['fit'].update(indices=[100]),
                       lambda s:s['validation'][0].update(indices=[0]),
                       lambda s:s['validation'][0].update(indices=[9,9]),
                       lambda s:s['validation'][0].update(selection_method='fit_residual_band')]:
            s=copy.deepcopy(original);change(s);s['selection_id']=selection_id(s)
            with self.assertRaises(ValueError):validate_confirmed_rows(s,obs,self.points,self.manifest,{'fixture':{}},self.model,self.plan)

    def test_caller_modified_observations_cannot_enlarge_human_offer_Q02_Q05(self):
        obs,_=self.observe();selection=self.confirmed(obs)
        obs['regions'][0]['source_rows'].append(100)
        selection['fit']['indices']=[100];selection['selection_id']=selection_id(selection)
        with self.assertRaises(ValueError):
            validate_confirmed_rows(selection,obs,self.points,self.manifest,{'fixture':{}},self.model,self.plan)

    def test_cli_pending_foreign_identity_and_output_protection_R01_R06(self):
        nominal_dir=self.root/'docs/human_fall/evidence/2026-10-04_gl_n01_r1';nominal_dir.mkdir(parents=True)
        level_capture(self.npz,nominal_dir/'run',26,1.1,'innolidar',self.root)
        m,_=load_adapted(self.npz);plan=copy.deepcopy(self.plan);plan['binding']=review_binding(m,self.model)
        # Export fixture points differ from observation-only geometry; broad XY.
        for r in plan['regions']:r.update(x_min_m=-200,x_max_m=200,y_min_m=-200,y_max_m=200)
        plan['plan_id']=plan_id(plan);pp=self.root/'plan.json';pp.write_text(json.dumps(plan))
        draft={'kind':'gli02_capture_selection_draft','schema':1,
               'source':{'meta_sha256':m['source']['meta_sha256'],'bin_sha256':m['source']['bin_sha256'],
                         'manifest_points_sha256':m['points']['sha256'],'frame':'innolidar','units':'m'},
               'fit_region':{'frame_group':plan['regions'][0]['frame_group'],'indices':[0,1,2]},
               'validation_regions':[{'region_id':r['region_id'],'frame_group':r['frame_group'],
                                      'indices':list(range(i*9,i*9+3))} for i,r in enumerate(plan['regions'][1:],1)]}
        dp=self.root/'draft.json';dp.write_text(json.dumps(draft));base=self.root/'docs/human_fall/evidence/2026-10-04_gl_b01_r1';base.mkdir(parents=True)
        result=prepare_region_review(self.npz,nominal_dir/'run',dp,pp,base/'a',self.root)
        self.assertEqual(result['status'],'pending_ground_selection')
        for dest in [base/'a',self.root/'captures/bad',base]:
            with self.assertRaises(ValueError):prepare_region_review(self.npz,nominal_dir/'run',dp,pp,dest,self.root)
        draft['source']['bin_sha256']='00'*32;dp.write_text(json.dumps(draft))
        with self.assertRaises(ValueError):prepare_region_review(self.npz,nominal_dir/'run',dp,pp,base/'foreign',self.root)


if __name__=='__main__':unittest.main()
