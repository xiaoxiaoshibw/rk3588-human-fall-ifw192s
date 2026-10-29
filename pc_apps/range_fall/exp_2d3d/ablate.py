"""2D/3D 联合路线只读实验：消融、最小 GT 对照、地面口径统一。

用途（pc_apps/range_fall/exp_2d3d/ablate.py）：
  survey      只读统计两会话逐帧状态、目标连续段、2D/3D 共享信息量。
  fit-ground  用 386 同一套既有配平估计器为另一会话拟合同源地面，写
              TRANSFORM.json + BOUND_GROUND.json + 质量记录。
  ablate      复算唯一前端的 2D 连通域与 5cm 3D 组件，按冻结阈值给出
              R2D / R3D / 联合 三路标签，输出可对照的逐帧表与汇总。
  render      一次性渲染 2D+3D 预览拼图（同一帧只渲染一次，不覆盖）。
  compare     人工 GT 表与算法输出逐帧对照与混淆计数。

不写生产默认、冻结配置、原始会话、历史证据；所有派生 JSON/PNG 只进同一
临时目录，任务末尾整体删除。仅 stdlib + NumPy，Python 3.8 语法兼容。
"""
import argparse
import hashlib
import json
import math
import sys
from collections import Counter
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
for _p in (ROOT / 'src/human_fall_detection', ROOT / 'src/human_fall_detection/scripts',
           ROOT / 'pc_apps/range_fall', ROOT / 'pc_apps/human_replay'):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from core.capture_input import ROW_DTYPE                      # noqa: E402
from core.range_image import ScanGrid                         # noqa: E402
from core.range_contract import binding_tuple                 # noqa: E402
from core.range_background import RayBackground               # noqa: E402
from core.range_denoise import denoise                        # noqa: E402
from core.range_components import label_components            # noqa: E402
from core.range_shape import shape_features                   # noqa: E402
from core.range_features import bound_ground             # noqa: E402
from core.lidar_candidates import rebuild_candidate, spatial_components  # noqa: E402
from replay_range_frontend import CALIBRATION, session_meta   # noqa: E402
from depth import png                                         # noqa: E402

# ---- 冻结口径（引用来源，不在本脚本调参） ----
PREFIX_FRAMES = 50                  # 与 386/780 既有运行同一 --empty-prefix-frames
MIN_COMPONENT_POINTS = 15           # core/range_runtime.py min_component_points
MIN_NEIGHBOURS = 2                  # core/range_runtime.py min_neighbours
R3D_CELL_M = 0.05                   # perception_single_target_v3.yaml cluster_cell_m
R3D_MIN_POINTS = 30                 # perception_single_target_v3.yaml min_cluster_points
PCA_MIN_POINTS = 12                 # perception_candidates pca_min_points
LYING_MAX_TOP_M = 0.7               # fall.lying_max_top_m / range_posture.max_top_m
LYING_MIN_EXTENT_M = 0.6            # fall.lying_min_extent_m
LYING_MAX_VERTICALITY = 0.5         # range_posture.max_verticality
VERTICAL_SURFACE_MIN = 0.8          # range_posture 直立分支阈值
POSE_MIN_POINTS = 15                # range_posture.min_points
RANGE_MIN_M, RANGE_MAX_M = 0.1, 8.0  # core/range_runtime.py 前景距离门

GROUND_FIT_MAX_FRAMES = 50   # 全段均匀抽样上限；固定取前 50 帧会被前段人物/家具污染
GROUND_FIT_MIN_FRAMES = 4    # 至少 1 个拟合帧 + 3 个独立留出帧


# ------------------------------------------------------------------ 基础工具
def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1 << 20), b''):
            digest.update(block)
    return digest.hexdigest()


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')


def load_json(path):
    with Path(path).open(encoding='utf-8') as stream:
        return json.load(stream)


def session_frame_bytes(session, info):
    with (session / 'points.bin').open('rb') as stream:
        stream.seek(info['offset_points'] * ROW_DTYPE.itemsize)
        raw = stream.read(info['count_points'] * ROW_DTYPE.itemsize)
    if len(raw) != info['count_points'] * ROW_DTYPE.itemsize:
        raise ValueError('truncated frame bytes')
    return raw


def grid_and_binding(session):
    grid = ScanGrid.from_csv(CALIBRATION / 'ifw192s_azimuth_192x256.csv',
                             CALIBRATION / 'ifw192s_elevation_192x256.csv')
    meta, meta_sha = session_meta(session)
    identity = dict(session=session.name, meta_sha256=meta_sha,
                    points_sha256=sha256_file(session / 'points.bin'),
                    coordinate='RAW/' + meta['sensor']['frame_id'], units='m',
                    coordinate_transform='identity', grid_sha256=grid.sha256,
                    epoch='source_header_epoch')
    identity['azimuth_sha256'] = sha256_file(CALIBRATION / 'ifw192s_azimuth_192x256.csv')
    identity['elevation_sha256'] = sha256_file(CALIBRATION / 'ifw192s_elevation_192x256.csv')
    return grid, meta, identity


def stamp_of(info):
    return info['stamp_sec'] + info.get('stamp_nanosec', 0) / 1e9


# ------------------------------------------------------------------ survey
def cmd_survey(args):
    out = {}
    for tag, session, analysis in args.pair:
        grid, meta, identity = grid_and_binding(Path(session))
        doc = load_json(analysis)
        frames = doc['frames']
        measured = [f for f in frames if f['measured']]
        runs = []
        for f in measured:
            if runs and f['frameIndex'] == runs[-1][-1] + 1:
                runs[-1].append(f['frameIndex'])
            else:
                runs.append([f['frameIndex']])
        dts = [frames[i + 1]['stampSec'] - frames[i]['stampSec'] for i in range(len(frames) - 1)]
        item = dict(
            tag=tag, sessionId=doc['sessionId'], frames=len(frames),
            processed=doc['processedFrames'], dropped=doc['droppedFrames'],
            completeSession=doc['completeSession'], postureSettings=doc['postureAlgorithm']['settings'],
            postureCalibrationStatus=doc['postureAlgorithm']['calibrationStatus'],
            confirmedEnabled=doc['confirmedEnabled'], semantic=doc['semantic'],
            intervals=doc['intervals'], measuredFrames=len(measured),
            measuredRuns=[[r[0], r[-1], len(r)] for r in runs],
            tracks=dict(Counter(f['trackId'] for f in measured if f['trackId'])),
            states=dict(Counter(f['state'] for f in frames)),
            posture=dict(Counter(f['posture']['state'] for f in frames)),
            postureReason=dict(Counter(f['posture']['reason'] for f in frames)),
            reasonSets=dict(Counter('+'.join(f['reasons']) or '(none)' for f in frames)),
            targetReasons=dict(Counter(str(f['targetReason']) for f in frames)),
            observationGapFrames=sum(1 for f in frames if f['observationGap']),
            medianDtSec=float(np.median(dts)), minDtSec=float(np.min(dts)), maxDtSec=float(np.max(dts)),
            uniqueRawSha=len({f['rawSha256'] for f in frames}),
            gridSha256=identity['grid_sha256'],
            targetPixelsTotal=int(sum(f['depth']['targetPixels'] for f in frames)),
            targetRowsTotal=int(sum(len(f['sourceRows']) for f in frames)),
            validPixelsTotal=int(sum(f['depth']['validPixels'] for f in frames)),
            framesWhereTargetPixelsEqualsRows=int(sum(
                1 for f in frames if f['depth']['targetPixels'] == len(f['sourceRows']))),
            metaSha256=identity['meta_sha256'], pointsSha256=identity['points_sha256'],
            humanAnnotations=meta.get('human_annotations'),
            sourceFrameCount=doc['sourceFrameCount'],
        )
        out[tag] = item
        print(json.dumps({k: item[k] for k in
                          ('tag', 'sessionId', 'frames', 'measuredFrames',
                           'framesWhereTargetPixelsEqualsRows', 'targetPixelsTotal',
                           'targetRowsTotal')}, ensure_ascii=False))
    if args.out:
        write_json(args.out, out)
    return 0


# ------------------------------------------------------------------ fit-ground
WINDOW_SPECS = (('head', 0), ('spread', 0), ('wide', 0))


def ground_frame_window(frame_count, kind):
    """返回一次拟合的 (fit_frames, held_frames)，两者互不重叠。

    head   旧版窗口：前 50 帧（fit 0..48 步长 2），留出 50/75/99；短会话退回三分点。
    spread 整段均匀抽样最多 50 帧，留出 1/3、2/3 与末帧。
    wide   整段均匀抽样最多 120 帧，留出同上。
    只改变输入帧覆盖，不放宽 floor_roi / leveling_quality 的任何阈值。
    """
    if frame_count < GROUND_FIT_MIN_FRAMES:
        raise ValueError('need at least %d frames (one fit plus three held-out)' % GROUND_FIT_MIN_FRAMES)
    if kind == 'head' and frame_count >= 100:
        held = [50, 75, 99]
    else:
        held = sorted({(frame_count - 1) // 3, 2 * (frame_count - 1) // 3, frame_count - 1})
    if kind == 'head':
        fit = [fi for fi in range(0, min(50, frame_count), 2) if fi not in held]
        return fit, held
    cap = 50 if kind == 'spread' else 120
    pool = [i for i in range(frame_count) if i not in held]
    if len(pool) > cap:
        pick = np.linspace(0, len(pool) - 1, cap)
        pool = [pool[int(round(float(v)))] for v in pick]
    return sorted(set(pool)), held


def cmd_fit_ground(args):
    """与 sidequests/.../prepare_leveling.py 同一估计器与质量门；按确定性窗口依次尝试。"""
    from floor_roi import detect_floor_regions_v3
    from leveling_estimators import ESTIMATORS
    from leveling_quality import compare, rotation

    session = Path(args.session).resolve()
    out = Path(args.out).resolve()
    session_meta_map, _ = session_meta(session)
    grid, meta, identity = grid_and_binding(session)
    frames_xyz = {}

    def frame_xyz(fi):
        if fi not in frames_xyz:
            info = meta['frames'][fi]
            packed = np.frombuffer(session_frame_bytes(session, info), dtype=ROW_DTYPE)
            p = np.lib.stride_tricks.as_strided(
                packed['x'], shape=(len(packed), 3), strides=(packed.strides[0], 4),
                writeable=False).astype(np.float64)
            frames_xyz[fi] = p
        return frames_xyz[fi]

    def load_frames(frames):
        samples, frame_ids = [], []
        for fi in frames:
            p = frame_xyz(fi)
            keep = np.flatnonzero(np.isfinite(p).all(1) & np.any(p != 0, 1))
            samples.append(p[keep])
            frame_ids.append(np.full(len(keep), fi, dtype=int))
        return np.concatenate(samples), np.concatenate(frame_ids)

    base = dict(sessionId=session.name, estimator='existing floor_roi v3 -> four full-height '
                'patches -> TLS/SVD/RANSAC consensus; unchanged thresholds, deterministic fit windows',
                sourceSha256=dict(meta=identity['meta_sha256'], points=identity['points_sha256']))
    frame_count = len(meta['frames'])
    if frame_count < GROUND_FIT_MIN_FRAMES:
        error = 'need at least %d frames (one fit plus three held-out)' % GROUND_FIT_MIN_FRAMES
        write_json(out / 'GROUND_FIT.json', dict(base, status='INFEASIBLE', error=error))
        print('INFEASIBLE: ' + error)
        return 2
    specs = [(args.window, 0)] if getattr(args, 'window', None) else list(WINDOW_SPECS)
    attempts = []
    solved = None
    for kind, _ in specs:
        fit_frames, held_frames = ground_frame_window(frame_count, kind)
        attempt = dict(window=kind, fitFrames=fit_frames, heldFrames=held_frames)
        try:
            p, ids = load_frames(fit_frames)
            seed_n, seed_d = ESTIMATORS['ransac'](p[::max(1, len(p) // 100000)])
            if seed_n[2] < 0:
                seed_n, seed_d = -seed_n, -seed_d
            attempt['seed'] = dict(normal=seed_n.tolist(), offset_m=float(seed_d))
            if seed_n[2] < .8 or not .8 <= seed_d <= 1.8:
                raise ValueError('initial plane is not a plausible ground orientation')
            pitch = math.degrees(math.atan2(-seed_n[0], seed_n[2]))
            roll = math.degrees(math.asin(float(np.clip(seed_n[1], -1, 1))))
            initial = rotation(pitch, roll)
            domain = detect_floor_regions_v3(p, ids, pitch, roll)
            xy = (p @ initial.T)[:, :2]
            codes = np.zeros(len(p), dtype=int)
            for i, (xl, xh, yl, yh) in enumerate(domain['regions'], 1):
                codes[(xy[:, 0] >= xl) & (xy[:, 0] < xh) & (xy[:, 1] >= yl) & (xy[:, 1] < yh)] = i
            take = codes > 0
            held = []
            for fi in held_frames:
                q = frame_xyz(fi)
                q = q[np.isfinite(q).all(1) & np.any(q != 0, 1)]
                qxy = (q @ initial.T)[:, :2]
                hc = np.zeros(len(q), dtype=int)
                for i, (xl, xh, yl, yh) in enumerate(domain['regions'], 1):
                    hc[(qxy[:, 0] >= xl) & (qxy[:, 0] < xh) & (qxy[:, 1] >= yl) & (qxy[:, 1] < yh)] = i
                held.append(dict(ordinal=fi, points=q[hc > 0], regions=hc[hc > 0]))
            quality = compare(p[take], codes[take], held, initial[2])
        except ValueError as exc:
            attempt.update(status='INFEASIBLE', error=str(exc))
            attempts.append(attempt)
            continue
        attempt['consensus'] = quality['consensus']
        attempt['recommended'] = quality['recommended']
        attempts.append(attempt)
        if quality['consensus'] != 'GOOD':
            attempt.update(status='REJECTED', error='existing ground quality checks rejected selected domain')
            continue
        attempt['status'] = 'FEASIBLE'
        solved = dict(kind=kind, fit_frames=fit_frames, held_frames=held_frames, p=p, domain=domain,
                      quality=quality, initial=initial)
        break
    if solved is None:
        state = 'REJECTED' if any(a.get('status') == 'REJECTED' for a in attempts) else 'INFEASIBLE'
        detail = '; '.join('%s: %s' % (a['window'], a.get('error', a.get('consensus', '?'))) for a in attempts)
        write_json(out / 'GROUND_FIT.json', dict(base, status=state, attempts=attempts,
                                                  error=detail))
        print(state + ': no fit window passed (' + detail + ')')
        return 2
    fit_frames, held_frames = solved['fit_frames'], solved['held_frames']
    p, domain, quality, initial = solved['p'], solved['domain'], solved['quality'], solved['initial']
    record = dict(base, window=solved['kind'], fitFrames=fit_frames, heldFrames=held_frames,
                  seed=attempts[-1].get('seed'), attempts=attempts)
    write_json(out / 'QUALITY.json', quality)
    record['quality'] = dict(consensus=quality['consensus'], recommended=quality['recommended'],
                             pairwise=quality['pairwise'],
                             domain_geometry=quality['domain_geometry'])
    record['regions'] = domain['regions']

    fitted = quality['estimators'][quality['recommended']]
    domain['candidate'].update(normal_source=fitted['normal_source'],
                               offset_source_m=fitted['offset_source_m'],
                               pitch_deg=fitted['pitch_deg'], roll_deg=fitted['roll_deg'])
    candidate = domain['candidate']
    normal = np.array(candidate['normal_source'])
    offset = candidate['offset_source_m']
    rot = rotation(candidate['pitch_deg'], candidate['roll_deg'])
    trans = np.array([0., 0., offset])
    if not np.allclose(rot[2], normal, atol=1e-10, rtol=0):
        raise ValueError('rotation row does not match plane normal')
    if not (np.allclose(rot @ rot.T, np.eye(3), atol=1e-10, rtol=0) and abs(np.linalg.det(rot) - 1) < 1e-10):
        raise ValueError('rotation is not orthonormal')
    validation = []
    for fi in held_frames:
        q = frame_xyz(fi)
        q = q[np.isfinite(q).all(1) & np.any(q != 0, 1)]
        residual = q @ normal + offset
        ground = q[np.abs(residual) <= .08]
        z = (ground @ rot.T + trans)[:, 2]
        validation.append(dict(fi=fi, full_points=len(q), plane_band_points=len(ground),
                               support_ratio=len(ground) / len(q),
                               band_rms_m=float(np.sqrt(np.mean(z * z))),
                               band_p95_m=float(np.percentile(np.abs(z), 95)),
                               note='band-conditioned geometric residual; not independent ground identity truth'))
    back = ((p @ rot.T + trans) - trans) @ rot
    artifact = dict(kind='project_ground_leveling', sid=session.name,
                    source_sha256=dict(meta=identity['meta_sha256'], points=identity['points_sha256']),
                    from_frame='RAW/innolidar', to_frame='GROUND_PROJECT', units='m',
                    R=rot.tolist(), t=trans.tolist(), row_formula='p_ground = p_raw @ R.T + t',
                    plane=candidate, fit_frames=fit_frames, held_frames=validation,
                    domain=domain['regions'], quality='GOOD / unchanged existing gates',
                    roundtrip_max_m=float(np.abs(back - p).max()),
                    qualification=dict(physical_verified=False, extrinsics_verified=False,
                                       runtime_eligible=False),
                    code_sha={str(k.relative_to(ROOT)): sha256_file(k) for k in (
                        HERE / 'ablate.py', ROOT / 'pc_apps/human_replay/floor_roi.py',
                        ROOT / 'pc_apps/human_replay/floor_sheet.py',
                        ROOT / 'pc_apps/human_replay/floor_detector.py',
                        ROOT / 'pc_apps/human_replay/leveling_quality.py',
                        ROOT / 'pc_apps/human_replay/leveling_estimators/ransac.py')})
    transform_id = hashlib.sha256(json.dumps(artifact, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    artifact['to_frame'] = 'GROUND_PROJECT/' + transform_id
    artifact['transform_id'] = transform_id
    write_json(out / 'TRANSFORM.json', artifact)
    transform_sha = sha256_file(out / 'TRANSFORM.json')
    ground = dict(status='valid', frame='innolidar', normal=candidate['normal_source'],
                  offset_m=offset,
                  provenance=dict(source=str(out / 'TRANSFORM.json'), sha256=transform_sha,
                                  physical_applicability='UNKNOWN'),
                  binding=identity)
    write_json(out / 'BOUND_GROUND.json', ground)
    record.update(status='FEASIBLE', transformSha256=transform_sha,
                  boundGroundSha256=sha256_file(out / 'BOUND_GROUND.json'),
                  transformId=transform_id, normal=ground['normal'], offsetM=ground['offset_m'],
                  pitchDeg=candidate['pitch_deg'], rollDeg=candidate['roll_deg'],
                  supportRatio=candidate['support_ratio'], held=validation,
                  roundtripMaxM=artifact['roundtrip_max_m'],
                  qualification=artifact['qualification'])
    write_json(out / 'GROUND_FIT.json', record)
    print(json.dumps({k: record[k] for k in ('status', 'normal', 'offsetM', 'pitchDeg', 'rollDeg',
                                             'supportRatio', 'transformSha256',
                                             'boundGroundSha256')}, ensure_ascii=False))
    return 0


# ------------------------------------------------------------------ 前端复算
def frontend_scan(session, grid, identity, limit=None):
    """复算唯一前端（逐射线背景 -> 去噪 -> 2D 连通域），逐帧 yield。"""
    meta, _ = session_meta(session)
    count = len(meta['frames']) if limit is None else min(limit, len(meta['frames']))
    binding = binding_tuple(identity)
    prefix, background = [], None
    for index in range(count):
        info = meta['frames'][index]
        raw = session_frame_bytes(session, info)
        frame = grid.decode(raw, binding)
        if background is None:
            if index != len(prefix):
                raise ValueError('non-contiguous prefix')
            prefix.append(frame)
            mask = np.zeros(grid.shape, dtype=bool)
        else:
            mask = background.foreground(frame)['mask']
            mask &= (frame.range_m >= RANGE_MIN_M) & (frame.range_m <= RANGE_MAX_M)
        cleaned = denoise(frame, mask, min_neighbours=MIN_NEIGHBOURS)
        labels, components = label_components(frame, cleaned['mask'],
                                              min_points=MIN_COMPONENT_POINTS)
        if background is None and len(prefix) == PREFIX_FRAMES:
            background = RayBackground(prefix, empty_prefix_declared=True,
                                       min_observations=min(10, PREFIX_FRAMES))
            prefix = []
        yield index, info, raw, frame, cleaned['mask'], labels, components


def cluster_pose(frame, rows, ground):
    """3D-only 结构量与冻结姿态判定；ground 未绑定时全部记 unknown。"""
    plane = bound_ground(frame, ground)
    xyz = frame.xyz[rows].astype(np.float64)
    features = rebuild_candidate(xyz, np.arange(len(rows)), ground=plane,
                                 frame_id=plane['frame'] if plane else 'unbound')
    height = features['height_m']
    top = None if height is None else height['max']
    extent_block = features['horizontal_extent_m']
    extent = None if extent_block is None else extent_block['max']
    axis = features['axis'] or dict(axis=None, eigenvalues=None, elongation=None,
                                    ambiguous=True, reason='no_candidate_axis',
                                    verticality=None)
    verticality = axis.get('verticality')
    pose = 'unknown'
    if top is not None and extent is not None and verticality is not None:
        if (0 <= top <= LYING_MAX_TOP_M and extent >= LYING_MIN_EXTENT_M
                and 0 <= verticality <= LYING_MAX_VERTICALITY):
            pose = 'lying'
        elif top <= LYING_MAX_TOP_M:
            pose = 'low'
        elif verticality >= VERTICAL_SURFACE_MIN:
            pose = 'standing'
    return dict(point_count=int(features['point_count']), top_m=top,
                extent_m=None if extent is None else float(extent),
                verticality=verticality, axis_ambiguous=bool(axis['ambiguous']),
                axis_reason=axis.get('reason'),
                ground_relative=bool(plane is not None and height is not None),
                pose=pose,
                height_min_m=None if height is None else height['min'],
                height_p10_m=None if height is None else height['p10'],
                range_median_m=features['range_m']['median'],
                eigenvalues_m2=axis.get('eigenvalues'))




def dilation2(cells, shape, radius=2):
    """2 格 8 邻域膨胀（仅用于判粘连候选，不进入判定阈值）。"""
    h, w = shape
    out = np.zeros(shape, dtype=bool)
    y, x = cells // w, cells % w
    for dy in range(-radius, radius + 1):
        for dx in range(-radius, radius + 1):
            yy = np.clip(y + dy, 0, h - 1)
            xx = np.clip(x + dx, 0, w - 1)
            out[yy, xx] = True
    return out


def cmd_ablate(args):
    session = Path(args.session).resolve()
    grid, meta, identity = grid_and_binding(session)
    doc = load_json(args.analysis)
    if doc['sessionId'] != session.name:
        raise ValueError('analysis/session mismatch')
    by_index = {f['frameIndex']: f for f in doc['frames']}
    recorded = {}
    if args.run:
        with (Path(args.run) / 'frames.jsonl').open(encoding='utf-8') as stream:
            for line in stream:
                row = json.loads(line)
                recorded[row['frame']] = row
    ground = load_json(args.ground) if args.ground else None
    if ground is not None and ground.get('binding') != identity:
        raise ValueError('ground binding mismatch')
    rows_out, counts = [], Counter()
    verify = Counter()
    for index, info, raw, frame, mask, labels, components in frontend_scan(
            session, grid, identity, limit=args.limit):
        row = by_index.get(index)
        if row is None:
            continue
        retained = [c for c in components if c['retained']]
        mine = set(int(c['component_id']) for c in retained)
        if args.run:
            run_row = recorded.get(index)
            if run_row is None:
                raise ValueError('recorded run has no frame %d' % index)
            claimed = set()
            for track in run_row['tracks']:
                claimed.update(int(v) for v in track['component_ids'])
            claimed.update(int(v) for v in run_row['ambiguous_component_ids'])
            if mine != claimed:
                raise ValueError('frontend recompute disagrees with recorded run at frame %d' % index)
            verify['componentIdsMatchedFrames'] += 1
            if [int(r) for r in run_row['target_source_rows']] != [int(r) for r in row['sourceRows']]:
                raise ValueError('recorded target rows differ from analysis at frame %d' % index)
            verify['targetRowsMatchedFrames'] += 1
        record = dict(frameIndex=index, stampSec=stamp_of(info),
                      rawSha256=hashlib.sha256(raw).hexdigest(),
                      measured=bool(row['measured']), jointPosture=row['posture']['state'],
                      jointPostureReason=row['posture']['reason'], jointState=row['state'],
                      jointReasons=row['reasons'], jointTrack=row['trackId'])
        target_rows = np.asarray(row['sourceRows'], dtype=np.int64)
        record['targetRows'] = int(len(target_rows))
        if len(target_rows):
            # 同一行集用 5cm/26 邻 3D 规则的自连通块数（无门限，纯结构对照）
            own = spatial_components(frame.xyz[target_rows].astype(np.float64), R3D_CELL_M)
            record['target3dClusters'] = len(own)
            record['target3dLargestFraction'] = round(
                max(len(g) for g in own) / float(len(target_rows)), 4) if own else None
        else:
            record['target3dClusters'] = None
            record['target3dLargestFraction'] = None
        # ---- 2D-only ----
        record['r2dRetainedComponents'] = len(retained)
        record['r2dTotalComponents'] = len(components)
        record['r2dForegroundPixels'] = int(mask.sum())
        if len(target_rows):
            cells = np.flatnonzero(np.isin(frame.source_rows, target_rows))
            lab = labels.ravel()[cells]
            lab = lab[lab >= 0]
            record['r2dTargetFragments'] = int(len(np.unique(lab)))
            shape = shape_features(frame, target_rows, labels)
            record.update(r2dRowSpan=shape['row_span'], r2dColSpan=shape['col_span'],
                          r2dFill=round(shape['fill_ratio'], 4),
                          r2dAspect=round(shape['aspect_col_row'], 4),
                          r2dAzSpanDeg=round(shape['azimuth_span_deg'], 3),
                          r2dElSpanDeg=round(shape['elevation_span_deg'], 3),
                          r2dRangeMedian=round(shape['range_median_m'], 4),
                          r2dAdjacentInvalid=round(shape['adjacent_invalid_fraction'], 4),
                          r2dTouchesBoundary=shape['touches_grid_boundary'])
            # 与目标同帧相邻（2 格内）的其它保留连通域 → 2D 平面粘连候选
            target_cell_set = cells
            others = np.zeros(grid.shape, dtype=bool)
            target_lab = set(int(v) for v in np.unique(lab))
            for comp in retained:
                if comp['component_id'] in target_lab:
                    continue
                others.ravel()[comp['cells']] = True
            grown = dilation2(target_cell_set, grid.shape, 2)
            record['r2dAdjacentOtherComponents'] = int(np.count_nonzero(others & grown))
        else:
            if row['measured']:
                raise ValueError('measured row without source rows')
            record['r2dTargetFragments'] = None
        # 2D 帧级存在性：只看 2D 前景连通域，不看 3D
        record['r2dFrameLabel'] = ('none' if not retained else
                                   'object' if len(retained) == 1 else 'ambiguous')
        # ---- 3D-only ----
        fg_cells = np.flatnonzero(mask.ravel())
        fg_rows = frame.source_rows.ravel()[fg_cells]
        fg_xyz = frame.xyz[fg_rows].astype(np.float64)
        groups = spatial_components(fg_xyz, R3D_CELL_M) if len(fg_xyz) else []
        groups = [np.asarray(g, dtype=np.int64) for g in groups if len(g) >= R3D_MIN_POINTS]
        groups.sort(key=lambda g: -len(g))
        record['r3dClusters'] = len(groups)
        record['r3dFrameLabel'] = ('none' if not groups else
                                   'object' if len(groups) == 1 else 'ambiguous')
        record['r3dClusterPoints'] = [int(len(g)) for g in groups[:6]]
        pose = None
        if len(target_rows) and groups:
            target_set = set(int(r) for r in target_rows)
            best, best_hit = None, 0
            for group in groups[:8]:
                hit = len(target_set & set(int(fg_rows[i]) for i in group))
                if hit > best_hit:
                    best, best_hit = group, hit
            if best is not None:
                pose = cluster_pose(frame, fg_rows[best], ground)
                pose['overlapFraction'] = round(best_hit / max(1, len(target_rows)), 4)
                pose['clusterRows'] = int(len(best))
                pose['recallOfCluster'] = round(best_hit / max(1, len(best)), 4)
        record['r3dTargetPose'] = pose
        record['r3dPose'] = pose['pose'] if pose else ('unknown' if row['measured'] else None)
        # ---- 位置一致性：3D 中心落点是否在该帧 2D 目标覆盖的标定格内 ----
        if len(target_rows):
            cells = np.flatnonzero(np.isin(frame.source_rows, target_rows))
            az_img = float(np.mean(grid.azimuth_deg.ravel()[cells]))
            el_img = float(np.mean(grid.elevation_deg.ravel()[cells]))
            centre = frame.xyz[target_rows].astype(np.float64).mean(axis=0)
            az_3d = math.degrees(math.atan2(centre[1], centre[0]))
            el_3d = math.degrees(math.atan2(centre[2], math.hypot(centre[0], centre[1])))
            record['positionDeltaDeg'] = round(max(abs(az_img - az_3d), abs(el_img - el_3d)), 6)
            distance = ((grid.azimuth_deg.ravel() - az_3d) ** 2
                        + (grid.elevation_deg.ravel() - el_3d) ** 2)
            nearest = int(np.argmin(distance))
            record['positionConflictCell'] = bool(nearest not in set(int(c) for c in cells))
            record['a3PositionConflict'] = record['positionConflictCell']
        else:
            record['positionDeltaDeg'] = None
            record['positionConflictCell'] = None
            record['a3PositionConflict'] = False
        # ---- 歧义类型（全部用冻结值/既有门，无新阈值） ----
        fragments = record.get('r2dTargetFragments')
        record['a1PlanarFragment'] = bool(record['r2dRetainedComponents'] >= 2
                                          and record['r3dClusters'] == 1)
        record['a1PlanarGlue'] = bool(record['r2dRetainedComponents'] == 1
                                      and record['r3dClusters'] >= 2)
        degenerate = bool(len(target_rows) and (
            (pose is None) or pose['axis_ambiguous'] or not pose['ground_relative']
            or (pose['point_count'] or 0) < PCA_MIN_POINTS))
        record['a2StructuralDegenerate'] = bool(
            degenerate and record.get('r2dTouchesBoundary') is False and fragments == 1)
        record['boundaryTruncation'] = bool(record.get('r2dTouchesBoundary'))
        rows_out.append(record)
        counts['frames'] += 1
        if record['measured']:
            counts['measured'] += 1
    # ---- 汇总 ----
    summary = dict(
        sessionId=session.name, analysisContentSha256=doc['contentSha256'],
        analysisRuntimeLedgerSha256=doc['runtimeLedgerSha256'],
        groundSha256=sha256_file(args.ground) if args.ground else None,
        groundNormal=ground['normal'] if ground else None,
        groundOffsetM=ground['offset_m'] if ground else None,
        gridSha256=identity['grid_sha256'], pointsSha256=identity['points_sha256'],
        prefixFrames=PREFIX_FRAMES, frames=len(rows_out), measured=counts['measured'],
        r2dFrameLabels=dict(Counter(r['r2dFrameLabel'] for r in rows_out)),
        r3dFrameLabels=dict(Counter(r['r3dFrameLabel'] for r in rows_out)),
        jointPosture=dict(Counter(r['jointPosture'] for r in rows_out)),
        r3dPoseMeasured=dict(Counter(r['r3dPose'] for r in rows_out if r['measured'])),
        ambiguity=dict(
            planarFragment=sum(1 for r in rows_out if r['a1PlanarFragment']),
            planarGlue=sum(1 for r in rows_out if r['a1PlanarGlue']),
            structuralDegenerate=sum(1 for r in rows_out if r['a2StructuralDegenerate']),
            positionConflict=sum(1 for r in rows_out if r['a3PositionConflict']),
            boundaryTruncation=sum(1 for r in rows_out if r['boundaryTruncation']),
            measuredFrameCount=sum(1 for r in rows_out if r['measured']),
        ),
        positionDeltaDeg=dict(
            n=sum(1 for r in rows_out if r['positionDeltaDeg'] is not None),
            max=max([r['positionDeltaDeg'] for r in rows_out if r['positionDeltaDeg'] is not None] or [None]),
        ),
        r2dTargetFragments=dict(Counter(str(r['r2dTargetFragments']) for r in rows_out if r['measured'])),
        target3dClusters=dict(Counter(str(r['target3dClusters']) for r in rows_out if r['measured'])),
        sameRowsPartition=dict(
            agree=sum(1 for r in rows_out if r['measured'] and r['r2dTargetFragments'] == r['target3dClusters']),
            split2dOnly=sum(1 for r in rows_out if r['measured'] and r['r2dTargetFragments'] > r['target3dClusters']),
            split3dOnly=sum(1 for r in rows_out if r['measured'] and r['r2dTargetFragments'] < r['target3dClusters']),
        ),
        r3dClustersMeasured=dict(Counter(str(r['r3dClusters']) for r in rows_out if r['measured'])),
        frontendVerifyAgainstRecordedRun=dict(verify) if args.run else None,
    )
    # 2D/3D/联合 三路在“有无物体”这一共同轴上的对照
    table = Counter()
    for r in rows_out:
        table[(r['r2dFrameLabel'], r['r3dFrameLabel'])] += 1
    summary['presenceAgreement'] = {'|'.join(k): v for k, v in sorted(table.items())}
    # 联合链在 2D/3D 分歧帧上的行为
    divergent = [r for r in rows_out if r['r2dFrameLabel'] != r['r3dFrameLabel']]
    summary['divergentFrames'] = len(divergent)
    summary['divergentJointBehavior'] = dict(Counter(
        ('ambiguous' if 'target_not_locked' in r['jointReasons'] else r['jointPosture'])
        for r in divergent))
    summary['divergentIndex'] = [r['frameIndex'] for r in divergent]
    result = dict(summary=summary, frames=rows_out)
    write_json(args.out, result)
    print(json.dumps(summary, ensure_ascii=False, indent=1))
    return 0


# ------------------------------------------------------------------ 预览渲染
_FONT = {
    '0': ('111', '101', '101', '101', '111'), '1': ('010', '110', '010', '010', '111'),
    '2': ('111', '001', '111', '100', '111'), '3': ('111', '001', '111', '001', '111'),
    '4': ('101', '101', '111', '001', '001'), '5': ('111', '100', '111', '001', '111'),
    '6': ('111', '100', '111', '101', '111'), '7': ('111', '001', '010', '010', '010'),
    '8': ('111', '101', '111', '101', '111'), '9': ('111', '101', '111', '001', '111'),
    'f': ('111', '100', '110', '100', '100'), ' ': ('000', '000', '000', '000', '000'),
    's': ('011', '100', '010', '001', '110'), 't': ('111', '010', '010', '010', '010'),
}


def draw_text(canvas, x0, y0, text, scale=2, colour=(255, 255, 255)):
    for n, ch in enumerate(text):
        glyph = _FONT.get(ch, _FONT[' '])
        for ry, line in enumerate(glyph):
            for rx, bit in enumerate(line):
                if bit != '1':
                    continue
                ys = y0 + ry * scale
                xs = x0 + (n * 4 + rx) * scale
                if 0 <= ys < canvas.shape[0] - scale and 0 <= xs < canvas.shape[1] - scale:
                    canvas[ys:ys + scale, xs:xs + scale] = colour


def ramp(rgb_range, valid):
    out = np.zeros(valid.shape + (3,), dtype=np.uint8)
    t = np.clip((rgb_range[valid] - .1) / 7.9, 0, 1)
    out[valid] = np.column_stack((255 * (1 - t), 255 * (1 - np.abs(2 * t - 1)),
                                  255 * t)).astype(np.uint8)
    return out


def scatter(panel, u, v, colours, u_lo, u_hi, v_lo, v_hi, size=3):
    h, w = panel.shape[:2]
    xs = ((u - u_lo) / (u_hi - u_lo) * (w - 1)).astype(np.int64)
    ys = (h - 1) - ((v - v_lo) / (v_hi - v_lo) * (h - 1)).astype(np.int64)
    ok = (xs >= 0) & (xs < w) & (ys >= 0) & (ys < h)
    xs, ys = xs[ok], ys[ok]
    colours = colours[ok]
    for dy in range(size):
        for dx in range(size):
            yy = np.clip(ys + dy, 0, h - 1)
            xx = np.clip(xs + dx, 0, w - 1)
            panel[yy, xx] = colours


def hline(panel, value, v_lo, v_hi, colour):
    h = panel.shape[0]
    row = int(round((h - 1) - (value - v_lo) / (v_hi - v_lo) * (h - 1)))
    if 0 <= row < h:
        panel[row, :] = colour


def vline(panel, value, u_lo, u_hi, colour):
    w = panel.shape[1]
    col = int(round((value - u_lo) / (u_hi - u_lo) * (w - 1)))
    if 0 <= col < w:
        panel[:, col] = colour


def cmd_render(args):
    session = Path(args.session).resolve()
    grid, meta, identity = grid_and_binding(session)
    ground = load_json(args.ground) if args.ground else None
    wanted = [int(v) for v in args.frames.split(',') if v.strip()]
    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    manifest_path = out / 'MANIFEST.json'
    manifest = load_json(manifest_path) if manifest_path.exists() else {}
    already = set(int(k) for k in manifest)
    clash = [i for i in wanted if i in already]
    if clash:
        raise SystemExit('refuse to re-render frames already exported: %s' % clash)
    target_rows = {}
    if args.target_json:
        for row in load_json(args.target_json)['frames']:
            target_rows[row['frameIndex']] = np.asarray(row['sourceRows'], dtype=np.int64)
    rendered = {}
    for index, info, raw, frame, mask, labels, components in frontend_scan(
            session, grid, identity, limit=max(wanted) + 1):
        if index not in wanted:
            continue
        rendered[index] = dict(info=info, frame=frame, mask=mask,
                               rgb=ramp(frame.range_m, frame.valid),
                               rawSha=hashlib.sha256(raw).hexdigest())
        if len(rendered) == len(set(wanted)):
            break
    manifest_new = {}
    rows_by_frame = {}
    for index in wanted:
        item = rendered.get(index)
        if item is None:
            raise SystemExit('frame %d not produced by frontend scan' % index)
        frame = item['frame']
        chosen = target_rows.get(index, np.zeros(0, dtype=np.int64))
        rgb2d = item['rgb'].copy()
        if len(chosen):
            sel = np.isin(frame.source_rows, chosen)
            blend = (rgb2d.astype(np.uint16) * 35
                     + np.array([0, 255, 0], dtype=np.uint16) * 65) // 100
            rgb2d[sel] = blend[sel].astype(np.uint8)
        rgb2d = rgb2d[::-1, ::-1]
        panel2d = np.repeat(np.repeat(rgb2d, args.scale, axis=0), args.scale, axis=1)
        fg_cells = np.flatnonzero(item['mask'].ravel())
        if args.points == 'all':
            fg_cells = np.flatnonzero(frame.valid.ravel())
        fg_rows = frame.source_rows.ravel()[fg_cells]
        xyz = frame.xyz[fg_rows].astype(np.float64)
        height = xyz[:, 2].copy()
        if ground is not None:
            height = xyz @ np.asarray(ground['normal'], dtype=float) + float(ground['offset_m'])
        shade = np.clip((height + .2) / 2.4, 0, 1)
        colours = np.column_stack((255 * shade, np.full(len(shade), 90.0),
                                   255 * (1 - shade))).astype(np.uint8)
        if len(chosen):
            colours[np.isin(fg_rows, chosen)] = (0, 255, 0)
        top = np.zeros((args.h, args.w, 3), dtype=np.uint8)
        side = np.zeros((args.h, args.w, 3), dtype=np.uint8)
        scatter(top, xyz[:, 0], xyz[:, 1], colours, args.x_lo, args.x_hi, args.y_lo, args.y_hi)
        scatter(side, np.hypot(xyz[:, 0], xyz[:, 1]), height, colours,
                0.0, args.d_max, args.z_lo, args.z_hi)
        hline(side, 0.0, args.z_lo, args.z_hi, (90, 90, 90))
        vline(top, 0.0, args.x_lo, args.x_hi, (90, 90, 90))
        draw_text(top, 4, 4, 't0p', 2)
        draw_text(side, 4, 4, 's1d', 2)
        body = np.concatenate((panel2d, top, side), axis=1)
        strip = np.zeros((26, body.shape[1], 3), dtype=np.uint8)
        draw_text(strip, 4, 4, 'f%d' % index, 3, (255, 255, 0))
        draw_text(strip, 100, 4, 'n%d' % len(chosen), 3, (0, 255, 0))
        draw_text(strip, 220, 4, 'p%02d' % len(rendered), 3, (120, 180, 255))
        rows_by_frame[index] = np.concatenate((strip, body), axis=0)
    groups = [wanted[i:i + args.rows] for i in range(0, len(wanted), args.rows)]
    for number, group in enumerate(groups):
        name = 'montage_%02d.png' % number
        path = out / name
        with path.open('xb') as stream:
            stream.write(png(np.concatenate([rows_by_frame[i] for i in group], axis=0)))
        for position, index in enumerate(group):
            manifest_new[str(index)] = dict(
                file=name, row=position, sha256=sha256_file(path),
                stampSec=stamp_of(rendered[index]['info']),
                rawSha256=rendered[index]['rawSha'], targetRows=int(len(target_rows.get(index, []))))
        print('rendered %s rows=%s' % (name, [i for i in group]))
    manifest.update(manifest_new)
    write_json(manifest_path, manifest)
    return 0


# ------------------------------------------------------------------ 表格
JOINT_MAP = {'lying_pending': 'lying', 'lying_candidate': 'lying',
             'vertical_surface': 'standing', 'unknown': 'unknown'}


def joint_label(row):
    """联合链的可比四类标签：躺倒 > 低姿态状态 > 直立表面 > unknown。"""
    if row['jointPosture'] in ('lying_pending', 'lying_candidate'):
        return 'lying'
    if row['jointState'] == 'low_posture_unclassified':
        return 'low'
    return JOINT_MAP.get(row['jointPosture'], 'unknown')


def cmd_tables(args):
    lines = []
    add = lines.append
    data = {}
    for tag, path in args.case:
        data[tag] = load_json(path)
    add('# 2D/3D 联合路线机器表格')
    add('')
    add('由 `pc_apps/range_fall/exp_2d3d/ablate.py tables` 生成；数值全部来自逐帧表，'
        '不手工改写。R2D = 2D 像面连通域；R3D = 5 cm/26 邻 3D 组件；联合 = 现规则链。')
    add('')
    add('## 1. 输入与共享信息')
    add('')
    add('| 代号 | 会话 | 帧 | 处理 | 丢帧 | 有目标帧 | 目标行合计 | 目标像素合计 | 逐帧相等帧数 | 地面 SHA |')
    add('|---|---|---|---|---|---|---|---|---|---|')
    for tag in data:
        s = data[tag]['summary']
        add('| %s | %s | %d | %d | %d | %d | %d | %d | %d | `%s` |' % (
            tag, s['sessionId'], s['frames'], s['frames'], 0, s['measured'],
            sum(r['targetRows'] for r in data[tag]['frames']),
            sum(r['targetRows'] for r in data[tag]['frames']),
            sum(1 for r in data[tag]['frames'] if r['measured']), (s['groundSha256'] or 'none')))
    add('')
    add('## 2. 同一行集上的 2D / 3D 结构对照')
    add('')
    add('| 代号 | 目标行 2D 分块=1 | =2 | ≥3 | 目标行 3D 分块=1 | =2 | 结构一致 | 仅 2D 分裂 | 仅 3D 分裂 |')
    add('|---|---|---|---|---|---|---|---|---|')
    for tag in data:
        fr = [r for r in data[tag]['frames'] if r['measured']]
        frag = Counter(r['r2dTargetFragments'] for r in fr)
        clus = Counter(r['target3dClusters'] for r in fr)
        sp = data[tag]['summary']['sameRowsPartition']
        add('| %s | %d | %d | %d | %d | %d | %d | %d | %d |' % (
            tag, frag[1], frag[2], sum(v for k, v in frag.items() if k and k >= 3),
            clus[1], clus[2], sp['agree'], sp['split2dOnly'], sp['split3dOnly']))
    add('')
    add('## 3. 帧级“有没有物体”对照（各自冻结门：2D ≥15 px，3D ≥30 点）')
    add('')
    for tag in data:
        add('%s：`%s`' % (tag, json.dumps(data[tag]['summary']['presenceAgreement'], ensure_ascii=False)))
        add('')
    add('## 4. 歧义类型计数（判定式见 ABLATION.md §3）')
    add('')
    add('| 代号 | 有目标帧 | 平面断裂 2D≥2/3D=1 | 平面粘连 2D=1/3D≥2 | 结构退化 | 位置冲突 | 像面边界截断 |')
    add('|---|---|---|---|---|---|---|')
    for tag in data:
        a = data[tag]['summary']['ambiguity']
        add('| %s | %d | %d | %d | %d | %d | %d |' % (
            tag, a['measuredFrameCount'], a['planarFragment'], a['planarGlue'],
            a['structuralDegenerate'], a['positionConflict'], a['boundaryTruncation']))
    add('')
    add('## 5. 姿态三路对照（只在有目标帧）')
    add('')
    add('| 代号 | 联合 直立 | 联合 低 | 联合 躺 | 联合 unknown | R3D 直立 | R3D 低 | R3D 躺 | R3D unknown | 逐帧一致 | 分歧 |')
    add('|---|---|---|---|---|---|---|---|---|---|---|')
    detail = {}
    for tag in data:
        fr = [r for r in data[tag]['frames'] if r['measured']]
        j = Counter(joint_label(r) for r in fr)
        p = Counter(r['r3dPose'] for r in fr)
        same = sum(1 for r in fr if joint_label(r) == r['r3dPose'])
        add('| %s | %d | %d | %d | %d | %d | %d | %d | %d | %d | %d |' % (
            tag, j['standing'], j['low'], j['lying'], j['unknown'],
            p['standing'], p['low'], p['lying'], p['unknown'], same, len(fr) - same))
        detail[tag] = Counter((joint_label(r), r['r3dPose']) for r in fr)
    add('')
    add('### 5.1 姿态交叉表')
    add('')
    for tag in data:
        add('%s：`%s`' % (tag, json.dumps({'|'.join(k): v for k, v in sorted(detail[tag].items())},
                                          ensure_ascii=False)))
        add('')
    add('## 6. 姿态分歧帧（联合 vs R3D 逐帧）')
    add('')
    for tag in data:
        rows = [r for r in data[tag]['frames'] if r['measured'] and joint_label(r) != r['r3dPose']]
        add('### %s（%d 帧）' % (tag, len(rows)))
        add('')
        if rows:
            add('| f | t/s | 联合 posture | 联合 state | R3D | top m | extent m | vert | 轴歧义 | 边界截断 | 2D 分块 |')
            add('|---|---|---|---|---|---|---|---|---|---|---|')
            for r in rows[:args.limit_rows]:
                pose = r['r3dTargetPose'] or {}
                add('| %d | %.3f | %s | %s | %s | %s | %s | %s | %s | %s | %s |' % (
                    r['frameIndex'], r['stampSec'] - data[tag]['frames'][0]['stampSec'],
                    r['jointPosture'], r['jointState'], r['r3dPose'],
                    fmt(pose.get('top_m')), fmt(pose.get('extent_m')), fmt(pose.get('verticality')),
                    pose.get('axis_ambiguous'), r.get('boundaryTruncation'), r.get('r2dTargetFragments')))
            if len(rows) > args.limit_rows:
                add('')
                add('（其余 %d 帧省略）' % (len(rows) - args.limit_rows))
        add('')
    add('## 7. 2D/3D 帧级分歧帧与联合链行为')
    add('')
    for tag in data:
        s = data[tag]['summary']
        add('%s：分歧 %d 帧，联合链行为 `%s`' % (
            tag, s['divergentFrames'], json.dumps(s['divergentJointBehavior'], ensure_ascii=False)))
        add('')
        rows = [r for r in data[tag]['frames'] if r['r2dFrameLabel'] != r['r3dFrameLabel']]
        rows = rows[:args.limit_rows]
        if rows:
            add('| f | 2D | 3D | 联合 posture | 联合 state | 主要 reason | 2D 保留域 | 3D 组件数 |')
            add('|---|---|---|---|---|---|---|---|')
            for r in rows:
                add('| %d | %s | %s | %s | %s | %s | %d | %d |' % (
                    r['frameIndex'], r['r2dFrameLabel'], r['r3dFrameLabel'],
                    r['jointPosture'], r['jointState'], '+'.join(r['jointReasons']),
                    r['r2dRetainedComponents'], r['r3dClusters']))
        add('')
    add('## 8. 复算一致性')
    add('')
    for tag in data:
        add('%s：`%s`' % (tag, json.dumps(data[tag]['summary'].get('frontendVerifyAgainstRecordedRun'),
                                          ensure_ascii=False)))
        add('')
    text = '\n'.join(lines) + '\n'
    Path(args.out).write_text(text, encoding='utf-8', newline='\n')
    print(text[:4000])
    return 0


def fmt(value, digits=3):
    return '-' if value is None else ('%.*f' % (digits, value))


# ------------------------------------------------------------------ GT 对照
def cmd_compare(args):
    gt = load_json(args.gt)
    cases = {}
    for tag, path in args.case:
        doc = load_json(path)
        cases[doc['summary']['sessionId']] = (tag, doc)
    rows, confusion = [], Counter()
    for label in gt['labels']:
        sid = label['sessionId']
        tag, doc = cases[sid]
        by_frame = {r['frameIndex']: r for r in doc['frames']}
        row = by_frame.get(label['frameIndex'])
        if row is None:
            raise ValueError('GT frame missing from ablation table')
        algo_person = 'yes' if row['measured'] else 'no'
        joint = joint_label(row)
        rows.append(dict(
            case=tag, sessionId=sid, frameIndex=label['frameIndex'],
            gtPerson=label['person'], gtPosture=label['posture'], confidence=label['confidence'],
            algoPerson=algo_person, jointPosture=joint, jointState=row['jointState'],
            r2d=row['r2dFrameLabel'], r3d=row['r3dFrameLabel'], r3dPose=row['r3dPose'],
            targetRows=row['targetRows'], jointReasons=row['jointReasons']))
        confusion[('person', label['person'], algo_person)] += 1
        confusion[('postureJoint', label['posture'], joint)] += 1
        confusion[('postureR3D', label['posture'], str(row['r3dPose']))] += 1
    definite = [r for r in rows if r['gtPerson'] in ('是', '否')]
    tp = sum(1 for r in definite if r['gtPerson'] == '是' and r['algoPerson'] == 'yes')
    fp = sum(1 for r in definite if r['gtPerson'] == '否' and r['algoPerson'] == 'yes')
    fn = sum(1 for r in definite if r['gtPerson'] == '是' and r['algoPerson'] == 'no')
    tn = sum(1 for r in definite if r['gtPerson'] == '否' and r['algoPerson'] == 'no')
    summary = dict(rows=len(rows), definite=len(definite), tp=tp, fp=fp, fn=fn, tn=tn,
                   precision=tp / (tp + fp) if tp + fp else None,
                   recall=tp / (tp + fn) if tp + fn else None,
                   confusion={'|'.join(k): v for k, v in sorted(confusion.items())},
                   confidence=dict(Counter(r['confidence'] for r in rows)),
                   indeterminate=sum(1 for r in rows if r['gtPerson'] == '不确定'))
    write_json(args.out, dict(summary=summary, rows=rows))
    print(json.dumps(summary, ensure_ascii=False, indent=1))
    return 0


# ------------------------------------------------------------------ CLI
def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest='command', required=True)

    p = sub.add_parser('survey')
    p.add_argument('--pair', nargs=3, action='append', required=True,
                   metavar=('TAG', 'SESSION', 'ANALYSIS'))
    p.add_argument('--out', type=Path)
    p.set_defaults(func=cmd_survey)

    p = sub.add_parser('fit-ground')
    p.add_argument('--session', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--window', choices=('head', 'spread', 'wide'),
                   help='只跑单个拟合窗口（默认依次尝试 head/spread/wide）')
    p.set_defaults(func=cmd_fit_ground)

    p = sub.add_parser('ablate')
    p.add_argument('--session', type=Path, required=True)
    p.add_argument('--analysis', type=Path, required=True)
    p.add_argument('--ground', type=Path)
    p.add_argument('--position-tolerance', type=float, default=1.0)
    p.add_argument('--limit', type=int)
    p.add_argument('--run', type=Path, help='已完成运行时目录，用于核对复算的连通域 id')
    p.add_argument('--out', type=Path, required=True)
    p.set_defaults(func=cmd_ablate)

    p = sub.add_parser('render')
    p.add_argument('--session', type=Path, required=True)
    p.add_argument('--frames', required=True)
    p.add_argument('--target-json', type=Path)
    p.add_argument('--ground', type=Path)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--scale', type=int, default=2)
    p.add_argument('--rows', type=int, default=4)
    p.add_argument('--w', type=int, default=320)
    p.add_argument('--h', type=int, default=384)
    p.add_argument('--x-lo', type=float, default=-4.0)
    p.add_argument('--x-hi', type=float, default=4.0)
    p.add_argument('--y-lo', type=float, default=-4.0)
    p.add_argument('--y-hi', type=float, default=4.0)
    p.add_argument('--z-lo', type=float, default=-1.0)
    p.add_argument('--z-hi', type=float, default=2.5)
    p.add_argument('--d-max', type=float, default=4.0)
    p.add_argument('--points', choices=('foreground', 'all'), default='foreground')
    p.set_defaults(func=cmd_render)

    p = sub.add_parser('tables')
    p.add_argument('--case', nargs=2, action='append', required=True, metavar=('TAG', 'ABLATE_JSON'))
    p.add_argument('--limit-rows', type=int, default=40)
    p.add_argument('--out', type=Path, required=True)
    p.set_defaults(func=cmd_tables)

    p = sub.add_parser('compare')
    p.add_argument('--gt', type=Path, required=True)
    p.add_argument('--case', nargs=2, action='append', required=True, metavar=('TAG', 'ABLATE_JSON'))
    p.add_argument('--out', type=Path, required=True)
    p.set_defaults(func=cmd_compare)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == '__main__':
    sys.exit(main())
