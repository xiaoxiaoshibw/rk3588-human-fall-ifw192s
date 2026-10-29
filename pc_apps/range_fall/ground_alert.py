"""最小可用"倒地报警"：持续低姿态 → 疑似区间（变体 ground_alert_v1）。

做什么
  读取一个已有会话与它已验证的 analysis.json，用**生产同一个特征函数**
  `core.range_features.measured_features` 对同一批目标来源行复算地面相对高度，
  再交给 `core.range_ground_alert` 判"是否持续处于地面高度"，输出疑似区间。

为什么可信
  --verify 会逐帧把复算出的 `height_m.median` 与 analysis.json 里既有的
  `heightMedianM` 对账；全部相等才说明复算与生产链一致（386 已核 269/269）。

不做什么
  * 不写 analysis、不改生产默认与冻结配置、不重新选目标、不重新跟踪；
  * 不产生 confirmed，输出 semantic=UNKNOWN（没有人体/跌倒真值）；
  * 没有 --ground 时高度不可用，区间必然为空（这正是 780 原状的写照）。

仅 stdlib + NumPy，Python 3.8 语法兼容。
"""
import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
for _p in (ROOT / 'src/human_fall_detection', ROOT / 'src/human_fall_detection/scripts',
           ROOT / 'pc_apps/range_fall', ROOT / 'pc_apps/human_replay'):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from core.capture_input import ROW_DTYPE                      # noqa: E402
from core.range_contract import binding_tuple                 # noqa: E402
from core.range_features import measured_features             # noqa: E402
from core.range_ground_alert import SETTINGS as ALERT_SETTINGS  # noqa: E402
from core.range_ground_alert import VARIANT, scan              # noqa: E402
from core.range_image import ScanGrid                          # noqa: E402
from replay_range_frontend import CALIBRATION, session_meta    # noqa: E402

PROGRESS_EVERY = 100


def load_json(path):
    with Path(path).open(encoding='utf-8') as stream:
        return json.load(stream)


def sha256_file(path):
    import hashlib
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1 << 20), b''):
            digest.update(block)
    return digest.hexdigest()


def session_frames(session):
    """逐帧产出 (index, info, frame, analysis row)，只解码不聚类。"""
    meta, meta_sha = session_meta(session)
    grid = ScanGrid.from_csv(CALIBRATION / 'ifw192s_azimuth_192x256.csv',
                             CALIBRATION / 'ifw192s_elevation_192x256.csv')
    identity = dict(session=session.name, meta_sha256=meta_sha,
                    points_sha256=sha256_file(session / 'points.bin'),
                    coordinate='RAW/' + meta['sensor']['frame_id'], units='m',
                    coordinate_transform='identity', grid_sha256=grid.sha256,
                    epoch='source_header_epoch')
    identity['azimuth_sha256'] = sha256_file(CALIBRATION / 'ifw192s_azimuth_192x256.csv')
    identity['elevation_sha256'] = sha256_file(CALIBRATION / 'ifw192s_elevation_192x256.csv')
    binding = binding_tuple(identity)
    item_size = ROW_DTYPE.itemsize
    with (session / 'points.bin').open('rb') as stream:
        for index, info in enumerate(meta['frames']):
            stream.seek(info['offset_points'] * item_size)
            raw = stream.read(info['count_points'] * item_size)
            if len(raw) != info['count_points'] * item_size:
                raise ValueError('truncated frame %d' % index)
            stamp = info['stamp_sec'] + info.get('stamp_nanosec', 0) / 1e9
            yield index, stamp, grid.decode(raw, binding), identity


def build_records(session, analysis, ground, verify=False, limit=None, progress=True):
    """复算每帧 `height_m.median`，组装报警输入记录。"""
    doc = load_json(analysis)
    rows = {f['frameIndex']: f for f in doc['frames']}
    records, checks = [], dict(frames=0, measured=0, computed=0, verified=0,
                               mismatched=0, missingInAnalysis=0, maxAbsDiff=0.,
                               analysisSession=doc.get('sessionId'))
    for index, stamp, frame, identity in session_frames(session):
        if limit is not None and index >= limit:
            break
        row = rows.get(index)
        if row is None:
            raise ValueError('analysis has no frame %d' % index)
        target_rows = row.get('sourceRows') or []
        height = None
        if row.get('measured'):
            checks['measured'] += 1
            height = measured_features(frame, target_rows, ground)['height_m']
            height = None if height is None else height.get('median')
            if height is not None:
                checks['computed'] += 1
            recorded = row.get('heightMedianM')
            if verify:
                if recorded is None:
                    checks['missingInAnalysis'] += 1
                else:
                    diff = abs(float(height) - float(recorded)) if height is not None else float('inf')
                    checks['maxAbsDiff'] = max(checks['maxAbsDiff'], diff)
                    if diff <= 1e-9:
                        checks['verified'] += 1
                    else:
                        checks['mismatched'] += 1
        elif target_rows:
            raise ValueError('measured flag false but source rows present at frame %d' % index)
        records.append(dict(frameIndex=index, stampSec=stamp,
                            measured=bool(row.get('measured')),
                            trackId=row.get('trackId'), heightMedianM=height,
                            generation=row.get('generation'), observationGap=row.get('observationGap', False)))
        checks['frames'] += 1
        if progress and checks['frames'] % PROGRESS_EVERY == 0:
            print('  ... %d frames' % checks['frames'], file=sys.stderr)
    checks['maxAbsDiff'] = round(checks['maxAbsDiff'], 12)
    return records, checks


def render(result, label):
    lines = []
    add = lines.append
    add('## %s' % label)
    add('')
    add('| 项 | 值 |')
    add('|---|---|')
    add('| 变体 | `%s` |' % VARIANT)
    add('| 低姿态高度门 | ≤ %.3f m（`fall.low_height_m`） |' % ALERT_SETTINGS['low_height_m'])
    add('| 最短持续 | ≥ %.3f s（`fall.low_min_duration_s`） |' % ALERT_SETTINGS['min_duration_s'])
    add('| 低姿态帧 / 直立帧 / 不可用帧 | %d / %d / %d |'
        % (result['lowFrames'], result['uprightFrames'], result['unavailableFrames']))
    add('| 达标报警区间 | **%d** |' % len(result['intervals']))
    add('| 未达标低姿态段 | %d |' % len(result['rejected']))
    add('')
    if result['intervals']:
        add('| # | 帧区间 | 源时间区间 (s) | 时长 (s) | 帧数 | 最低中位高度 (m) | 状态 |')
        add('|---|---|---|---|---|---|---|')
        for i, iv in enumerate(result['intervals'], 1):
            add('| %d | f%d–f%d | %.3f–%.3f | **%.2f** | %d | %.3f | `%s`（confirmed=%s） |'
                % (i, iv['startFrame'], iv['endFrame'], iv['startSourceS'], iv['endSourceS'],
                   iv['durationS'], iv['frames'], iv['minHeightMedianM'], iv['state'],
                   'False'))
        add('')
    if result['rejected']:
        add('未达标段（差多少秒一目了然）：')
        add('')
        add('| 帧区间 | 时长 (s) | 帧数 | 最低中位高度 (m) |')
        add('|---|---|---|---|')
        for iv in result['rejected']:
            add('| f%d–f%d | %.2f | %d | %.3f |'
                % (iv['startFrame'], iv['endFrame'], iv['durationS'], iv['frames'],
                   iv['minHeightMedianM']))
        add('')
    return '\n'.join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description='持续低姿态报警（ground_alert_v1，默认关闭）')
    parser.add_argument('--session', type=Path, required=True)
    parser.add_argument('--analysis', type=Path, required=True)
    parser.add_argument('--ground', type=Path,
                        help='绑定地面；不给时高度不可用，区间必然为空')
    parser.add_argument('--out', type=Path, help='输出 JSON（区间 + 逐帧计数）')
    parser.add_argument('--md', type=Path, help='输出 Markdown 表')
    parser.add_argument('--label', default=None)
    parser.add_argument('--limit', type=int)
    parser.add_argument('--verify', action='store_true',
                        help='把复算高度与 analysis.heightMedianM 逐帧对账')
    parser.add_argument('--quiet', action='store_true')
    args = parser.parse_args(argv)

    ground = load_json(args.ground) if args.ground else None
    if ground is not None and ground.get('status') != 'valid':
        parser.error('ground file is not status=valid')
    records, checks = build_records(args.session, args.analysis, ground,
                                    verify=args.verify, limit=args.limit,
                                    progress=not args.quiet)
    result = scan(records)
    label = args.label or args.session.name
    document = dict(
        variant=VARIANT, sessionId=args.session.name, label=label,
        analysis=str(args.analysis), ground=str(args.ground) if args.ground else None,
        groundStatus=None if ground is None else ground.get('status'),
        groundOffsetM=None if ground is None else ground.get('offset_m'),
        settings=ALERT_SETTINGS, checks=checks, result=result,
        semantic='UNKNOWN', confirmedEnabled=False, confirmedCount=0,
    )
    if args.md:
        args.md.parent.mkdir(parents=True, exist_ok=True)
        args.md.write_text(render(result, label) + '\n', encoding='utf-8', newline='\n')
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        with args.out.open('w', encoding='utf-8', newline='\n') as stream:
            json.dump(document, stream, ensure_ascii=False, indent=2, allow_nan=False)
            stream.write('\n')
    if not args.quiet:
        print(render(result, label))
        print('checks: %s' % json.dumps(checks, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    sys.exit(main())
