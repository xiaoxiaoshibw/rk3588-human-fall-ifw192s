"""Corroborate independent original-bag observation against frozen local assets."""
import hashlib
import json
from pathlib import Path
import sys
import numpy as np

OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[3]
sys.path.insert(0,str(ROOT/'src/human_fall_detection'))
from core.capture_input import load_adapted

def sha_bytes(b):return hashlib.sha256(b).hexdigest()


def compare_frames(meta_frames,bag_frames,manifest_frames):
    if not (len(meta_frames)==len(bag_frames)==len(manifest_frames)):
        raise ValueError('source frame count mismatch')
    keys=('seq','stamp_sec','stamp_nanosec','offset_points','count_points','dropped_points','bag_time_sec')
    for ordinal,(meta,bag,adapted) in enumerate(zip(meta_frames,bag_frames,manifest_frames)):
        if bag['ordinal']!=ordinal or adapted['ordinal']!=ordinal:
            raise ValueError('ordinal alias/ordering mismatch')
        for key in keys:
            original = round(bag[key],6) if key=='bag_time_sec' else bag[key]
            # Frozen extractor explicitly rounds bag time to 6 decimals;
            # source header secs/nsecs remain exact integers, no tolerance.
            if not meta[key]==original==adapted[key]:
                raise ValueError('frame %d.%s mismatch'%(ordinal,key))
    return True


def main():
    observed=json.loads((OUT/'03_original_bag_chain.json').read_text(encoding='utf8'))
    session=ROOT/'captures/remote/cap_20261002_163621'
    meta_raw=(session/'meta.json').read_bytes();bin_raw=(session/'points.bin').read_bytes()
    meta=json.loads(meta_raw)
    declared=meta['extraction']['source_bag_sha256']
    if observed['source']['sha256_before']!=declared or observed['source']['sha256_after']!=declared:
        raise ValueError('original bag hash does not match extraction identity')
    if observed['canonical_bin_sha256']!=sha_bytes(bin_raw):
        raise ValueError('canonical complete byte hash mismatch')
    npz_path=ROOT/'docs/human_fall/evidence/2026-10-03_gl_i02_r1/08_real/real_candidate.adapted.npz'
    manifest,points=load_adapted(str(npz_path))
    if manifest['source']['meta_sha256']!=sha_bytes(meta_raw) or manifest['source']['bin_sha256']!=sha_bytes(bin_raw):
        raise ValueError('NPZ source identity mismatch')
    compare_frames(meta['frames'],observed['frames'],manifest['frames'])
    rows=np.frombuffer(bin_raw,dtype=np.uint8).reshape(-1,28)
    xyz=rows[:,:12].copy().view('<f4').reshape(-1,3)
    if not np.array_equal(points,xyz):raise ValueError('NPZ XYZ differs from canonical source rows')
    if observed['canonical_xyz_sha256']!=sha_bytes(xyz.tobytes()):
        raise ValueError('original bag XYZ digest mismatch')
    per_frame=[]
    for ordinal,frame in enumerate(observed['frames']):
        lo=frame['offset_points'];hi=lo+frame['count_points']
        if sha_bytes(rows[lo:hi].tobytes())!=frame['canonical_frame_sha256']:
            raise ValueError('frame canonical bytes mismatch')
        if sha_bytes(xyz[lo:hi].tobytes())!=frame['raw_xyz_sha256']:
            raise ValueError('frame XYZ content mismatch')
        if frame['frame_id']!=manifest['declared']['frame']:
            raise ValueError('original frame_id mismatch')
        per_frame.append(dict(ordinal=ordinal,seq=frame['seq'],points=frame['count_points'],
                              canonical_bytes_match=True,xyz_match=True))
    result=dict(kind='original_bag_bin_npz_chain_audit',schema=1,
        source_bag_sha256_verified=declared,meta_sha256=sha_bytes(meta_raw),
        bin_sha256=sha_bytes(bin_raw),npz_sha256=sha_bytes(npz_path.read_bytes()),
        xyz_sha256=sha_bytes(xyz.tobytes()),frames=per_frame,total_points=len(xyz),
        all_headers_layout_bytes_xyz_match=True,original_manifest_untouched=True,
        old_source_bag_hash_verified_field=manifest['source']['source_bag_hash_verified'],
        max_timestamp_numeric_conversion_error=observed['max_timestamp_numeric_conversion_error'],
        timestamp_units_verified=False,physical_verified=False,recording_config_binding='unknown',
        conclusion='original bag -> canonical 28-byte binary -> approved NPZ source chain corroborated; '
                   'not an installation, ground identity, human identity or time-unit validation')
    with (OUT/'04_local_chain_audit.json').open('x',encoding='utf8') as f:json.dump(result,f,indent=2)
    print(json.dumps(dict(frames=len(per_frame),points=len(xyz),all_match=True,
        original_manifest_flag=manifest['source']['source_bag_hash_verified'],physical_verified=False)))


if __name__=='__main__':main()
