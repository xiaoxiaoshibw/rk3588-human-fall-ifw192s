"""Read-only inputs, machine-only evidence for the automatic target development path."""
import argparse
from collections import Counter
import json
from pathlib import Path

import numpy as np

import run as P
from target_points import components
from coordinates import GroundCoordinates


def load(path):
    return [json.loads(line) for line in Path(path).read_text(encoding='utf8').splitlines()]


def check(records, src, coordinates):
    for record in records:
        frame=src.frame(record['fi']);rows=np.asarray(record['target_rows'],dtype=np.int64)
        assert len(set(rows.tolist()))==len(rows)
        assert set(rows)<=set(record['foreground_rows'])
        assert np.all(rows>=frame['offset']) and np.all(rows<frame['offset']+len(frame['xyz']))
        points=frame['xyz'][rows-frame['offset']]
        bound=[row for c in record['clusters'] for row in c['source_rows']]
        assert sorted(bound)==sorted(record['foreground_rows']) and len(bound)==len(set(bound))
        assert record['binding']['source_sha256']==src.binding
        assert record['binding']['ground_version']==coordinates.artifact['transform_id']
        observed=bool(len(rows))
        assert observed==(record['track']['status']=='locked' and not record['track']['predicted'])
        assert record['acquisition']['semantic']=='unknown'
        assert not record['track']['requires_reselection']
        assert not record['fall']['confirmed_enabled']
        if observed:
            assert record['candidate']['point_count']==len(rows)
            assert record['bbox_raw']==dict(min=points.min(0).tolist(),max=points.max(0).tolist())
            assert record['center_raw']==np.median(points,axis=0).tolist()
            assert abs(record['candidate']['height_m']['median']-float(np.median(coordinates.points(points)[:,2])))<1e-12
        else:
            assert record['candidate'] is None and record['bbox_raw'] is None
        for node in record['nodes'].values():
            assert set(node['support_rows'])<=set(rows)
            if node['valid']:
                p=frame['xyz'][np.asarray(node['support_rows'])-frame['offset']]
                assert np.array_equal(np.median(p,axis=0),node['xyz'])


class Prefix:
    def __init__(self,src,count):
        self.src=src;self.frames=src.frames[:count];self.times=src.times[:count]
        self.sid=src.sid;self.binding=src.binding
    def frame(self,fi):
        assert fi<len(self.frames),'future frame access'
        return self.src.frame(fi)


def verify(evidence,run_dir,repeat_dir,foreground_dir):
    evidence=Path(evidence).resolve()
    if not evidence.is_relative_to((P.ROOT/'docs/evidence').resolve()):raise ValueError('evidence root required')
    meta=json.loads((run_dir/'RUN.json').read_text(encoding='utf8'))
    src=P.source(meta['session']);coords=GroundCoordinates(meta['ground']['path'],src.sid,src.binding)
    result={}
    try:
        for variant in ('orientation','partition'):
            rows=load(run_dir/(variant+'_frames.jsonl'))
            again=load(repeat_dir/(variant+'_frames.jsonl'))
            assert rows==again
            check(rows,src,coords)
            fg=load(foreground_dir/(variant+'_frames.jsonl'));check(fg,src,coords)
            prefix,_=P.process(Prefix(src,120),None,variant=='partition',meta['ground']['path'],
                settings=meta['settings'],empty_prefix_frames=meta['empty_prefix_frames'],
                region_contract=meta.get('region_contract','legacy_raw_roi'),
                human_entry_gate=meta.get('human_entry_gate',False))
            assert prefix==rows[:120]
            result[variant]=dict(repeated_frames=len(rows),membership_checked=len(rows)+len(fg),
                                  future_invariance_frames=len(prefix))
        old=load(P.ROOT/'docs/evidence/2026-10-18_hfus_project_dev/run_04/partition_frames.jsonl')
        comparisons=[]
        with np.load(P.S07/'FOREGROUND_LEDGER.npz',allow_pickle=False) as ledger:
            for i,(before,new,raw_new) in enumerate(zip(old,fg,rows)):
                frame=src.frame(i);sl=slice(ledger['indptr'][i],ledger['indptr'][i+1])
                old_rows=ledger['global_rows'][sl][ledger['keep'][sl]]
                p=frame['xyz'][old_rows-frame['offset']]
                _,groups=components(p,old_rows,coords)
                largest=max(groups,key=lambda c:c['point_count'])['source_rows'] if groups else []
                body=frame['xyz'][np.asarray(largest,dtype=np.int64)-frame['offset']]
                if len(p)<30 or len(body)<30:body=p
                box=None if not len(body) else dict(min=body.min(0).tolist(),max=body.max(0).tolist())
                comparisons.append(dict(fi=i,old_count=before['candidate_rows'],foreground_target_count=new['candidate_rows'],
                    raw_target_count=raw_new['candidate_rows'],old_center=None if not len(p) else np.median(p,0).tolist(),
                    foreground_center=new['center_raw'],raw_center=raw_new['center_raw'],
                    old_display_box=box,foreground_box=new['bbox_raw'],raw_box=raw_new['bbox_raw'],
                    old_track=before['track'],foreground_track=new['track'],raw_track=raw_new['track'],
                    old_pose=before['fall']['status'],foreground_pose=new['fall']['status'],raw_pose=raw_new['fall']['status'],
                    foreground_acquisition=new['acquisition'],raw_acquisition=raw_new['acquisition'],
                    old_region_count=before['valid_nodes'],foreground_region_count=new['valid_nodes'],raw_region_count=raw_new['valid_nodes']))
        P.put(evidence/'RUN04_FRAME_COMPARE.jsonl',''.join(json.dumps(r,allow_nan=False)+'\n' for r in comparisons))
        result['run04_comparison']=dict(frames=len(comparisons),
            foreground_count_changes=sum(r['old_count']!=r['foreground_target_count'] for r in comparisons),
            raw_count_changes=sum(r['old_count']!=r['raw_target_count'] for r in comparisons),
            foreground_pose_changes=sum(r['old_pose']!=r['foreground_pose'] for r in comparisons),
            raw_pose_changes=sum(r['old_pose']!=r['raw_pose'] for r in comparisons),
            raw_region_reasons=dict(Counter(r['reason'] for r in rows)),
            interpretation=['foreground: unique component membership replaces all foreground; 0.6s acquisition delay',
                            'raw: full sensor search, causal voxel background and configured '+meta['settings'].get('cluster_mode','horizontal')+' clustering replace historical ROI/nearest reference',
                            'region module refuses targets outside its development domain; target tracking continues',
                            'software changes only; semantic performance UNKNOWN'])
        intervals=np.diff(src.times)
        result['source_interval_s']=dict(p50=float(np.median(intervals)),p95=float(np.quantile(intervals,.95)),max=float(max(intervals)))
        inventory=[]
        for folder in sorted((P.ROOT/'data/sessions').iterdir()):
            path=folder/'meta.json'
            if not path.is_file():continue
            try:
                m=json.loads(path.read_text(encoding='utf8'))
                inventory.append(dict(sid=folder.name,frames=len(m.get('frames',[])),
                    total_points=m.get('total_points'),meta_sha256=P.sha(path),
                    points_bytes=(folder/'points.bin').stat().st_size if (folder/'points.bin').is_file() else None,
                    scene_categories='UNKNOWN; no independent scene/identity labels'))
            except (OSError,ValueError) as exc:inventory.append(dict(sid=folder.name,error=str(exc)))
        P.put(evidence/'SESSION_INVENTORY.json',dict(sessions=inventory,
            missing_verified_real_scenarios=['stationary entry','two competing people','split/merge identity','short occlusion identity','long loss identity','low posture identity'],
            existing_replay='cap_20261018_110029, reused development only; no independent semantic GT'))
        P.put(evidence/'VERIFICATION.json',result)
        print(json.dumps(result,ensure_ascii=True))
    finally:src.close()


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--evidence',type=Path,required=True)
    ap.add_argument('--run',type=Path,required=True);ap.add_argument('--repeat',type=Path,required=True)
    ap.add_argument('--foreground',type=Path,required=True);a=ap.parse_args()
    verify(a.evidence,a.run,a.repeat,a.foreground)
