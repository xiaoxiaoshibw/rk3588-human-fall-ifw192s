"""Register PROTOCOL_V2 for the skeleton milestone: only the observable-model revision.

v1 gated 12 segments including thigh/shin and the head, but a single-view body-plane cloud cannot
separate two near-collinear segments of one limb, and the head capsule is not separable from the
trunk capsule. v2 keeps the same numeric strictness on what is identifiable and makes the synthetic
test harder by requiring real bends (>= 25 deg). No gate is relaxed: the within-tolerance fraction
stays 0.8 and the convergence requirement stays 3 of 4 scenarios within 60 frames.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import s5core as C

if __name__ == '__main__':
    v1 = C.load(C.OUT / 'PROTOCOL_V1.json')
    v2 = dict(v1, version=2, revision_reason=(
        'observable-model revision before any gate run: v1 gated 12 segments including thigh/shin pairs and the '
        'head capsule. A single-view body-plane cloud cannot identify two near-collinear segments of one limb when '
        'the joint is nearly straight, and the head capsule (r 0.09) is not separable from the trunk capsule '
        '(r 0.11). v2 calibrates the identifiable quantities only (trunk + four limb pairs = 9 lengths, plus two '
        'widths), keeps the same strictness (0.8 within max(3 cm, 5%), 3 of 4 scenarios converging within 60 '
        'frames) and makes the synthetic test harder by requiring joint angles >= 25 deg. Failed pilot runs are '
        'kept in PILOT_R1.json (12-segment model) and PILOT_V2.json (this model, measurement still wrong).'))
    v2['body_model'] = dict(
        kind='observable segments of an articulated body in the body plane',
        joints=['PELVIS', 'HEAD', 'SHOULDER_C', 'HIP_C', 'SHOULDER_L', 'ELBOW_L', 'WRIST_L',
                'SHOULDER_R', 'ELBOW_R', 'WRIST_R', 'HIP_L', 'KNEE_L', 'ANKLE_L', 'HIP_R', 'KNEE_R', 'ANKLE_R'],
        segments=['TRUNK', 'UPPER_ARM_L', 'FOREARM_L', 'UPPER_ARM_R', 'FOREARM_R',
                  'THIGH_L', 'SHIN_L', 'THIGH_R', 'SHIN_R'],
        widths=['SHOULDER_W', 'HIP_W'],
        not_gated=['head length (not separable from the trunk capsule)', 'left/right identity', 'absolute scale'],
        plane='body plane from the temporal PCA axis; the third dimension is used only for a depth check',
        seed='anthropometric-ratio seed only (no per-person claim); immediately replaced by online estimates',
        calibration=dict(estimator='per-segment online mean/variance over frames with valid support, drift reset on '
                                   'a single-frame ratio outside [0.6, 1.7]',
                         states=['COLLECTING', 'CALIBRATING', 'CALIBRATED', 'DRIFT_RESET'],
                         calibrated='relative std <= 3% over the last 15 samples with >= 15 samples'),
        measurement=dict(trunk='axial 2-98 percentile span of the trunk core band minus twice the median lateral '
                               'radius of that band',
                         limb='best-breakpoint two-segment polyline of each limb quadrant, each part measured along '
                              'its own principal direction minus twice its median cross-section radius',
                         width='sum of the per-side median |v| of limb clusters inside the shoulder/hip height band'))
    v2['verification'] = dict(v1['verification'])
    v2['verification']['synthetic'] = dict(
        generator=v1['verification']['synthetic']['generator'],
        scenarios=['upright', 'bent', 'lying', 'occluded'],
        observable_condition='all limb joint angles >= 25 deg so thigh/shin and upper/forearm are separable',
        metric='recovered vs true length for the 9 segments and 2 widths',
        gate='at least 80% of the 11 quantities within max(3 cm, 5%) and at least 3 of 4 scenarios converging '
             'within 60 frames',
        no_cheating=v1['verification']['synthetic']['no_cheating'])
    v2['verification']['real'] = dict(
        data=v1['verification']['real']['data'],
        reported=v1['verification']['real']['reported'],
        accuracy='UNKNOWN (no joint ground truth)')
    v2['verification']['gates'] = dict(
        K03=v2['verification']['synthetic']['gate'],
        K04=v1['verification']['gates']['K04'],
        K05=v1['verification']['gates']['K05'])
    v2['protocol_history'] = dict(v1_sha=C.sha(C.OUT / 'PROTOCOL_V1.json'),
                                  v1_used_for='the first implementation round only; no gate run happened under v1')
    C.write(C.OUT / 'PROTOCOL_V2.json', v2)
    print(C.sha(C.OUT / 'PROTOCOL_V2.json'))
