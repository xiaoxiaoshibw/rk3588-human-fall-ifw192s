"""Stream every source row and all frozen members through one historical R/t."""
import argparse
import json
import time
import numpy as np
from bootstrap import ROOT,OUT,sha,write
from preview import load,make_transform,Frozen,converted_record
from coordinates import Transform,check_points,valid_xyz


def save(path,array):
    with PathGuard(path).open('xb') as f:np.save(f,array,allow_pickle=False)


def PathGuard(path):
    p=path.absolute()
    if not p.resolve().is_relative_to(OUT.resolve()) or any(x.is_symlink() or x.is_junction() for x in [p,*p.parents] if x.exists()):
        raise ValueError('Output outside item/reparse')
    return p


def residual(p,T):
    z=p[valid_xyz(p)]@T.R[2]+T.t[2]
    return dict(denominator=len(z),rms_m=float(np.sqrt(np.mean(z*z))) if len(z) else None,
        median_signed_m=float(np.median(z)) if len(z) else None,
        p95_abs_m=float(np.percentile(np.abs(z),95)) if len(z) else None,
        interpretation='ALL_VALID_SCENE including furniture/walls; not ground quality')


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--mode',choices=['probe','full'],required=True);ap.add_argument('--label');a=ap.parse_args()
    start=time.time();protocol=load(OUT/'PROTOCOL_V1.json')
    label=a.label or a.mode
    if not label.replace('_','').isalnum():raise ValueError('Unsafe output label')
    dest=OUT/label;dest.mkdir(exist_ok=False)
    here=__import__('pathlib').Path(__file__).resolve().parent
    write(dest/'CODE_AT_START.json',dict(argv=__import__('sys').argv,protocol_sha=sha(OUT/'PROTOCOL_V1.json'),
        files={str(p.relative_to(ROOT)):sha(p) for p in here.iterdir() if p.is_file()},
        note='frozen before source loading; no runtime code reload'))
    artifact=make_transform(protocol)
    if not (OUT/'TRANSFORM_V1.json').exists():write(OUT/'TRANSFORM_V1.json',artifact)
    elif load(OUT/'TRANSFORM_V1.json')!=artifact:raise ValueError('Transform drift')
    T=Transform(artifact);frozen=Frozen(protocol)
    write(OUT/(label+'_SOURCE_SHA.json'),dict(actual=frozen.source.binding,source_stats=frozen.source_stats,
        alias_resolves_to_same=(ROOT/'captures/remote'/frozen.source.sid).resolve()==frozen.source.folder.resolve(),
        historical_transform_sha=sha(ROOT/protocol['historical']['path']),
        frozen_output_index_sha=sha(frozen.path/'OUTPUT_INDEX.json'),protocol_sha=sha(OUT/'PROTOCOL_V1.json')))
    ids=protocol['probe_frames'] if a.mode=='probe' else list(range(780))
    entries=[];totals=dict(rows=0,valid=0,invalid=0,candidates=0,member_rows=0,track_rows=0)
    index_hashes={}
    trajectory=[]
    with (dest/'FRAME_CHECKS.jsonl').open('x',encoding='utf8') as log:
        for fi in ids:
            f,r,rows,hits,p=frozen.frame(fi)
            q=T.points(p,T.tag(fi,False),fi,source_validity=True)
            check=check_points(T,p,q)
            record=converted_record(T,r,p,q,rows)
            record['historical_record_sha']=sha(frozen.path/f['variants']['main']['record'])
            record['scene_residual']=residual(p,T)
            # Legacy band selection is descriptive, never a ground validation set.
            mask=(rows['flags']&32)!=0
            record['legacy_band_residual']=residual(p[mask],T)
            record['legacy_band_residual']['interpretation']='LEGACY_SELECTED_BAND; selected-on-plane, not validation or confirmed ground'
            save(dest/('%04d.npy'%fi),q)
            write(dest/('%04d.json'%fi),record)
            # Read persisted full array and independently check all rows, not display samples.
            disk=np.load(dest/('%04d.npy'%fi),mmap_mode='r',allow_pickle=False)
            check_points(T,p,disk)
            del disk
            check.update(fi=fi,rows=len(p),raw28_sha256=f['raw28_sha256'],
                candidate_count=len(record['candidates']),candidate_members=sum(len(c['rows']) for c in r['candidates']),
                track_state=r['track']['state'],track_rows=len(r['track']['rows']),
                map_exists=record['candidate_map_exists'],scene_residual=record['scene_residual'],
                legacy_band_residual=record['legacy_band_residual'])
            log.write(json.dumps(check,allow_nan=False)+'\n');log.flush()
            entries.append(dict(fi=fi,offset=f['offset_points'],rows=len(p),raw28_sha256=f['raw28_sha256']))
            for suffix in ['npy','json']:index_hashes['%04d.%s'%(fi,suffix)]=sha(dest/('%04d.%s'%(fi,suffix)))
            totals['rows']+=len(p);totals['valid']+=check['valid'];totals['invalid']+=check['invalid']
            totals['candidates']+=check['candidate_count'];totals['member_rows']+=check['candidate_members'];totals['track_rows']+=check['track_rows']
            if r['track']['center'] is not None:
                trajectory.append(dict(fi=fi,raw_center=r['track']['center'],local_center=record['track']['center'],
                    tag=T.tag(fi),historical_state=r['track']['state'],historical_track_id=r['track'].get('track_id'),
                    identity_valid_for_coordinate_version=False))
            if fi%100==0:print('checked',fi,'rows',totals['rows'],flush=True)
    if a.mode=='full':
        m=frozen.map;mapdir=dest/'map';mapdir.mkdir(exist_ok=False)
        for key in ['centers','matching_tree_xyz']:
            save(mapdir/(key+'.npy'),T.points(m[key],T.tag(-1,False),-1))
        obb=np.array([T.box(lo,hi,-1) for lo,hi in zip(m['minimum'],m['maximum'])])
        save(mapdir/'obb_corners.npy',obb)
        # Only frozen diagonal noise is available; do not claim full measured covariance.
        save(mapdir/'diagonal_noise_proxy_covariance.npy',T.covariance(np.array([np.diag(x*x) for x in m['noise']])))
        ids_support=m['support_global'];support_check=dict(rows=len(ids_support),roundtrip_max_m=0.0,display_float32_max_m=0.0)
        with PathGuard(mapdir/'support_local_xyz.bin').open('xb') as dest_support:
            for startrow in range(0,len(ids_support),50000):
                ids_batch=ids_support[startrow:startrow+50000]
                raw=np.asarray(frozen.source.xyz[ids_batch],dtype=float)
                if not valid_xyz(raw).all():raise ValueError('Invalid M0 support')
                local=T.points(raw,T.tag(-1,False),-1)
                checked=check_points(T,raw,local)
                support_check['roundtrip_max_m']=max(support_check['roundtrip_max_m'],checked['roundtrip_max_m'])
                support_check['display_float32_max_m']=max(support_check['display_float32_max_m'],checked['display_float32_max_m'])
                dest_support.write(np.asarray(local,dtype='<f8').tobytes())
        meta=dict(tag=T.tag(-1),historical_meta=frozen.map_meta,surfaces=len(m['centers']),
            support=support_check,CSR='unchanged frozen support_global/indptr, exact order; linked by SHA',
            frozen_surfaces_sha=sha(frozen.path/'map/surfaces.npz'),
            available_after_fi=frozen.map_build_end,first_display_fi=next(x['fi'] for x in entries if load(dest/('%04d.json'%x['fi']))['candidate_map_exists']),
            operation='FROZEN_M0_NUMERIC_TRANSFORM; no local voxel rebuild, no algorithm rerun',
            covariance='R diag(noise_xyz**2) R.T, diagonal-only frozen proxy, cross terms absent in input',
            geometry_validated=False)
        write(mapdir/'MAP.json',meta)
        for p in mapdir.iterdir():index_hashes[str(p.relative_to(dest)).replace('\\','/')]=sha(p)
        write(dest/'TRAJECTORY.json',trajectory)
        index_hashes['TRAJECTORY.json']=sha(dest/'TRAJECTORY.json')
        if totals['rows']!=protocol['source']['rows'] or len(entries)!=780:raise ValueError('Full denominator missing')
    write(dest/'INDEX.json',dict(frames=entries,tag=T.tag(-1),source_sha256=frozen.source.binding,
        frozen_run=protocol['frozen_run'],transform_sha256=sha(OUT/'TRANSFORM_V1.json')))
    index_hashes['INDEX.json']=sha(dest/'INDEX.json')
    write(dest/'OUTPUT_INDEX.json',index_hashes)
    final={k:sha(frozen.source.folder/n) for k,n in [('meta','meta.json'),('points','points.bin')]}
    if final!=frozen.source.binding or frozen.stats()!=frozen.source_stats:raise ValueError('Source changed during run')
    write(dest/'SUMMARY.json',dict(mode=a.mode,frames=len(entries),totals=totals,seconds=time.time()-start,
        source_final=final,source_zero_write='opened read only; before/after SHA+size+mtime identical',
        bytes=sum(p.stat().st_size for p in dest.rglob('*') if p.is_file()),
        velocity_covariance_real='NOT_PRESENT_IN_FROZEN_INPUT; adapter synthetic tested; no fabricated measured values',
        algorithm_rerun=False))
    frozen.source.close()
    print(json.dumps(load(dest/'SUMMARY.json')))


if __name__=='__main__':main()
