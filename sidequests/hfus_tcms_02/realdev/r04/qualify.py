"""T5 close-out: bind the verification result to the frozen transform without changing R/t."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import s3core as C
import transform as X

if __name__ == '__main__':
    art_path = C.OUT / 'TRANSFORM/TRANSFORM_S3.json'
    ver_path = C.OUT / 'RUN/VERIFICATION.json'
    art = C.load(art_path)
    ver = C.load(ver_path)
    if art['transform_id'] != ver['transform_id'] or art['coordinate_version'] != ver['coordinate_version']:
        raise SystemExit('TRANSFORM/VERIFICATION MISMATCH')
    passed = (ver['spatial_pass_patches'] >= ver['spatial_required'] and ver['temporal']['PASS']
              and ver['prefix']['PASS'] and ver['m0_rebuild_ok'])
    C.write(C.OUT / 'TRANSFORM/TRANSFORM_QUALIFICATION.json', dict(
        item=C.ITEM, transform_id=art['transform_id'], coordinate_version=art['coordinate_version'],
        artifact_sha=C.sha(art_path),
        R=art['R'], t=art['t'],
        R_t_unchanged=True,
        qualification=dict(identity_confirmed=False,
                           geometry_validated_local=bool(passed),
                           physical_verified=False,
                           runtime_eligible=False,
                           offline_preview=True),
        state='GEOMETRY_VALIDATED_LOCAL' if passed else 'CANDIDATE_PLANE_PREVIEW',
        state_from_fi=271 if passed else None,
        evidence=dict(verification_sha=C.sha(ver_path),
                      domains_sha=ver['domains_sha'],
                      spatial=ver['spatial_pass_patches'], spatial_required=ver['spatial_required'],
                      temporal=ver['temporal']['fraction'], temporal_required=0.95,
                      prefix=ver['prefix']['all_patch_pass_frames'], prefix_required='19/19',
                      m0_rebuild_ok=ver['m0_rebuild_ok']),
        not_claimed=['ground identity', 'physical height/extrinsics', 'independent D', 'human effect',
                     'production/online eligibility'],
        note='qualification is a separate record: the frozen artifact bytes were not rewritten, '
             'R/t are byte-identical, and identity/physical/runtime stay false'))
    print('qualification written: %s' % passed)
