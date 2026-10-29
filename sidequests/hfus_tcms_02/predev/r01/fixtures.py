"""Explicit SYNTHETIC fixtures. Never sessions A-D or physical sensor evidence."""
from pathlib import Path
import numpy as np
from contracts import Source, sha, write_new


def plane_fixture():
    # Three independent spatial hold-out regions, not SVD refits of fit inliers.
    fit = np.array([[x, y, -1.] for x in np.linspace(.2, 4.8, 18) for y in np.linspace(-2, 2, 15)])
    patches = [(.25, -1.9), (3.7, -1.7), (2.1, 1.1)]
    for x0, y0 in patches:
        fit = fit[~((fit[:,0] >= x0) & (fit[:,0] <= x0+.8) & (fit[:,1] >= y0) & (fit[:,1] <= y0+.7))]
    regions, parts = [], [fit]
    for i, (x0, y0) in enumerate(patches):
        p = np.array([[x, y, -1.] for x in np.linspace(x0, x0 + .8, 6) for y in np.linspace(y0, y0 + .7, 6)])
        start = sum(len(q) for q in parts)
        regions.append(dict(region_id='independent-space-%d' % i, frame_group='spatial-validation-%d' % i,
                            indices=list(range(start, start + len(p)))))
        parts.append(p)
    spec = dict(up_axis=[0, 0, 1], sensor_height_interval_m=[.9, 1.1],
                fit_indices=list(range(len(fit))), fit_frame_group='spatial-fit', validation_regions=regions,
                coordinate_version='SYNTHETIC_RAW_m/v1', reference_axis=[1, 0, 0], synthetic=True,
                independence='Constructed disjoint spatial support; cross-time physical validation NOT_RUN')
    return np.concatenate(parts), spec


def body(x=1.9, low=False):
    if low:
        return np.array([[a, b, -.95] for a in np.linspace(x - .6, x + .6, 9) for b in [-.1, .0, .1]])
    return np.array([[a, b, z] for a in [x - .12, x, x + .12] for b in [-.1, .1]
                     for z in np.linspace(-.8, .7, 9)])


def write_source(folder, frames, stamps=None):
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=False)
    offset, records = 0, []
    if stamps is None:
        stamps = [int(i * 100000000) for i in range(len(frames))]
    with (folder / 'points.bin').open('xb') as stream:
        for i, p in enumerate(frames):
            p = np.asarray(p, dtype='<f4').reshape(-1, 3)
            raw = np.full((len(p), 28), 0xA5, dtype='u1')
            raw[:, :12] = p.view('u1').reshape(-1, 12)
            stream.write(raw.tobytes())
            records.append(dict(seq=i, offset_points=offset, count_points=len(p),
                                stamp_sec=stamps[i] // 1000000000, stamp_nanosec=stamps[i] % 1000000000))
            offset += len(p)
    meta = dict(format='human_capture_session', format_version=1, session_id=folder.name,
                point_stride_bytes=28, total_points=offset, frames=records,
                time_domain='device_stamp_s_unanchored', sensor={'frame_id': 'SYNTHETIC_RAW'},
                point_layout=dict(fields=['x', 'y', 'z', 'OPAQUE_16_BYTES'], dtypes=['<f4'] * 3,
                                  stride_bytes=28, endian='little'))
    write_new(folder / 'meta.json', meta)
    return dict(sid=folder.name, path=str(folder), role='SYNTHETIC_CONTRACT', kind='SYNTHETIC',
                source_sha256={k: sha(folder / n) for k, n in [('meta', 'meta.json'), ('points', 'points.bin')]},
                coordinate_version='SYNTHETIC_RAW_m/v1', development_seen=True, dev_tainted=True,
                audit_scope='All constructed rows; no real human annotation')


def build(output):
    output = Path(output)
    floor, spec = plane_fixture()
    chair = np.array([[3.1, y, z] for y in np.linspace(-.3, .3, 7) for z in np.linspace(-.8, -.3, 6)])
    background = np.concatenate([floor, chair])
    a = write_source(output / 'synthetic_map', [background])
    # Cases retain full current raw rows. No point from a different frame fills a gap.
    frames = [background, np.concatenate([background, body()]),
              np.concatenate([background, body()]), np.concatenate([background, body(low=True)]),
              background, background, background, background,
              np.concatenate([background, body(2.9)]),
              np.concatenate([floor, chair + [0, 1., 0]]),
              np.concatenate([floor, chair + [0, 1., 0]]), background]
    stamps = [0, 100000000, 300000000, 500000000, 700000000, 1000000000,
              1300000000, 1500000000, 1600000000, 1700000000, 1800000000, 1900000000]
    b = write_source(output / 'synthetic_actions', frames, stamps)
    cases = [dict(name=n, fi=i, kind='SYNTHETIC', contract_only=True) for n, i in [
        ('进入', 1), ('静止实测', 2), ('近地卧地', 3), ('遮挡预测', 4), ('超时LOST', 6),
        ('重现背景', 7), ('人椅混合', 8), ('移椅残留', 10)]]
    labels = []
    for i, p in enumerate(frames):
        rows = list(range(len(background), len(p))) if i in [1, 2, 3, 8] else []
        labels.append(dict(sid=b['sid'], source_sha256=b['source_sha256'], fi=i, human_rows=rows, background_rows=[j for j in range(len(p)) if j not in rows],
                           visible=bool(rows), identity='fixture-person', identity_present=i in [1,2,3,4,5,6,8],
                           annotation_kind='points', reviewed=True))
    return dict(map_entry=a, action_entry=b, ground_spec=spec,
                authorization=dict(confirmed_empty=True, layout_consistent=True, provenance='SYNTHETIC_FIXTURE_ONLY',
                                   origin_xyz=None, return_mode_verified=False, angular_support_verified=False,
                                   segments=[dict(sid=a['sid'], source_sha256=a['source_sha256'], start_fi=0, end_fi=0)]),
                cases=cases, labels=labels)
