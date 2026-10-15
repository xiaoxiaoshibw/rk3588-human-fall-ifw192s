"""One evaluator for source-index foreground arms and existing runtime selector."""
import argparse
import json
import sys
from pathlib import Path
import numpy as np
import yaml
from close_data_bg import ROOT,PS,read,source,dump,module


def main(out):
    core=module('pointset_geometry_ab',PS/'core.py')
    cfg=yaml.safe_load((PS/'config.yaml').read_text(encoding='utf8'))
    all_results=[];summaries=[]
    for sid in ['cap_20261013_094333','cap_20261010_180557']:
        manifest=read(out/(sid+'_ab_manifest.json'));meta,raw,hashes=source(sid)
        assert manifest['source']['meta_sha256']==hashes['meta'] and manifest['source']['bin_sha256']==hashes['points']
        total={arm:{'reviewed_person_denominator':0,'fg_person_kept':0,'cluster_person_kept':0,'selected_person_kept':0,
                    'foreground_points':0,'selected_points':0,'labeled_nonhuman':0,'selected_unknown':0,
                    'fragmented_person_frames':0,'candidate_frames':0,'low_z_reviewed_denominator':0,'low_z_reviewed_kept':0,
                    'prototype_target_proxy_denominator':0,'prototype_target_proxy_kept':0}
               for arm in ['A_P','B_FROZEN','C_V2_DIAGNOSTIC']}
        real=read(ROOT/'docs/human_fall/evidence/2026-10-13_hf_real_04_r1/process.json') if sid.endswith('094333') else None
        real_meta=read(ROOT/'docs/human_fall/evidence/2026-10-13_hf_real_04_r1'/ (sid+'_foreground.json')) if real else None
        real_rows=np.fromfile(ROOT/'docs/human_fall/evidence/2026-10-13_hf_real_04_r1'/(sid+'_source_rows.bin'),dtype='<u4') if real else None
        with (out/(sid+'_ab_indices.jsonl')).open(encoding='utf8') as lines:
            for line in lines:
                row=json.loads(line);fi=row['frame'];f=meta['frames'][fi]
                p=raw[f['offset_points']:f['offset_points']+f['count_points']].astype('f8')@np.array(manifest['R']).T+manifest['t']
                refrow=read(PS/'output'/sid/f'{fi:04d}.json') if not real else None
                refs=refrow['reference'] if refrow else []
                humans=set(i for r in refs for i in r['source_indices'])
                # Known FURNITURE IDs from source-bound old GT, decoded after inference.
                furniture=set()
                if not real:
                    gtpath=ROOT/'pc_apps/human_replay/gt_store'/sid/'GT_V1.json'
                    if fi==0:gt=read(gtpath)
                    for oid in gt.get('frames_objects',{}).get(str(fi),[]):
                        o=gt['objects'][oid]
                        if o['class_name']=='FURNITURE':furniture.update(core.decode_indices(o['raw_point_indices']).tolist())
                proxy=set()
                if real:
                    rm=real_meta['frames'][fi]
                    proxy=set(real_rows[rm['offset']:rm['offset']+rm['count']][real['rows'][fi]['source_fg_indices']].tolist())
                for arm,ids in row['arms'].items():
                    assert len(ids)==len(set(ids)) and all(type(i) is int and 0<=i<f['count_points'] for i in ids)
                    ids=np.array(ids,dtype='i8');groups,_=core.cluster(p[ids],cfg)
                    # GT-free largest cluster diagnostic; do not call this production target selector.
                    selected=ids[max(groups,key=len)] if groups else np.empty(0,dtype='i8')
                    kept=set(ids.tolist());chosen=set(selected.tolist());known=humans|furniture
                    counts=total[arm];counts['reviewed_person_denominator']+=len(humans);counts['fg_person_kept']+=len(humans&kept)
                    hits=[len(humans&set(ids[g].tolist())) for g in groups]
                    counts['cluster_person_kept']+=max(hits,default=0);counts['selected_person_kept']+=len(humans&chosen)
                    counts['foreground_points']+=len(ids);counts['selected_points']+=len(selected)
                    counts['labeled_nonhuman']+=len(furniture&chosen);counts['selected_unknown']+=len(chosen-known)
                    counts['fragmented_person_frames']+=int(sum(h>0 for h in hits)>1);counts['candidate_frames']+=bool(groups)
                    low={i for i in humans if p[i,2]<.1};counts['low_z_reviewed_denominator']+=len(low);counts['low_z_reviewed_kept']+=len(low&kept)
                    counts['prototype_target_proxy_denominator']+=len(proxy);counts['prototype_target_proxy_kept']+=len(proxy&kept)
                    all_results.append({'sid':sid,'frame':fi,'t':row['t'],'arm':arm,'reviewed_human_points':len(humans),
                        'fg_human_kept':len(humans&kept),'selected_human_kept':len(humans&chosen),'selected_points':len(selected),
                        'known_nonhuman':len(furniture&chosen),'unknown':len(chosen-known),'oracle_best_hits':max(hits,default=0),
                        'fragments':sum(h>0 for h in hits),'candidates':len(groups),'identity_takeover':'UNKNOWN_PARTIAL_GT',
                        'complete_precision':None,'body_parts':'UNKNOWN','proxy_target':len(proxy),'proxy_kept':len(proxy&kept)})
        summaries.append({'sid':sid,'frames':len(meta['frames']),'arms':total,'status':'ISOLATED_DIAGNOSTIC_NOT_OFFLINE_QUALIFIED',
             'selector':'largest XYZ cluster, same cfg all arms; separate from existing page RF/PointNet selector',
             'human_confirmed':None,'events':None,'GT':'HF_REAL_UNREVIEWED_PROXY_ONLY' if real else 'BOUND_PARTIAL_PERSON_LABELS'})
        print('scored',sid,flush=True)
    # Actual existing page default RF selector and alternative PointNet; never pick with GT.
    runtime=[]
    catalog=read(PS/'output/catalog.json')
    for s in catalog['sessions']:
        totals={model:{'denominator':0,'hits':0,'oracle_hits':0,'selected_points':0,'known_furniture':0,'unknown':0} for model in ['rf_xyz_prob','pointnet_prob']}
        for fi in range(s['frame_count']):
            row=read(PS/'output'/s['session_id']/f'{fi:04d}.json');groups=row['full_3d']
            persons=row['metrics']['full_3d']['persons']
            human=set(i for r in row['reference'] for i in r['source_indices'])
            for model,counts in totals.items():
                chosen=max(groups,key=lambda c:c.get(model,0)*(c['independence']['score_0_100']/100)*np.log1p(c['point_count'])) if groups else None
                if not persons:continue
                counts['denominator']+=sum(p['reference_count'] for p in persons);counts['oracle_hits']+=sum(p['intersection'] for p in persons)
                if chosen:
                    counts['hits']+=len(human&set(chosen['source_indices']));counts['selected_points']+=chosen['point_count']
                    overlaps=chosen.get('reference_overlap',[]);counts['known_furniture']+=sum(o['intersection'] for o in overlaps if o['class_name']=='FURNITURE')
                    counts['unknown']+=chosen['point_count']-sum(o['intersection'] for o in overlaps)
        runtime.append({'sid':s['session_id'],'selectors':totals})
    dump(out/'BACKGROUND_METRICS.json',{'sessions':summaries,'runtime':runtime,'complete_point_precision':'BLOCKED',
         'P_equivalence':'NOT_IDENTICAL_TO_NONCAUSAL_FULL_RECORDING_DEFAULT; causal previous10 context explicit',
         'thin_ground_segmentation':'NOT_RUN_SEPARATE_FROM_LEVELING_AND_IDENTITY','body_parts':'UNKNOWN_NO_REVIEWED_PART_LABELS'})
    with (out/'background_frame_results.jsonl').open('x',encoding='utf8') as f:
        for row in all_results:f.write(json.dumps(row)+'\n')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',required=True);args=p.parse_args();main(Path(args.out).resolve())
