"""离线单页对比：点云绿框（单人）+ 相机画面 + 跌倒候选时间轴（只读、离线）。

链路（检测算法只有 core 一份，本文件只喂离线输入并做显示）：

  原始会话 points.bin（28 字节行）
    -> core.range_image.ScanGrid                    标定 192x256 距离图（W1）
    -> core.range_offline.QuantileBackground        整段逐射线 p98 背景（显式非因果）
    -> core.range_runtime.RangeRuntime              去噪/连通域/跟踪/特征/状态机（与在线同一条链）
    -> core.range_offline.fit_declared_plane        本会话 RANSAC 地面（仅离线显示/高度参考）

  camera.mjpeg + camera_frames.jsonl -> 按“相机接收时刻 vs 雷达帧墙钟”取最近帧

边界（页面与 SUMMARY 里都写明）：
  * 背景是整段 98 分位（非因果），不是生产 W1 的显式空场前缀；只用于本回放可视化，
    不能安装到在线引擎。
  * 地面平面由本会话原始点云 RANSAC 拟合，physical_verified=false、runtime_eligible=false。
  * camera/雷达是主机接收时刻配对，无硬件同步、无外参，所以不在相机画面上投影点云。
  * 没有人工真值：人体语义、跌倒真值、召回/误报均 UNKNOWN；state=suspected 不是 confirmed。

用法：
  python -B pc_apps/range_fall/session_compare.py \
      --session data/sessions/cap_20261023_221125 \
      --out docs/evidence/2026-10-23_single_person_fall_compare
"""

import argparse
import hashlib
import json
import math
from pathlib import Path
import sys
import time

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
HF = ROOT / 'src' / 'human_fall_detection'
for extra in (str(HF), str(HF / 'scripts')):
    if extra not in sys.path:
        sys.path.insert(0, extra)

from core.capture_input import ROW_DTYPE, sha256_file  # noqa: E402
from core.fall_state import resolve_settings as fall_settings  # noqa: E402
from core.features import resolve_settings as feature_settings  # noqa: E402
from core.range_contract import binding_tuple, source_binding  # noqa: E402
from core.range_image import ScanGrid  # noqa: E402
from core.range_offline import (DECLARATION, DELTA_M, MIN_OBSERVATIONS,  # noqa: E402
                                QUANTILE, QuantileBackground, fit_declared_plane)
from core.range_runtime import RangeRuntime  # noqa: E402
from core.range_tracker import SETTINGS as TRACKER_SETTINGS, RangeTracker  # noqa: F401  RangeTracker 供 replay_compare 的“不运行跟踪”守卫引用
from replay_range_frontend import CALIBRATION, session_meta, write_json  # noqa: E402

SCHEMA = 'session_compare_v1'
SEED = 20261023
BACKGROUND_QUANTILE = QUANTILE
BACKGROUND_MIN_OBS = MIN_OBSERVATIONS
FOREGROUND_DELTA_M = DELTA_M
MAX_RANGE_M = 8.0
MIN_NEIGHBOURS = 2
MIN_COMPONENT_POINTS = 15
SCENE_DISPLAY_POINTS = 2400
TARGET_DISPLAY_POINTS = 2600
SCENE_VOXEL_M = 0.05
TARGET_VOXEL_M = 0.03

ALARM_STATES = ('suspected', 'confirmed')


class SessionCompareError(ValueError):
    """输入/输出不满足契约。"""


def _require(condition, message):
    if not condition:
        raise SessionCompareError(message)


def load_grid():
    return ScanGrid.from_csv(CALIBRATION / 'ifw192s_azimuth_192x256.csv',
                             CALIBRATION / 'ifw192s_elevation_192x256.csv')


def _iter_decoded(session, meta, grid, binding):
    """顺序解码整段；边读边累计原始字节摘要，结束后由调用方读取 .digest。"""
    digest = hashlib.sha256()
    handle = (session / 'points.bin').open('rb')
    try:
        for index, info in enumerate(meta['frames']):
            size = info['count_points'] * ROW_DTYPE.itemsize
            raw = handle.read(size)
            _require(len(raw) == size, 'points.bin 在帧 %d 处被截断' % index)
            digest.update(raw)
            yield index, info, grid.decode(raw, binding)
    finally:
        handle.close()
        _iter_decoded.digest = digest.hexdigest()


def fit_ground(points, seed=SEED):
    """兼容入口：平面拟合已迁到 core.range_offline（离线专用）。"""
    try:
        return fit_declared_plane(points, seed=seed)
    except ValueError as error:
        raise SessionCompareError(str(error)) from None


def background_range(stack, observed):
    """兼容入口：整段 p98 背景已迁到 core.range_offline。"""
    try:
        return QuantileBackground.from_stack(stack, observed).mean_m
    except ValueError as error:
        raise SessionCompareError(str(error)) from None


def display_basis(normal):
    """显示坐标：x 前向（原始 x 投影到水平面）、y 左、z 上。"""
    up = np.asarray(normal, dtype=np.float64)
    up = up / np.linalg.norm(up)
    forward = np.array([1.0, 0.0, 0.0]) - up * float(up[0])
    if np.linalg.norm(forward) < 1e-6:
        forward = np.array([0.0, 1.0, 0.0]) - up * float(up[1])
    forward = forward / np.linalg.norm(forward)
    left = np.cross(up, forward)
    return np.stack([forward, left, up])


def to_display(xyz, basis, offset_m):
    points = np.asarray(xyz, dtype=np.float64) @ np.asarray(basis).T
    points[:, 2] += float(offset_m)
    return points


def voxel_pick(points, size_m, limit, seed_key):
    """先按体素去重（空间均匀），再按固定种子压到点数上限。确定性。"""
    points = np.asarray(points, dtype=np.float64)
    if not len(points):
        return np.empty(0, dtype=np.int64)
    cells = np.floor(points / float(size_m)).astype(np.int64)
    _, first = np.unique(cells, axis=0, return_index=True)
    keep = np.sort(first)
    if len(keep) > limit:
        seed = int.from_bytes(hashlib.sha256(seed_key.encode('utf8')).digest()[:8], 'little')
        picked = np.random.default_rng(seed).choice(len(keep), int(limit), replace=False)
        keep = keep[np.sort(picked)]
    return points[keep]


def quantize(points):
    """显示用厘米整数，避免体积与浮点抖动。"""
    return [int(v) for v in np.rint(np.asarray(points, dtype=np.float64) * 100.0).ravel()]


def read_camera(session):
    rows_path = session / 'camera_frames.jsonl'
    blob_path = session / 'camera.mjpeg'
    if not rows_path.is_file() or not blob_path.is_file():
        return None
    rows = [json.loads(line) for line in rows_path.read_text(encoding='utf8').splitlines()
            if line.strip()]
    blob = blob_path.read_bytes()
    previous = None
    for index, row in enumerate(rows):
        for name in ('offset', 'length', 'recv_unix_ns'):
            _require(isinstance(row.get(name), int) and row[name] >= 0,
                     '相机索引第 %d 行缺少 %s' % (index, name))
        _require(row['length'] > 0 and row['offset'] + row['length'] <= len(blob),
                 '相机索引第 %d 行字节范围越界' % index)
        _require(row['recv_unix_ns'] > 0, '相机索引第 %d 行缺少接收时刻' % index)
        if previous is not None:
            _require(row['recv_unix_ns'] > previous, '相机接收时刻必须严格递增')
        previous = row['recv_unix_ns']
        data = blob[row['offset']:row['offset'] + row['length']]
        _require(data[:2] == b'\xff\xd8' and data[-2:] == b'\xff\xd9',
                 '相机索引第 %d 行不是完整 JPEG' % index)
    return rows, blob


def nearest_camera(rows, stamp):
    times = np.asarray([row['recv_unix_ns'] / 1e9 for row in rows], dtype=np.float64)
    index = int(np.argmin(np.abs(times - float(stamp))))
    return index, float(times[index] - float(stamp))


def _frame_relative_seconds(info, base):
    return (info['stamp_sec'] + info['stamp_nanosec'] / 1e9) - base


def build(session, out, *, limit=None, title=None, preview=True):
    session = Path(session).resolve()
    out = Path(out).resolve()
    _require(session.is_dir(), '会话目录不存在：%s' % session)
    for protected in (ROOT / 'data', ROOT / 'captures'):
        protected = protected.resolve()
        _require(not (out == protected or protected in out.parents or out in protected.parents),
                 '输出目录不能落在数据根内：%s' % out)
    _require(out != session and out not in session.parents, '输出目录不能是会话目录')
    template_path = Path(__file__).resolve().parent / 'template.html'
    _require(template_path.is_file(), '模板缺失：%s' % template_path)
    started = time.time()
    meta, meta_sha = session_meta(session)
    points_sha = sha256_file(session / 'points.bin')
    camera = read_camera(session)
    grid = load_grid()
    identity = source_binding(session, meta, meta_sha, points_sha, grid)
    identity['azimuth_sha256'] = sha256_file(CALIBRATION / 'ifw192s_azimuth_192x256.csv')
    identity['elevation_sha256'] = sha256_file(CALIBRATION / 'ifw192s_elevation_192x256.csv')
    binding = binding_tuple(identity)
    count = len(meta['frames']) if limit is None else int(limit)
    _require(1 <= count <= len(meta['frames']), '回放帧数越界')
    base_time = meta['frames'][0]['stamp_sec'] + meta['frames'][0]['stamp_nanosec'] / 1e9

    # 第一遍：只收集离线输入（整段背景统计 + 地面拟合采样）。
    stack = np.empty((count, grid.shape[0], grid.shape[1]), dtype=np.float32)
    observed = np.zeros(grid.shape, dtype=np.int32)
    ground_sample = []
    for index, info, frame in _iter_decoded(session, meta, grid, binding):
        if index >= count:
            break
        stack[index] = frame.range_m.astype(np.float32)
        observed += frame.valid
        if index in (0, count // 4, count // 2, (3 * count) // 4, count - 1):
            rows = frame.source_rows[frame.valid]
            with np.errstate(invalid='ignore'):
                kept = np.isfinite(frame.range_m[frame.valid]) & (frame.range_m[frame.valid] > 0.3)
            ground_sample.append(frame.xyz[rows][kept].astype(np.float64))
        del frame
    _require(len(ground_sample) >= 3, '可用于拟合地面的帧太少')
    if limit is None and count == len(meta['frames']):
        _require(_iter_decoded.digest == points_sha,
                 'points.bin 在回放期间发生变化（两遍字节摘要不一致）')
    ground = fit_declared_plane(np.concatenate(ground_sample), binding=identity,
                                frame=identity['coordinate'][4:], seed=SEED)
    ground['source'] = dict(meta_sha256=meta_sha, points_sha256=points_sha,
                            frame=ground['frame'], coordinate=identity['coordinate'])
    background = QuantileBackground.from_stack(stack, observed, binding=binding,
                                               grid_sha256=grid.sha256)
    del stack, ground_sample
    ground_sha = hashlib.sha256(json.dumps(ground, sort_keys=True, allow_nan=False).encode()).hexdigest()
    runtime = RangeRuntime(grid, identity, empty_prefix_frames=None, ground=ground,
                           ground_sha=ground_sha, background=background)

    basis = display_basis(ground['normal'])
    records = []
    states = {}
    first_state = {}
    selected_tracks = {}
    alarm_frames = []
    camera_pairs = []
    camera_unique = {}
    ground_alarm = None
    with (session / 'points.bin').open('rb') as stream:
        for index, info in enumerate(meta['frames'][:count]):
            size = info['count_points'] * ROW_DTYPE.itemsize
            raw = stream.read(size)
            _require(len(raw) == size, 'points.bin 在帧 %d 处被截断' % index)
            stamp = info['stamp_sec'] + info['stamp_nanosec'] / 1e9
            relative = stamp - base_time
            result, frame, _ = runtime.update(raw, stamp, index)
            record = result['tracking']
            rule = result['rule']
            features = rule['features']
            rows = np.asarray(record['target_source_rows'], dtype=np.int64)
            track_id = record['target_track_id']
            locked = bool(len(rows)) and track_id is not None
            state = rule['state']['state']
            states[state] = states.get(state, 0) + 1
            first_state.setdefault(state, round(relative, 3))
            if state in ALARM_STATES and ground_alarm is None:
                ground_alarm = round(relative, 3)
            if state in ALARM_STATES:
                alarm_frames.append(index)
            if locked:
                selected_tracks[track_id] = selected_tracks.get(track_id, 0) + 1
            _require(rule['state'].get('new_event') is None, '离线运行时不允许 confirmed/事件')

            height_block = features.get('height_m') or {}
            target_cm, box_cm, centre_cm = [], None, None
            target_points = (frame.xyz[rows].astype(np.float64) if locked
                             else np.empty((0, 3), dtype=np.float64))
            if len(target_points):
                display = to_display(target_points, basis, ground['offset_m'])
                centre_cm = [int(v) for v in np.rint(np.median(display, axis=0)[:2] * 100.0)]
                low = np.min(display, axis=0)
                high = np.max(display, axis=0)
                box_cm = [int(round(float(v) * 100.0)) for v in (*low, *high)]
                picked = voxel_pick(display, TARGET_VOXEL_M, TARGET_DISPLAY_POINTS,
                                    'target:%d' % index)
                target_cm = quantize(picked)
            scene_display = to_display(frame.xyz[frame.source_rows[frame.valid]],
                                       basis, ground['offset_m'])
            scene_cm = quantize(voxel_pick(scene_display, SCENE_VOXEL_M,
                                           SCENE_DISPLAY_POINTS, 'scene:%d' % index))

            camera_row = None
            if camera is not None and isinstance(info.get('bag_time_sec'), (int, float)):
                cam_index, cam_dt = nearest_camera(camera[0], info['bag_time_sec'])
                camera_pairs.append(abs(cam_dt))
                camera_unique[cam_index] = camera_unique.get(cam_index, 0) + 1
                camera_row = [cam_index, round(cam_dt, 4)]

            records.append(dict(
                i=index, t=round(relative, 3), st=state,
                rs=[code for code in rule['state'].get('reason_codes') or []][:4],
                tid=track_id if locked else None,
                n=int(len(rows)),
                hm=None if height_block.get('median') is None else round(float(height_block['median']), 3),
                ht=None if height_block.get('max') is None else round(float(height_block['max']), 3),
                sp=None if features.get('horizontal_extent_m') is None else round(float(features['horizontal_extent_m']), 3),
                rt=None if features.get('descent_rate_m_s') is None else round(float(features['descent_rate_m_s']), 2),
                vt=None if features.get('axis_verticality') is None else round(float(features['axis_verticality']), 2),
                bb=box_cm,
                c=centre_cm,
                cam=camera_row,
                bl=None,
                bg=scene_cm, tg=target_cm,
            ))
            del frame
    _require(sha256_file(session / 'points.bin') == points_sha
             and sha256_file(session / 'meta.json') == meta_sha,
             '回放期间源文件发生变化')

    out.mkdir(parents=True, exist_ok=False)
    if camera is not None:
        (out / 'camera').mkdir()
        for cam_index in sorted(camera_unique):
            row = camera[0][cam_index]
            data = camera[1][row['offset']:row['offset'] + row['length']]
            (out / 'camera' / ('c%03d.jpg' % cam_index)).write_bytes(data)
    (out / 'data').mkdir()
    frames_js = 'window.FRAMES=' + json.dumps(records, ensure_ascii=False,
                                              separators=(',', ':')) + ';\n'
    (out / 'data' / 'frames.js').write_text(frames_js, encoding='utf8')
    with (out / 'FRAMES.jsonl').open('x', encoding='utf8') as stream:
        for record in records:
            stream.write(json.dumps({key: value for key, value in record.items()
                                     if key not in ('bg', 'tg')},
                                    ensure_ascii=False, sort_keys=True) + '\n')
    write_json(out / 'GROUND.json', ground)

    target_frames = [record for record in records if record['n'] > 0]
    centres = np.asarray([record['c'] for record in target_frames], dtype=np.float64) / 100.0
    view = dict(
        yaw=-1.08, pitch=0.42, dist=4.8,
        tx=float(np.median(centres[:, 0])) if len(centres) else 2.0,
        ty=float(np.median(centres[:, 1])) if len(centres) else 0.0,
        tz=0.9,
    )
    sources = [Path(__file__).resolve(), template_path,
               *sorted((HF / 'core').glob('*.py'))]
    summary = dict(
        schema=SCHEMA,
        title=title or ('单会话对比：%s' % session.name),
        session=session.name,
        source=dict(
            meta_sha256=meta_sha, points_sha256=points_sha,
            camera_sha256=(sha256_file(session / 'camera.mjpeg')
                           if camera is not None else None),
            camera_index_sha256=(sha256_file(session / 'camera_frames.jsonl')
                                 if camera is not None else None),
            frames=count, camera_frames=(0 if camera is None else len(camera[0])),
            duration_sec=round(sum(_relative_delta(meta, index) for index in range(1, count)), 3)
            if count > 1 else 0.0,
            sensor=meta.get('sensor'), time_domain=meta.get('time_domain'),
            human_annotations=len(meta.get('human_annotations') or []),
        ),
        source_binding=identity,
        ground=ground,
        pipeline=dict(
            module='core.range_runtime.RangeRuntime',
            config=runtime.config, configSha256=runtime.config_sha,
            background=background.statistics(),
            ground=dict(offline_only=True, physical_verified=False, runtime_eligible=False),
            note='离线与在线共用同一条 core 运行时；差别只在显式声明的前景背景/地面输入',
        ),
        foreground=dict(
            method='core.range_offline.QuantileBackground（整段逐射线分位，非因果）',
            declaration=DECLARATION,
            quantile=BACKGROUND_QUANTILE, min_observations=BACKGROUND_MIN_OBS,
            delta_m=FOREGROUND_DELTA_M, max_range_m=MAX_RANGE_M,
            min_neighbours=MIN_NEIGHBOURS, min_component_points=MIN_COMPONENT_POINTS,
            note='整段统计的背景只用于本次回放展示，不是生产 W1 的空场前缀契约'),
        tracking=dict(
            tracker='core.range_tracker.RangeTracker', settings=dict(TRACKER_SETTINGS),
            frames_with_target=len(target_frames),
            target_ratio=round(len(target_frames) / max(1, len(records)), 4),
            first_target_s=target_frames[0]['t'] if target_frames else None,
            last_target_s=target_frames[-1]['t'] if target_frames else None,
            selected_tracks={key: value for key, value in sorted(selected_tracks.items())},
            semantic='unknown; 单目标关联结果，不是人体识别准确率'),
        fall=dict(
            machine='core.fall_state.FallStateMachine', settings=fall_settings(None),
            feature_settings=feature_settings(None),
            baseline=dict(mode='automatic_stance',
                          reason='由 core runtime 按逐帧观测采集；不作为疑似跌倒的前置条件'),
            states=states, first_state_s=first_state,
            alarm_states=list(ALARM_STATES), first_alarm_s=ground_alarm,
            alarm_frames=len(alarm_frames), events=[],
            confirmed_enabled=False,
            limits=['active_lying_indistinguishable_from_fall',
                    'no_human_labelled_geometry', 'suspected_is_not_confirmed']),
        camera_pairing=dict(
            pairs=len(camera_pairs),
            method='nearest camera reception time vs lidar bag wall time',
            median_abs_dt_s=None if not camera_pairs else round(float(np.median(camera_pairs)), 4),
            max_abs_dt_s=None if not camera_pairs else round(float(np.max(camera_pairs)), 4),
            hardware_sync=False, extrinsics=None,
            note='接收时刻配对，非硬件同步；无外参，页面不把点云投影到相机画面'),
        display=dict(
            coordinate='x forward / y left / z up (ground z=0), centimetres',
            view=view,
            scene_points_cap=SCENE_DISPLAY_POINTS, target_points_cap=TARGET_DISPLAY_POINTS,
            scene_voxel_m=SCENE_VOXEL_M, target_voxel_m=TARGET_VOXEL_M,
            frames_js_bytes=len(frames_js)),
        honesty=dict(
            human_gt='UNKNOWN', fall_gt='UNKNOWN', person_semantics='unknown',
            physical_verified=False, runtime_eligible=False, deployed=False,
            core_pipeline='core.range_runtime.RangeRuntime',
            non_causal_background=True,
            note='没有人工真值：召回/误报/人体有效性均 UNKNOWN；页面只展示 core 规则链输出'),
        verdict=_verdict(records, states, ground_alarm, alarm_frames, target_frames),
        reproduce='python -B pc_apps/range_fall/session_compare.py --session %s --out %s'
                  % (_display_path(session), _display_path(out)),
        sources={path.relative_to(ROOT).as_posix(): sha256_file(path) for path in sources},
        preview='PREVIEW.png' if preview else None,
    )
    write_json(out / 'SUMMARY.json', summary)
    html = (template_path.read_text(encoding='utf8')
            .replace('@@TITLE@@', summary['title'])
            .replace('@@SUBTITLE@@', _subtitle(summary))
            .replace('@@VERDICT@@', summary['verdict'])
            .replace('@@MAX_INDEX@@', str(len(records) - 1))
            .replace('@@VIEW@@', json.dumps(view))
            .replace('@@REPRODUCE@@', summary['reproduce'])
            .replace('@@SUMMARY_JSON@@', json.dumps(
                {key: summary[key] for key in ('session', 'source', 'fall', 'tracking',
                                               'camera_pairing', 'honesty')},
                ensure_ascii=False, indent=2)))
    _require('@@' not in html, '模板仍有未替换占位符')
    (out / 'index.html').write_text(html, encoding='utf8')
    if preview:
        render_preview(records, out / 'PREVIEW.png', summary)
    print(json.dumps(dict(output=str(out), frames=len(records),
                          verdict=summary['verdict'], states=states,
                          first_alarm_s=ground_alarm,
                          elapsed_s=round(time.time() - started, 2)),
                     ensure_ascii=False, indent=2))
    return summary


def _display_path(path):
    try:
        return Path(path).resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return Path(path).resolve().as_posix()


def _project(points, eye, right, up, forward, focal, cx, cy):
    points = np.asarray(points, dtype=np.float64).reshape(-1, 3)
    delta = points - eye
    depth = delta @ forward
    screen = np.empty((len(points), 3))
    screen[:, 0] = cx + focal * (delta @ right) / np.where(depth > 0.25, depth, np.nan)
    screen[:, 1] = cy - focal * (delta @ up) / np.where(depth > 0.25, depth, np.nan)
    screen[:, 2] = depth
    return screen


def render_preview(records, path, summary):
    """把与页面相同的显示数据渲染成 2x2 联络图（离线证据，不参与判定）。"""
    try:
        from PIL import Image, ImageDraw
    except ImportError:  # pragma: no cover - 仅 PC 工具需要
        return None
    picks = []
    rules = (lambda r: r['n'] > 0 and r['hm'] is not None and r['hm'] > 0.9 and r['t'] < 5.0,
             lambda r: r['st'] == 'low_posture_unclassified' and r['n'] > 0 and r['t'] > 4.0,
             lambda r: r['st'] in ALARM_STATES,
             lambda r: r['st'] == 'recovering' and r['n'] > 0)
    for rule in rules:
        for record in records:
            if rule(record):
                if record['i'] not in picks:
                    picks.append(record['i'])
                break
    if len(picks) < 4:
        for record in reversed(records):
            if record['n'] > 0 and record['i'] not in picks:
                picks.append(record['i'])
                break
    views = picks[:4]
    cell_w, cell_h, pad = 640, 430, 8
    sheet = Image.new('RGB', (cell_w * 2 + pad * 3, cell_h * 2 + pad * 3 + 26), (8, 11, 16))
    draw = ImageDraw.Draw(sheet)
    draw.text((pad, 6), '%s  |  green box = tracked target, grey = scene, preview only'
              % summary['session'], fill=(230, 238, 248))
    shown = summary['display']['view']
    yaw, pitch, dist = shown['yaw'], shown['pitch'], shown['dist']
    target = np.array([shown['tx'], shown['ty'], shown['tz']])
    cp, sp = math.cos(pitch), math.sin(pitch)
    eye = target + dist * np.array([cp * math.cos(yaw), cp * math.sin(yaw), sp])
    forward = target - eye
    forward = forward / np.linalg.norm(forward)
    right = np.cross(forward, np.array([0.0, 0.0, 1.0]))
    right = right / np.linalg.norm(right)
    up = np.cross(right, forward)
    ascii_state = {'unknown': 'UNKNOWN', 'upright': 'UPRIGHT', 'descending': 'DESCENDING',
                   'low_posture_unclassified': 'LOW', 'suspected': 'FALL-SUSPECT',
                   'confirmed': 'CONFIRMED', 'recovering': 'RECOVERING'}
    for slot, index in enumerate(views):
        record = records[index]
        panel = Image.new('RGB', (cell_w, cell_h - 22), (7, 10, 15))
        painter = ImageDraw.Draw(panel)
        focal, cx, cy = (cell_h - 22) * 0.95, cell_w / 2, (cell_h - 22) / 2
        for gx in np.arange(-1.0, 6.01, 0.5):
            line = _project([[gx, -4, 0], [gx, 4, 0]], eye, right, up, forward, focal, cx, cy)
            if np.isfinite(line[:, 2]).all():
                painter.line([tuple(line[0, :2]), tuple(line[1, :2])], fill=(38, 50, 66))
        for gy in np.arange(-4.0, 4.01, 0.5):
            line = _project([[-1, gy, 0], [6, gy, 0]], eye, right, up, forward, focal, cx, cy)
            if np.isfinite(line[:, 2]).all():
                painter.line([tuple(line[0, :2]), tuple(line[1, :2])], fill=(38, 50, 66))
        scene = np.asarray(record['bg'], dtype=np.float64).reshape(-1, 3) / 100.0
        target_points = np.asarray(record['tg'], dtype=np.float64).reshape(-1, 3) / 100.0
        for points, colour, size in ((scene, (54, 66, 84), 2), (target_points, (53, 255, 122), 3)):
            if not len(points):
                continue
            screen = _project(points, eye, right, up, forward, focal, cx, cy)
            order = np.argsort(-screen[:, 2])
            for row in screen[order]:
                if not np.isfinite(row[0]) or not np.isfinite(row[1]):
                    continue
                painter.rectangle([row[0], row[1], row[0] + size, row[1] + size], fill=colour)
        if record['bb']:
            x0, y0, z0, x1, y1, z1 = [value / 100.0 for value in record['bb']]
            corners = np.array([[x0, y0, z0], [x1, y0, z0], [x1, y1, z0], [x0, y1, z0],
                                [x0, y0, z1], [x1, y0, z1], [x1, y1, z1], [x0, y1, z1]])
            projected = _project(corners, eye, right, up, forward, focal, cx, cy)
            for a, b in ((0, 1), (1, 2), (2, 3), (3, 0), (4, 5), (5, 6), (6, 7), (7, 4),
                         (0, 4), (1, 5), (2, 6), (3, 7)):
                if np.isfinite(projected[[a, b], 2]).all():
                    painter.line([tuple(projected[a, :2]), tuple(projected[b, :2])],
                                 fill=(53, 255, 122), width=2)
        state_text = ascii_state.get(record['st'], record['st'])
        painter.text((10, 8), 'frame %03d  t=%0.2fs  %s  n=%d' %
                     (record['i'], record['t'], state_text, record['n']),
                     fill=(230, 238, 248))
        if record['n'] > 0:
            painter.text((10, 24), 'h_med=%s m  top=%s m  span=%s m  rate=%s m/s' % (
                _fmt(record['hm']), _fmt(record['ht']), _fmt(record['sp']), _fmt(record['rt'])),
                fill=(150, 200, 175))
        sheet.paste(panel, (pad + (slot % 2) * (cell_w + pad), 26 + pad + (slot // 2) * (cell_h + pad)))
    sheet.save(path)
    return path


def _fmt(value):
    return 'n/a' if value is None else '%0.2f' % value


def _relative_delta(meta, index):
    frame = meta['frames'][index]
    previous = meta['frames'][index - 1]
    return ((frame['stamp_sec'] + frame['stamp_nanosec'] / 1e9)
            - (previous['stamp_sec'] + previous['stamp_nanosec'] / 1e9))


def _verdict(records, states, alarm_s, alarm_frames, target_frames):
    parts = ['单人绿框 %d/%d 帧' % (len(target_frames), len(records))]
    if alarm_s is None:
        parts.append('本段未触发跌倒候选')
    else:
        span = '%0.2f–%0.2f s' % (alarm_s, max(records[index]['t'] for index in alarm_frames))
        parts.append('跌倒嫌疑 %s（%d 帧）' % (span, len(alarm_frames)))
    if states.get('confirmed'):
        parts.append('confirmed 帧 %d' % states['confirmed'])
    return '；'.join(parts)


def _subtitle(summary):
    source = summary['source']
    return ('%s · %d 帧雷达 / %d 帧相机 · %0.2f s'
            % (summary['session'], source['frames'], source['camera_frames'],
               source['duration_sec']))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--session', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--limit', type=int, default=None)
    parser.add_argument('--title', default=None)
    parser.add_argument('--no-preview', action='store_true', help='不生成 PREVIEW.png')
    args = parser.parse_args(argv)
    try:
        build(args.session, args.out, limit=args.limit, title=args.title,
              preview=not args.no_preview)
    except SessionCompareError as error:
        print('ERROR: %s' % error, file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
