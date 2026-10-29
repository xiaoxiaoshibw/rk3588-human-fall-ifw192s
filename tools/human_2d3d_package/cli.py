"""命令行入口：manifest 自检 / 合成 demo / 已有测量行逐帧运行 / 包内单测。"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import unittest

import numpy as np

PACKAGE = Path(__file__).resolve().parent
if str(PACKAGE) not in sys.path:
    sys.path.insert(0, str(PACKAGE))

import human_2d3d
import synthetic
from core.capture_input import ROW_DTYPE

MANIFEST_KIND = 'human_2d3d_algorithm_source'


def verify_manifest(root=PACKAGE):
    root = Path(root).resolve()
    manifest = json.loads((root / 'MANIFEST.json').read_text(encoding='utf-8'))
    if manifest.get('kind') != MANIFEST_KIND:
        raise ValueError('unsupported manifest kind')
    if manifest.get('version') != human_2d3d.VERSION:
        raise ValueError('manifest version differs from the algorithm version')
    broken = []
    for name, expected in manifest['files'].items():
        path = (root / name).resolve()
        if root not in path.parents:
            raise ValueError('unsafe manifest path: ' + name)
        if not path.is_file():
            broken.append(name + ':missing')
        elif hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            broken.append(name + ':sha256')
    if broken:
        raise ValueError('manifest mismatch: ' + ', '.join(broken))
    return manifest


def check(args):
    report = dict(package=str(PACKAGE), version=human_2d3d.VERSION,
                  python=sys.version.split()[0], numpy=np.__version__,
                  semantic=human_2d3d.SEMANTIC, confirmedEnabled=False,
                  bodyParts='range_topology_branches_v2')
    manifest = verify_manifest()
    report['manifestVerified'] = True
    report['files'] = len(manifest['files'])
    grid = human_2d3d.Human2D3D().grid
    if grid.sha256 != manifest.get('gridSha256'):
        raise ValueError('calibration tables do not match the manifest grid SHA')
    report['gridSha256'] = grid.sha256
    report['calibrationMatched'] = True
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0


def demo(args):
    algorithm = human_2d3d.Human2D3D(session='synthetic-demo', body_parts=args.body)
    algorithm.install_ground()
    background = synthetic.scene_rows(algorithm.grid)
    person = synthetic.scene_rows(algorithm.grid, person=True)
    records, locked = [], None
    for index in range(args.frames):
        rows = background if index < args.prefix else person
        result = algorithm.feed(rows, round(index * args.dt, 9), index)
        record = human_2d3d.summary(result)
        records.append(record)
        print(json.dumps(record, ensure_ascii=False, sort_keys=True))
        if index >= args.prefix and result['target3d']['trackId'] is not None:
            locked = result['target3d']['trackId']
    if args.out:
        Path(args.out).write_text(json.dumps(records, ensure_ascii=False, indent=2) + '\n',
                                  encoding='utf-8')
    if locked is None:
        print('demo did not lock a target: the expected 3-frame birth window failed',
              file=sys.stderr)
        return 2
    print('demo locked target %s after %d frames; synthetic input, no accuracy claim'
          % (locked, args.frames), file=sys.stderr)
    return 0


def load_rows(path):
    path = Path(path)
    if path.suffix.lower() == '.npy':
        array = np.load(path, allow_pickle=False)
        if array.dtype != ROW_DTYPE or array.ndim != 1:
            raise ValueError('%s is not a 1-D capture_input.ROW_DTYPE array' % path)
        return array
    raw = path.read_bytes()
    if len(raw) % ROW_DTYPE.itemsize:
        raise ValueError('%s is not a multiple of %d bytes' % (path, ROW_DTYPE.itemsize))
    return np.frombuffer(raw, dtype=ROW_DTYPE)


def run(args):
    algorithm = human_2d3d.Human2D3D(session=args.session, body_parts=args.body,
                                      empty_prefix_frames=args.prefix)
    if args.ground:
        algorithm.install_ground()
    payloads = [load_rows(path) for path in args.packed]
    if not payloads:
        raise ValueError('at least one packed frame is required')
    statuses, records = [], []
    for index, rows in enumerate(payloads):
        result = algorithm.feed(rows, round(args.stamp0 + index * args.dt, 9), index)
        record = human_2d3d.summary(result)
        records.append(record)
        statuses.append(result['status'])
        print(json.dumps(record, ensure_ascii=False, sort_keys=True))
    if args.out:
        Path(args.out).write_text(json.dumps(records, ensure_ascii=False, indent=2) + '\n',
                                  encoding='utf-8')
    if len(payloads) < args.prefix:
        print('only %d frames fed; the declared %d-frame empty prefix is incomplete'
              % (len(payloads), args.prefix), file=sys.stderr)
        return 2
    return 0


def self_test(args):
    suite = unittest.defaultTestLoader.discover(str(PACKAGE / 'tests'), pattern='test_*.py')
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command')
    checker = sub.add_parser('check', help='校验包内 MANIFEST 与运行环境')
    checker.set_defaults(func=check)

    sample = sub.add_parser('demo', help='合成场景（不是实测数据）跑完整 2D→3D 链路')
    sample.add_argument('--prefix', type=int, default=50, help='显式声明的空场前缀帧数')
    sample.add_argument('--frames', type=int, default=54, help='总帧数（≥ 前缀 + 3）')
    sample.add_argument('--dt', type=float, default=0.1)
    sample.add_argument('--body', action='store_true', help='同时计算身体部位假设')
    sample.add_argument('--out', type=str)
    sample.set_defaults(func=demo)

    runner = sub.add_parser('run', help='按顺序喂入已有 28 字节测量行（.npy 或原始 .bin）')
    runner.add_argument('--packed', nargs='+', required=True)
    runner.add_argument('--session', default='local')
    runner.add_argument('--prefix', type=int, default=50)
    runner.add_argument('--stamp0', type=float, default=0.0)
    runner.add_argument('--dt', type=float, default=0.1)
    runner.add_argument('--ground', action='store_true', help='声明 z=0 地面平面（不是拟合）')
    runner.add_argument('--body', action='store_true')
    runner.add_argument('--out', type=str)
    runner.set_defaults(func=run)

    tests = sub.add_parser('test', help='运行包内单元测试')
    tests.set_defaults(func=self_test)
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, 'func', None):
        parser.print_help()
        return 0
    if args.command == 'demo' and args.frames < args.prefix + 3:
        parser.error('--frames must be at least --prefix + 3 to observe the birth window')
    return args.func(args)