"""Evaluation only. GT is loaded after JS inference and cannot select clusters."""
import gzip,json,sys
from collections import defaultdict
from pathlib import Path
import numpy as np
import yaml
ROOT=Path(__file__).resolve().parents[2]
PS=ROOT/'sidequests/human_fusion_lab_next/pointset/r01'
sys.path.insert(0,str(PS))
from actions import read,sha,load,dump
from core import cluster,decode_indices,valid_raw
E=ROOT/'docs/human_fall/evidence/2026-10-14_hf_mainline_points_r1'


def main(js_dir):
    out=E/js_dir
    cfg=yaml.safe_load((PS/'config.yaml').read_text(encoding='utf8'))
    summaries=[];frames=[];source_count=0
    preservation=read(E/'BASELINE_BEFORE.json')['files']
    for sid in ['cap_20261013_094333','cap_20261010_180557']:
        manifest=read(out/sid/'MANIFEST.json');meta,raw,hashes=load(sid)
        assert hashes=={'meta':manifest['source']['meta_sha256'],'points':manifest['source']['bin_sha256']}
        gtpath=ROOT/'pc_apps/human_replay/gt_store'/sid/'GT_V1.json'
        gt=None
        if sid.endswith('180557'):
            assert sha(gtpath)==preservation[gtpath.relative_to(ROOT).as_posix()]
            gt=read(gtpath);assert gt['session_id']==sid and gt['session_sha256']==hashes and gt['review_status']=='reviewed'
        totals=defaultdict(lambda:defaultdict(int));labeled_frames=0
        with (out/sid/'members.jsonl').open(encoding='utf8') as f:
            for line in f:
                row=json.loads(line);fi=row['frame'];source_frame=meta['frames'][fi]
                q=raw[source_frame['offset_points']:source_frame['offset_points']+source_frame['count_points']].astype('f8')
                p=q@np.array(manifest['R']).T+manifest['t'];human=set();furniture=set()
                if gt:
                    reference=read(PS/'output'/sid/f'{fi:04d}.json')['reference']
                    human=set(i for r in reference for i in r['source_indices'])
                    valid_ids=np.flatnonzero(valid_raw(q))
                    for oid in gt.get('frames_objects',{}).get(str(fi),[]):
                        o=gt['objects'][oid]
                        if o['class_name']=='FURNITURE':furniture.update(valid_ids[decode_indices(o['raw_point_indices'])].tolist())
                    if human:labeled_frames+=1
                low={i for i in human if p[i,2]<.1}
                selection_arrays={}
                for arm,ids0 in row['arms'].items():
                    ids=np.array(ids0,dtype=int);assert len(ids)==len(np.unique(ids)) and np.all(ids<len(q))
                    groups,_=cluster(p[ids],cfg);selected=ids[max(groups,key=len)] if groups else np.empty(0,dtype=int)
                    kept=set(ids.tolist());chosen=set(selected.tolist());known=human|furniture
                    selection_arrays[arm]=selected.astype('u4')
                    stage=np.frombuffer(gzip.decompress((out/sid/f'{fi:04d}_{arm}.stage.gz').read_bytes()),dtype='u1')
                    assert len(stage)==len(q) and np.all((stage>=1)&(stage<=10))
                    c=totals[arm];c['frames']+=1;c['human_denominator']+=len(human);c['fg_human']+=len(human&kept);c['selected_human']+=len(human&chosen)
                    c['selected']+=len(selected);c['fg']+=len(ids);c['unknown']+=len(chosen-known);c['furniture_denominator']+=len(furniture);c['selected_furniture']+=len(furniture&chosen)
                    c['low_denominator']+=len(low);c['low_fg_human']+=len(low&kept);c['native_cleanup_removed']+=row['native'][arm]['cleanup'];c['native_clusters']+=row['native'][arm]['clusters']
                    frames.append({'sid':sid,'fi':fi,'arm':arm,'human':len(human),'fg_human':len(human&kept),'selected_human':len(human&chosen),
                                   'selected':len(selected),'unknown':len(chosen-known),'furniture':len(furniture&chosen),'low_fg_human':len(low&kept)})
                # Separate from native XY/cleanup stages: frozen AB scorer selects largest XYZ cluster.
                selection_path=out/sid/f'{fi:04d}_xyz_selected.npz'
                if selection_path.exists():raise ValueError('Exclusive selected archive required')
                np.savez_compressed(selection_path,**selection_arrays)
                source_count+=len(q)
        if gt:
            assert labeled_frames==53 and totals['C_V2_DIAGNOSTIC']['human_denominator']==57045
            assert totals['C_V2_DIAGNOSTIC']['fg_human']==54069 and totals['C_V2_DIAGNOSTIC']['selected_human']==54063
        summaries.append({'sid':sid,'labeled_frames':labeled_frames,'arms':dict(totals),'furniture_status':'NOT_EVALUATED' if not totals['C_V2_DIAGNOSTIC']['furniture_denominator'] else 'SCORED',
                          'complete_precision':None,'identity':'PARTIAL_BOUND_LABELS' if gt else 'PROXY_ONLY_NO_HUMAN_DENOMINATOR'})
        print('JS SCORED',sid,labeled_frames,flush=True)
    dump(E/'JS_METRICS.json',{'sessions':summaries,'js_dir':js_dir,'ledger_source_records':source_count,'baseline_comparison':'fixed C_V2_DIAGNOSTIC; reproduced exactly, JS default unchanged',
         'separate_ranges':'Python .2..15 strict; JS .35..25 inclusive raw range then transform Float32',
         'selector':'GT-free largest XYZ cluster, frozen config; native XY cleanup not part of AB denominator',
         'GT_SHA':sha(ROOT/'pc_apps/human_replay/gt_store/cap_20261010_180557/GT_V1.json')})
    with (E/'JS_FRAME_METRICS.jsonl').open('x',encoding='utf8') as f:
        for row in frames:f.write(json.dumps(row)+'\n')


if __name__=='__main__':main(sys.argv[1])
