"""Real, same-source combined result -> native copies and causal hints."""
import copy
import json
from pathlib import Path
import sys
import unittest

import test_integration as fixtures

ROOT=fixtures.ROOT
FLOW=ROOT/'docs/evidence/2026-10-26_unified_flow'


class UnifiedChecks(unittest.TestCase):
    setUp=fixtures.TestApp.setUp
    run_service=fixtures.TestApp.run_service

    def test_source_cadence_native_playback_crosses_real_low_posture_segment(self):
        if not fixtures.ANALYSIS.parent.name.startswith('run780'):self.skipTest('requires combined real 780 fixture')
        report=self.run_service(['--smoke','--smoke-playback-ms','10000','--frame','640'])
        rows=[r for r in report['log'] if r['eventType']=='published']
        indices=[r['info']['frameIndex'] for r in rows]
        self.assertEqual(indices,list(range(640,indices[-1]+1)))
        self.assertGreaterEqual(indices[-1],730)
        active=[r['info']['frameIndex'] for r in rows if r['info']['result']['groundAlert']['active']]
        self.assertEqual(active,list(range(689,708)))
        gaps=[b['atMs']-a['atMs'] for a,b in zip(rows[2:],rows[3:])]
        self.assertLess(max(gaps),300)

    def test_native_body_counts_and_causal_alert_on_real_780(self):
        analysis=Path(fixtures.ANALYSIS)
        if not analysis.parent.name.startswith('run780'):self.skipTest('requires combined real 780 fixture')
        expected=json.loads(analysis.read_text('utf8'))
        row=next(r for r in expected['frames'] if r['frameIndex']==690)
        self.assertTrue(row['groundAlert']['active'])
        report=self.run_service(['--smoke','--smoke-depth','--smoke-frame','690','--screenshot',str(self.out/'window.png')])
        published=[r for r in report['log'] if r['eventType']=='published']
        last=published[-1]['info']
        self.assertEqual(last['frameIndex'],690)
        self.assertEqual(last['result']['groundAlert'],row['groundAlert'])
        self.assertEqual(last['analysisIntervals'],expected['intervals'])
        acks=[json.loads(r['command']) for r in report['log'] if r['eventType']=='command'
              and json.loads(r['command'])['op']=='ack']
        self.assertEqual(len(acks),len(published))
        self.assertEqual(acks[-1]['targetSha256'],last['targetSha256'])
        self.assertEqual(acks[-1]['depthSha256'],last['depth']['previewSha256'])
        self.assertEqual(report['jointMutationRequests'],0)
        self.assertEqual(report['directBoardCalls'],0)

    def test_native_3d_head_torso_200_matches_precomputed_source(self):
        if not fixtures.ANALYSIS.parent.name.startswith('run386'):self.skipTest('requires combined real 386 fixture')
        report=self.run_service(['--smoke','--smoke-frame','200','--screenshot',str(self.out/'window.png')])
        row=[r['info'] for r in report['log'] if r['eventType']=='published'][-1]
        self.assertEqual(row['frameIndex'],200)
        counts={p['part']:p['pointCount'] for p in row['result']['bodyCandidates']['parts']}
        self.assertEqual((counts['head'],counts['torso']),(137,1045))
        self.assertFalse(row['result']['groundAlert']['active'])

    def test_native_rejects_body_points_outside_current_target(self):
        original=json.loads(fixtures.ANALYSIS.read_text('utf8'))
        if not original.get('bodyAlgorithm'):self.skipTest('requires combined fixture')
        for row in original['frames']:row.pop('depth',None)
        row=next(r for r in original['frames'] if any(p['sourceRows'] for p in r['bodyCandidates']['parts']))
        part=next(p for p in row['bodyCandidates']['parts'] if p['sourceRows'])
        part['sourceRows'][0]=500000
        sys.path.insert(0,str(ROOT/'pc_apps/range_fall'))
        from analysis import content_sha
        original['contentSha256']=content_sha({k:v for k,v in original.items() if k!='contentSha256'})
        path=self.out/'bad.json';path.write_text(json.dumps(original,separators=(',',':')),'utf8')
        self.run_service(['--check'],analysis=path,expect=2)
        self.assertIn('Body support/target mismatch',(self.out/'stderr.txt').read_text('utf8'))


if __name__=='__main__':unittest.main()
