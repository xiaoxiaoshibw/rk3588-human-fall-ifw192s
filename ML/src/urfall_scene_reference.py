"""Explicit pre-event background/ground bundle for the offline raw-depth path.

Clock and empty-scene declarations are metadata, never physical certification.
No target-frame fitting, cross-clip chronology guessing, or silent fallback.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import sys
import zipfile

import numpy as np

from fall_candidate_runtime import file_sha256

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src/human_fall_detection'))
from core.ground import validate_ground_plane,resolve_settings


def check_ground(plane):
    from urfall_raw_depth import GROUND_SETTINGS
    validate_ground_plane(plane,expected_frame='nominal_cam0')
    expected=resolve_settings(GROUND_SETTINGS)
    if plane['status']!='valid' or plane.get('settings')!=expected:
        raise ValueError('Reference ground status/settings mismatch')
    support=plane['holdout_support']
    if (not isinstance(plane.get('fit_inlier_count'),int) or
            plane['fit_inlier_count']<expected['min_inliers'] or
            number(plane.get('inlier_fraction'))<expected['min_inlier_fraction'] or
            number(support['count'])<expected['min_holdout_points'] or
            number(support['fraction'])<max(expected['min_holdout_support'],expected['min_inlier_fraction']) or
            number(support['rms_m'])>expected['max_holdout_rms_m'] or
            number(plane['normal'][2])<expected['normal_up_min_z']):
        raise ValueError('Reference ground validation criteria failed')
    return plane


def number(value):
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value):
        raise ValueError('Expected finite clock value')
    return float(value)


def check_clock(clock, source_sha, target_sha, last_source_s, first_target_s):
    if (clock.get('schema') != 'recording_clock_pair_v1' or
            clock.get('qualification') != 'metadata_declared' or
            not isinstance(clock.get('clock_id'),str) or not clock['clock_id'] or
            not isinstance(clock.get('installation_id'),str) or not clock['installation_id'] or
            clock.get('source_archive_sha256') != source_sha or
            clock.get('target_archive_sha256') != target_sha or source_sha == target_sha or
            clock.get('empty_source_prefix_declared') is not True):
        raise ValueError('Need distinct recordings, explicit shared clock/setup and empty-prefix declaration')
    uncertainty=number(clock.get('uncertainty_s'))
    if uncertainty < 0:
        raise ValueError('Negative clock uncertainty')
    end=number(clock.get('source_origin_s'))+number(last_source_s)
    start=number(clock.get('target_origin_s'))+number(first_target_s)
    if end+uncertainty >= start-uncertainty:
        raise ValueError('Reference is not strictly before target, including clock uncertainty')
    return dict(source_end_global_s=end,target_start_global_s=start,uncertainty_s=uncertainty,
                qualification='metadata_declared; not physical verification')


def build(source_archive, source_sync, target_archive, target_sync, calibration, clock_path, out,
          prefix_s=.3, ground_start_fraction=.75):
    from urfall_raw_depth import load_pinhole,decode_png,median_reference,read_sync,fit_ground_plane,SETTINGS,GROUND_SETTINGS
    if (number(prefix_s) < 0 or not .5 <= number(ground_start_fraction) < 1.):
        raise ValueError('Invalid reference prefix or ground band')
    camera=load_pinhole(calibration)
    source_match=re.fullmatch(r'(fall|adl)-(\d{2})-cam0-d.zip',source_archive.name)
    target_match=re.fullmatch(r'(fall|adl)-(\d{2})-cam0-d.zip',target_archive.name)
    if not source_match or not target_match:
        raise ValueError('Expected named cam0 raw recordings')
    source_sequence='%s-%s'%source_match.groups()
    target_sequence='%s-%s'%target_match.groups()
    if source_sync.name != source_sequence+'-data.csv' or target_sync.name != target_sequence+'-data.csv':
        raise ValueError('Clock table recording mismatch')
    source_sha,target_sha=file_sha256(source_archive),file_sha256(target_archive)
    clock=json.loads(clock_path.read_text(encoding='utf-8-sig'))
    source_times,target_times=read_sync(source_sync),read_sync(target_sync)
    stride=SETTINGS['stride']; scale=6. if source_match.group(1)=='fall' else 7.
    depths,points,frames=[],[],[]
    with zipfile.ZipFile(source_archive) as archive:
        names=archive.namelist()
        if len(names) != len(set(names)):
            raise ValueError('Duplicate reference archive member')
        members=[]
        for name in names:
            if not name.endswith('.png'):
                continue
            m=re.fullmatch(re.escape(source_sequence)+r'-cam0-d-(\d+)\.png',name.rsplit('/',1)[-1])
            if not m:
                raise ValueError('Reference member recording mismatch')
            members.append((int(m.group(1)),name))
        members.sort()
        if len({f for f,_ in members}) != len(members):
            raise ValueError('Duplicate reference frame')
        for frame,name in members:
            if frame not in source_times:
                raise ValueError('Missing reference timestamp; no interpolation')
            stamp=source_times[frame]
            if stamp > prefix_s:
                break
            raw=archive.read(name)
            xyz,pixels,depth=decode_png(raw,scale,camera,stride)
            valid=(xyz[:,1]>=SETTINGS['depth_min_m'])&(xyz[:,1]<=SETTINGS['depth_max_m'])
            lower=pixels//camera['width']>=int(camera['height']*ground_start_fraction)
            points.append(xyz[valid&lower]);depths.append(depth)
            frames.append(dict(frame=frame,local_stamp_s=stamp,member=name,
                               member_sha256=hashlib.sha256(raw).hexdigest()))
    if not frames:
        raise ValueError('Empty reference prefix')
    chronology=check_clock(clock,source_sha,target_sha,frames[-1]['local_stamp_s'],min(target_times.values()))
    plane=fit_ground_plane(np.concatenate(points),frame='nominal_cam0',settings=GROUND_SETTINGS)
    if plane['status'] != 'valid':
        raise ValueError('Reference ground did not qualify: '+str(plane.get('reason')))
    check_ground(plane)
    out.mkdir(parents=True,exist_ok=False)
    np.savez_compressed(out/'reference.npz',depth_m=median_reference(depths))
    (out/'clock.json').write_bytes(clock_path.read_bytes())
    (out/'SOURCE_FRAMES.json').write_text(json.dumps(frames,indent=2),encoding='utf-8')
    manifest=dict(schema='urfall_scene_reference_v1',camera=camera,camera_sha256=file_sha256(calibration),
        stride=stride,depth_units='m',source_scale_m=scale,ground=plane,physical_verified=False,
        source=dict(sequence=source_sequence,archive_sha256=source_sha,sync_sha256=file_sha256(source_sync),
                    prefix_s=prefix_s,last_stamp_s=frames[-1]['local_stamp_s']),
        target=dict(sequence=target_sequence,archive_sha256=target_sha,sync_sha256=file_sha256(target_sync),
                    first_stamp_s=min(target_times.values())),
        chronology=chronology,ground_start_fraction=ground_start_fraction,
        members_sha256={name:file_sha256(out/name) for name in ('reference.npz','clock.json','SOURCE_FRAMES.json')},
        code_sha256={p.name:file_sha256(p) for p in (Path(__file__),Path(__file__).with_name('urfall_raw_depth.py'),
                                                   ROOT/'src/human_fall_detection/core/ground.py')},
        environment=dict(python=sys.version,numpy=np.__version__),
        qualification='clock/setup/empty-prefix metadata declarations; no independent person or physical GT')
    (out/'REFERENCE.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    return manifest


def load_reference(path,camera,camera_sha,stride,sequence,target_sha,target_sync_sha,first_stamp_s):
    doc=json.loads(path.read_text(encoding='utf-8-sig'))
    if (doc.get('schema')!='urfall_scene_reference_v1' or doc.get('physical_verified') is not False or
            doc.get('depth_units')!='m' or doc.get('camera')!=camera or
            doc.get('camera_sha256')!=camera_sha or doc.get('stride')!=stride):
        raise ValueError('Scene reference camera/grid/qualification mismatch')
    target=doc['target'];source=doc['source']
    if (target['sequence']!=sequence or target['archive_sha256']!=target_sha or
            target['sync_sha256']!=target_sync_sha or number(target['first_stamp_s'])!=first_stamp_s):
        raise ValueError('Scene reference target binding mismatch')
    members=doc['members_sha256']
    if set(members)!= {'reference.npz','clock.json','SOURCE_FRAMES.json'}:
        raise ValueError('Incomplete scene reference members')
    for name,digest in members.items():
        if file_sha256(path.parent/name)!=digest:
            raise ValueError('Scene reference member SHA mismatch: '+name)
    clock=json.loads((path.parent/'clock.json').read_text(encoding='utf-8-sig'))
    frames=json.loads((path.parent/'SOURCE_FRAMES.json').read_text(encoding='utf-8'))
    if (not frames or any(number(f['local_stamp_s'])>number(source['prefix_s']) for f in frames) or
            any(b['frame']<=a['frame'] or number(b['local_stamp_s'])<=number(a['local_stamp_s'])
                for a,b in zip(frames,frames[1:])) or
            number(frames[-1]['local_stamp_s'])!=number(source['last_stamp_s'])):
        raise ValueError('Invalid scene reference source ledger')
    chronology=check_clock(clock,source['archive_sha256'],target_sha,source['last_stamp_s'],first_stamp_s)
    if chronology!=doc['chronology']:
        raise ValueError('Scene reference chronology mismatch')
    plane=check_ground(doc['ground'])
    with np.load(path.parent/'reference.npz',allow_pickle=False) as data:
        depth=data['depth_m']
    shape=((camera['height']+stride-1)//stride,(camera['width']+stride-1)//stride)
    if (depth.shape!=shape or depth.dtype.kind!='f' or not np.isfinite(depth).all() or
            np.any(depth<0) or np.any(depth>number(doc['source_scale_m'])) or not np.any(depth>0)):
        raise ValueError('Invalid reference depth grid')
    return depth,plane,dict(manifest_sha256=file_sha256(path),source=source,target=target,
                           chronology=chronology,qualification=doc['qualification'],physical_verified=False)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('source-archive','source-sync','target-archive','target-sync','calibration','clock','output'):
        parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--prefix-seconds',type=float,default=.3)
    parser.add_argument('--ground-start-fraction',type=float,default=.75)
    args=parser.parse_args()
    result=build(args.source_archive,args.source_sync,args.target_archive,args.target_sync,
                 args.calibration,args.clock,args.output,args.prefix_seconds,args.ground_start_fraction)
    print(json.dumps(dict(schema=result['schema'],source=result['source'],target=result['target'],chronology=result['chronology'])))
