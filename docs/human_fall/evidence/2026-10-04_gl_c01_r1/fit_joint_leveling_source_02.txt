#!/usr/bin/env python3
"""Fit one frozen source-frame plane and report joint pose with full holdouts."""
import argparse
import json
from pathlib import Path
import sys

import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from core.capture_input import load_adapted,sha256_file
from core.ground_evidence import read_json,require
from core.joint_leveling import solve_joint_leveling


def fit_capture_joint(npz,selection_path,output,repo_root):
    root=Path(repo_root).resolve();target=Path(output).absolute()
    allowed=root/'docs/human_fall/evidence/2026-10-04_gl_c01_r1'
    require(target.resolve()==target and allowed in target.parents and not target.exists()
            and target.parent.is_dir(),'output must be new child directory inside this work item')
    for p in [target]+list(target.parents):require(not p.is_symlink(),'output aliases forbidden')
    for p in [Path(npz),Path(selection_path)]:
        require(target!=p.resolve() and target not in p.resolve().parents,'output contains input')
    before=sha256_file(npz);selection,selection_sha=read_json(selection_path)
    manifest,points=load_adapted(npz)
    model,report=solve_joint_leveling(points,manifest,selection)
    all_rows=selection['fit']['indices']+sum([v['indices'] for v in selection['validation']],[])
    rr=np.asarray(all_rows,dtype=np.int64);from core.calibration import apply_transform
    mapped=apply_transform(points[rr],model)
    require(sha256_file(npz)==before and sha256_file(selection_path)==selection_sha,'inputs changed during solve')
    for name in ('meta','bin'):
        s=manifest['source'];require(sha256_file(s[name+'_path'])==s[name+'_sha256'],'actual source changed during solve')
    record={'kind':'joint_capture_input_record','schema':1,'npz_path':str(Path(npz).resolve()),'npz_sha256':before,
            'selection_path':str(Path(selection_path).resolve()),'selection_sha256':selection_sha,
            'source':manifest['source'],'frames':manifest['frame_groups'],
            'source_bag_original_chain':'metadata_declared_not_independently_verified_in_this_99_frame_cohort',
            'observed_plane_not_measured_installation':True}
    target.mkdir(exist_ok=False)
    for name,obj in [('joint_estimate.json',model),('quality_report.json',report),('frozen_selection.json',selection),('input_record.json',record)]:
        with (target/name).open('x',encoding='utf8') as f:json.dump(obj,f,ensure_ascii=False,indent=2,allow_nan=False)
    with (target/'frozen_selected_points.npz').open('xb') as f:
        np.savez(f,source_rows=rr,source_points=points[rr],estimated_points=mapped,
                 model_json=np.array(json.dumps(model)))
    return {'model_id':model['model_id'],'pitch_deg':model['pitch_deg'],'roll_deg':model['roll_deg'],
            'tz_m':model['tz_m'],'validation_quality':report['validation_quality'],
            'source_counts':{r['region_id']:r['same_FIT_plane_full_point_stats']['count'] for r in report['regions']},
            'candidate_eligible':False,'physical_verified':False}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for flag in ('input','selection','output'):p.add_argument('--'+flag,required=True)
    args=p.parse_args()
    try:
        result=fit_capture_joint(args.input,args.selection,args.output,Path(__file__).resolve().parents[3])
        print(json.dumps(result));return 0
    except (ValueError,OSError,KeyError,TypeError,OverflowError) as exc:
        print('joint leveling refused: '+str(exc),file=sys.stderr);return 2


if __name__=='__main__':sys.exit(main())
